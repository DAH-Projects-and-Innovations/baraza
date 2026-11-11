"""Pipeline complet de génération du compte rendu (issues #81 à #89).

Chaîne : transcription -> LLM (sortie structurée, une réparation) -> contrôles
anti-invention -> brouillon + actions + statut, dans une transaction -> notification.

Le job ne connaît ni la base ni le système de notification : il parle à deux interfaces
(MinutesRepository, Notifier). Voir baraza.storage.minutes_sql pour la version SQL.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import re
from collections import Counter
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from pydantic import ValidationError

from baraza.core.anti_invention import Correction, apply_anti_invention
from baraza.core.generation import load_prompt, render_transcript
from baraza.core.minutes import ActionItem, Minutes
from baraza.core.segments import TranscriptSegment
from baraza.llm.errors import InvalidModelOutputError, LLMError

logger = logging.getLogger(__name__)

# Statuts de génération. À ALIGNER sur les états de réunion (#77) si besoin.
STATUS_GENERATING = "generating"
STATUS_DRAFT_READY = "draft_ready"
STATUS_GENERATION_FAILED = "generation_failed"
STATUS_NOT_STARTED = "not_started"  # valeur renvoyée par l'API quand rien n'a encore été lancé

SUPPORTED_LANGUAGES = ("fr", "en")


@dataclass
class LoadedTranscript:
    """Ce que le job lit en base. Même forme que Transcript pour render_transcript."""

    meeting_id: str
    segments: list[TranscriptSegment]
    language: str = "en"
    meeting_date: date | None = None  # sert à vérifier l'année des échéances ; optionnelle


class MinutesRepository(Protocol):
    async def get_status(self, meeting_id: str) -> str | None: ...
    async def set_status(self, meeting_id: str, status: str, reason: str | None = None) -> None: ...
    async def load_transcript(self, meeting_id: str) -> LoadedTranscript: ...
    async def save_draft(
        self,
        meeting_id: str,
        minutes: Minutes,
        corrections: list[Correction],
        model: str,
        prompt_version: str,
    ) -> int: ...
    async def create_action_items(
        self, meeting_id: str, draft_id: int, items: list[ActionItem]
    ) -> None: ...

    def transaction(self) -> AbstractAsyncContextManager[None]:
        """Brouillon, actions et statut réussissent ou échouent ensemble."""
        ...


class Notifier(Protocol):
    async def notify_draft_ready(self, meeting_id: str) -> None: ...


class LogNotifier:
    """Notifier provisoire : journalise seulement (aucun contenu). À remplacer."""

    async def notify_draft_ready(self, meeting_id: str) -> None:
        logger.info("draft ready meeting=%s", meeting_id)


@dataclass(frozen=True)
class GenerationResult:
    status: str  # "draft_ready" | "skipped" | "failed"
    draft_id: int | None = None
    error_code: str | None = None
    corrections: tuple[str, ...] = field(default=())


# ---------------- sortie JSON robuste (#82) ----------------


def extract_json(text: str) -> dict:
    """Tolère les balises ```json et le texte autour de l'objet JSON."""
    t = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fenced:
        t = fenced.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(t[start : end + 1])


def describe_error(exc: Exception, limit: int = 5) -> str:
    """Chemins et messages seulement : jamais les valeurs reçues (pas de fuite de contenu)."""
    if isinstance(exc, ValidationError):
        parts = [
            f"{'.'.join(str(x) for x in e['loc']) or 'root'}: {e['msg']}"
            for e in exc.errors()[:limit]
        ]
        return "schema errors -> " + "; ".join(parts)
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})"
    return str(exc)


def normalize_language(language: str | None) -> str:
    code = (language or "").strip().lower()[:2]
    return code if code in SUPPORTED_LANGUAGES else "en"


def prompt_version_of(system_prompt: str, language: str) -> str:
    """Version automatique : change dès que le fichier de prompt change."""
    return f"{language}-{hashlib.sha256(system_prompt.encode('utf-8')).hexdigest()[:8]}"


async def generate_checked_minutes(
    transcript,
    llm,
    *,
    meeting_date: date | None = None,
    max_repairs: int = 1,
) -> tuple[Minutes, list[Correction], str]:
    """Retourne (minutes nettoyées, corrections, version du prompt).

    ``transcript`` : tout objet avec .segments (speaker, start, text) et .language.
    Une seule réparation : le message d'erreur de validation est renvoyé au modèle.
    """
    language = normalize_language(getattr(transcript, "language", None))
    system = load_prompt("minutes", language)
    user = render_transcript(transcript)
    if meeting_date is not None:
        user = (
            f"Meeting date: {meeting_date.isoformat()} (if a date is spoken without a year, "
            f"infer the year from this date)\n{user}"
        )
    schema = Minutes.model_json_schema()

    attempt_user = user
    for attempt in range(max_repairs + 1):
        raw = await llm.complete_json(system, attempt_user, schema=schema)
        try:
            minutes = Minutes.model_validate(extract_json(raw))
            break
        except (ValueError, ValidationError) as exc:  # JSONDecodeError est un ValueError
            summary = describe_error(exc)
            if attempt == max_repairs:
                raise InvalidModelOutputError(summary) from exc
            attempt_user = (
                f"{user}\n\nYour previous answer was invalid: {summary}. "
                "Return ONLY the corrected JSON object matching the required schema."
            )
    cleaned, corrections = apply_anti_invention(minutes, transcript.segments, meeting_date)
    return cleaned, corrections, prompt_version_of(system, language)


# ---------------- le job de bout en bout (#89) ----------------


async def _fail(
    repo: MinutesRepository, meeting_id: str, code: str, reason: str
) -> GenerationResult:
    await repo.set_status(meeting_id, STATUS_GENERATION_FAILED, reason)
    logger.warning("generation failed meeting=%s code=%s", meeting_id, code)
    return GenerationResult("failed", error_code=code)


def _model_name(llm) -> str:
    return str(getattr(llm, "model_name", None) or getattr(llm, "_model", None) or "unknown")


async def run_generation(
    meeting_id: str,
    *,
    repo: MinutesRepository,
    llm,
    notifier: Notifier,
    force: bool = False,
) -> GenerationResult:
    # Idempotence : un brouillon déjà prêt n'est ni régénéré ni dupliqué (reprise, #60).
    if not force and await repo.get_status(meeting_id) == STATUS_DRAFT_READY:
        logger.info("generation skipped meeting=%s (already draft_ready)", meeting_id)
        return GenerationResult("skipped")

    await repo.set_status(meeting_id, STATUS_GENERATING)
    try:
        transcript = await repo.load_transcript(meeting_id)
        if not transcript.segments:
            return await _fail(repo, meeting_id, "empty_transcript", "La transcription est vide.")

        minutes, corrections, prompt_version = await generate_checked_minutes(
            transcript, llm, meeting_date=transcript.meeting_date
        )
        async with repo.transaction():
            draft_id = await repo.save_draft(
                meeting_id, minutes, corrections, _model_name(llm), prompt_version
            )
            await repo.create_action_items(meeting_id, draft_id, minutes.actions)
            await repo.set_status(meeting_id, STATUS_DRAFT_READY)
    except LLMError as exc:
        return await _fail(repo, meeting_id, exc.code, exc.user_message)
    except Exception as exc:
        # Erreur inattendue (base, bug...) : statut lisible puis on relance pour qu'arq réessaie.
        logger.error("generation crashed meeting=%s error=%s", meeting_id, type(exc).__name__)
        with contextlib.suppress(Exception):
            await repo.set_status(
                meeting_id, STATUS_GENERATION_FAILED, "Erreur interne de génération."
            )
        raise

    try:  # le brouillon est enregistré : une notification qui échoue ne le remet pas en cause
        await notifier.notify_draft_ready(meeting_id)
    except Exception as exc:
        logger.warning("notification failed meeting=%s error=%s", meeting_id, type(exc).__name__)
    counts = Counter(c.kind for c in corrections)
    return GenerationResult(
        "draft_ready",
        draft_id=draft_id,
        corrections=tuple(f"{k}:{v}" for k, v in sorted(counts.items())),
    )
