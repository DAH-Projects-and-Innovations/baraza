"""Schéma du compte rendu (issue #82) et types d'entrée."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class Segment:
    """Segment de transcript (contrat #111 avec Nancy : à aligner sur le sien)."""

    index: int
    text: str
    speaker: str | None = None
    start_ms: int | None = None


@dataclass
class Transcript:
    meeting_id: str
    segments: list[Segment]
    participants: list[str] = field(default_factory=list)
    speaker_renames: dict[str, str] = field(default_factory=dict)
    meeting_date: date | None = None  # sert à vérifier l'année des échéances (#83)


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Decision(_Model):
    text: str = Field(min_length=1)
    segment_indices: list[int] = Field(default_factory=list)


class ActionItem(_Model):
    description: str = Field(min_length=1)
    owner: str | None = None
    due_date: str | None = None  # ISO "YYYY-MM-DD" de préférence, sinon texte
    segment_indices: list[int] = Field(default_factory=list)


class Minutes(_Model):
    title: str = ""
    summary: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


class Correction(_Model):
    """Trace d'une correction anti-invention, montrée aux relecteurs."""

    kind: Literal["item_rejected", "owner_nulled", "due_date_nulled", "due_date_year_adjusted"]
    item_type: Literal["decision", "action_item"]
    item_position: int
    original_value: str | None
    reason: str


def minutes_json_schema() -> dict:
    """JSON schema envoyé aux fournisseurs qui supportent les sorties structurées (#82)."""
    return Minutes.model_json_schema()
