"""Doubles de test : dépôt en mémoire et notifier enregistreur (tests et démonstration)."""
from __future__ import annotations

import copy
from contextlib import asynccontextmanager
from dataclasses import dataclass

from .schema import ActionItem, Correction, Minutes, Transcript


@dataclass
class DraftRecord:
    minutes: Minutes
    corrections: list[Correction]
    model: str
    prompt_version: str


class InMemoryRepository:
    def __init__(self, transcript: Transcript, template: str | None = "Standard", status: str | None = None):
        self.transcript, self.template, self.status = transcript, template, status
        self.reason: str | None = None
        self.status_history: list[str] = []
        self.drafts: list[DraftRecord] = []
        self.action_items: list[ActionItem] = []
        self.fail_on_create_action_items: Exception | None = None  # pour simuler une panne de base

    async def get_status(self, meeting_id):
        return self.status

    async def set_status(self, meeting_id, status, reason=None):
        self.status, self.reason = status, reason
        self.status_history.append(status)

    async def load_transcript(self, meeting_id):
        return self.transcript

    async def load_template(self, meeting_id):
        return self.template

    async def save_draft(self, meeting_id, minutes, corrections, model, prompt_version):
        self.drafts.append(DraftRecord(minutes, corrections, model, prompt_version))
        return f"draft-{len(self.drafts)}"

    async def create_action_items(self, meeting_id, items):
        if self.fail_on_create_action_items:
            raise self.fail_on_create_action_items
        self.action_items = list(items)

    @asynccontextmanager
    async def transaction(self):
        snapshot = copy.deepcopy((self.drafts, self.action_items, self.status, self.reason, self.status_history))
        try:
            yield
        except BaseException:
            self.drafts, self.action_items, self.status, self.reason, self.status_history = snapshot
            raise


class RecordingNotifier:
    def __init__(self, fail: bool = False):
        self.sent: list[str] = []
        self.fail = fail

    async def notify_draft_ready(self, meeting_id):
        if self.fail:
            raise RuntimeError("notification service down")
        self.sent.append(meeting_id)
