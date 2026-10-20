"""Job de génération de bout en bout (issue #89).

Le job ne connaît ni la base de données ni le système de notification : il parle à
deux interfaces (MeetingRepository, Notifier) que le projet implémente, ce qui permet
de le tester avec un faux LLM et un dépôt en mémoire (voir app/minutes/testing.py).
"""
from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, replace
from typing import AsyncContextManager, Protocol

from app.llm.errors import LLMError

from .anti_invention import apply_anti_invention
from .json_output import generate_minutes_json
from .prompts import PROMPT_VERSION, build_messages
from .schema import ActionItem, Correction, Minutes, Segment, Transcript

logger = logging.getLogger(__name__)

# Statuts : À ALIGNER sur les états de réunion définis dans l'issue #77.
STATUS_GENERATING = "generating"
STATUS_DRAFT_READY = "draft_ready"
STATUS_GENERATION_FAILED = "generation_failed"

DEFAULT_TEMPLATE = "Standard meeting minutes: summary, decisions, action items."


class MeetingRepository(Protocol):
    async def get_status(self, meeting_id: str) -> str | None: ...
    async def set_status(self, meeting_id: str, status: str, reason: str | None = None) -> None: ...
    async def load_transcript(self, meeting_id: str) -> Transcript: ...
    async def load_template(self, meeting_id: str) -> str | None: ...
    async def save_draft(
        self, meeting_id: str, minutes: Minutes, corrections: list[Correction],
        model: str, prompt_version: str,
    ) -> str: ...
    async def create_action_items(self, meeting_id: str, items: list[ActionItem]) -> None: ...

    def transaction(self) -> AsyncContextManager[None]:
        """Les écritures du brouillon, des actions et du statut doivent réussir ou échouer ensemble."""
        ...


class Notifier(Protocol):
    async def notify_draft_ready(self, meeting_id: str) -> None: ...


@dataclass(frozen=True)
class GenerationResult:
    status: str  # "draft_ready" | "skipped" | "failed"
    draft_id: str | None = None
    error_code: str | None = None


def apply_speaker_renames(segments: list[Segment], renames: dict[str, str]) -> list[Segment]:
    return [
        replace(s, speaker=renames.get(s.speaker, s.speaker)) if s.speaker else s
        for s in segments
    ]


async def _fail(repo: MeetingRepository, meeting_id: str, code: str, reason: str) -> GenerationResult:
    await repo.set_status(meeting_id, STATUS_GENERATION_FAILED, reason)
    logger.warning("generation failed meeting=%s code=%s", meeting_id, code)
    return GenerationResult("failed", error_code=code)


async def run_generation(
    meeting_id: str,
    *,
    repo: MeetingRepository,
    client,
    notifier: Notifier,
    force: bool = False,
) -> GenerationResult:
    # Idempotence (reprise, issue #60) : un brouillon déjà prêt n'est pas régénéré ni dupliqué.
    if not force and await repo.get_status(meeting_id) == STATUS_DRAFT_READY:
        logger.info("generation skipped meeting=%s (already draft_ready)", meeting_id)
        return GenerationResult("skipped")

    await repo.set_status(meeting_id, STATUS_GENERATING)
    try:
        transcript = await repo.load_transcript(meeting_id)
        template = (await repo.load_template(meeting_id)) or DEFAULT_TEMPLATE
        renames = transcript.speaker_renames
        segments = sorted(apply_speaker_renames(transcript.segments, renames), key=lambda s: s.index)
        participants = [renames.get(p, p) for p in transcript.participants]
        if not segments:
            return await _fail(repo, meeting_id, "empty_transcript", "La transcription est vide.")

        messages = build_messages(segments, participants, template, transcript.meeting_date)
        minutes = await generate_minutes_json(client, messages)
        minutes, corrections = apply_anti_invention(
            minutes, segments, participants, transcript.meeting_date
        )

        async with repo.transaction():
            draft_id = await repo.save_draft(
                meeting_id, minutes, corrections, client.settings.model, PROMPT_VERSION
            )
            await repo.create_action_items(meeting_id, minutes.action_items)
            await repo.set_status(meeting_id, STATUS_DRAFT_READY)
    except LLMError as exc:
        return await _fail(repo, meeting_id, exc.code, exc.user_message)
    except Exception as exc:
        # Erreur inattendue (base de données, bug...) : statut lisible, puis on relance
        # l'exception pour que le worker (arq) la voie et puisse réessayer.
        logger.error("generation crashed meeting=%s error=%s", meeting_id, type(exc).__name__)
        with contextlib.suppress(Exception):
            await repo.set_status(meeting_id, STATUS_GENERATION_FAILED, "Erreur interne de génération.")
        raise

    # Le brouillon est enregistré : un échec de notification ne doit pas le remettre en cause.
    try:
        await notifier.notify_draft_ready(meeting_id)
    except Exception as exc:
        logger.warning("notification failed meeting=%s error=%s", meeting_id, type(exc).__name__)
    return GenerationResult("draft_ready", draft_id=draft_id)
