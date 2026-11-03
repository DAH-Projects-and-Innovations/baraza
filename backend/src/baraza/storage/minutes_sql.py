"""Stockage SQL des brouillons de comptes rendus (issues #89 et #54, version minimale).

Tables ajoutées sur la même Base que transcript_segments :
  - minutes_generation   : statut de génération par réunion
  - minutes_drafts       : brouillons (historique : un nouveau brouillon à chaque régénération)
  - draft_action_items   : actions extraites d'un brouillon

draft_action_items est volontairement séparée du futur modèle « actions suivies entre réunions »
(#54) : à raccorder ou à remplacer quand ce modèle existera.
TODO (comme storage/sql.py) : remplacer create_all par une migration Alembic.
"""

from __future__ import annotations

from collections import Counter
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from baraza.core.anti_invention import Correction
from baraza.core.minutes import ActionItem, Minutes
from baraza.core.pipeline import LoadedTranscript, normalize_language
from baraza.storage.sql import Base, SqlSegmentStore


def _now() -> datetime:
    return datetime.now(UTC)


class MinutesStateRow(Base):
    __tablename__ = "minutes_generation"

    meeting_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MinutesDraftRow(Base):
    __tablename__ = "minutes_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(String(200), index=True)
    minutes: Mapped[dict] = mapped_column(JSON)
    corrections: Mapped[list] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DraftActionItemRow(Base):
    __tablename__ = "draft_action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(String(200), index=True)
    draft_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    segment_indices: Mapped[list] = mapped_column(JSON)


# Une session par tâche asyncio : plusieurs jobs peuvent partager le même dépôt sans conflit.
_current_session: ContextVar[AsyncSession | None] = ContextVar("minutes_session", default=None)


def engine_from_settings(settings) -> AsyncEngine:
    """Crée l'engine depuis Settings. HYPOTHÈSE : le champ s'appelle database_url."""
    for name in ("database_url", "db_url", "postgres_url", "sql_url"):
        url = getattr(settings, name, None)
        if url:
            return create_async_engine(str(url))
    raise RuntimeError("Aucun champ d'URL de base dans Settings (attendu : database_url).")


class SqlMinutesRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)
        self._segments = SqlSegmentStore(engine)
        self._ready = False

    async def _ensure_schema(self) -> None:
        if not self._ready:
            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            self._ready = True

    @asynccontextmanager
    async def _session(self):
        """Session de la transaction en cours si elle existe, sinon une session autonome."""
        await self._ensure_schema()
        current = _current_session.get()
        if current is not None:
            yield current
            return
        async with self._sessions() as session, session.begin():
            yield session

    @asynccontextmanager
    async def transaction(self):
        await self._ensure_schema()
        if _current_session.get() is not None:  # transaction déjà ouverte : on la réutilise
            yield
            return
        async with self._sessions() as session, session.begin():
            token = _current_session.set(session)
            try:
                yield
            finally:
                _current_session.reset(token)

    # --- statut ---

    async def get_status(self, meeting_id: str) -> str | None:
        state = await self.get_state(meeting_id)
        return state[0] if state else None

    async def get_state(self, meeting_id: str) -> tuple[str, str | None] | None:
        async with self._session() as s:
            row = await s.get(MinutesStateRow, meeting_id)
            return (row.status, row.reason) if row else None

    async def set_status(self, meeting_id: str, status: str, reason: str | None = None) -> None:
        async with self._session() as s:
            await s.merge(MinutesStateRow(
                meeting_id=meeting_id, status=status, reason=reason, updated_at=_now()
            ))

    # --- lecture de la transcription (segments stockés par l'ingestion, #78) ---

    async def load_transcript(self, meeting_id: str) -> LoadedTranscript:
        rows = await self._segments.list(meeting_id)
        final = [r for r in rows if r.is_final]  # les segments provisoires sont ignorés
        languages = Counter(r.language for r in final if r.language)
        language = normalize_language(languages.most_common(1)[0][0] if languages else None)
        return LoadedTranscript(meeting_id=meeting_id, segments=final, language=language)

    # --- écriture du brouillon ---

    async def save_draft(
        self, meeting_id: str, minutes: Minutes, corrections: list[Correction],
        model: str, prompt_version: str,
    ) -> int:
        async with self._session() as s:
            row = MinutesDraftRow(
                meeting_id=meeting_id,
                minutes=minutes.model_dump(mode="json"),
                corrections=[c.model_dump(mode="json") for c in corrections],
                model=model,
                prompt_version=prompt_version,
            )
            s.add(row)
            await s.flush()
            return row.id

    async def create_action_items(
        self, meeting_id: str, draft_id: int, items: list[ActionItem]
    ) -> None:
        async with self._session() as s:
            for item in items:
                s.add(DraftActionItemRow(
                    meeting_id=meeting_id, draft_id=draft_id, text=item.text, owner=item.owner,
                    due_date=item.due_date, segment_indices=list(item.source.segment_indices),
                ))

    # --- lecture pour l'API ---

    async def get_latest_draft(self, meeting_id: str) -> dict | None:
        async with self._session() as s:
            row = (await s.scalars(
                select(MinutesDraftRow).where(MinutesDraftRow.meeting_id == meeting_id)
                .order_by(MinutesDraftRow.id.desc()).limit(1)
            )).first()
            if row is None:
                return None
            return {
                "id": row.id, "created_at": row.created_at, "model": row.model,
                "prompt_version": row.prompt_version, "minutes": row.minutes,
                "corrections": row.corrections,
            }
