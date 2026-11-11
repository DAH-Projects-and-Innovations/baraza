"""Dépôt en mémoire et notifier de test (même interface que SqlMinutesRepository)."""

import copy
from contextlib import asynccontextmanager
from dataclasses import dataclass

from baraza.core.pipeline import LoadedTranscript


@dataclass
class DraftRecord:
    minutes: object
    corrections: list
    model: str
    prompt_version: str


class MemRepo:
    def __init__(self, transcript: LoadedTranscript, status=None):
        self.transcript, self.status, self.reason = transcript, status, None
        self.history, self.drafts, self.items = [], [], []
        self.fail_on_items = None

    async def get_status(self, meeting_id):
        return self.status

    async def set_status(self, meeting_id, status, reason=None):
        self.status, self.reason = status, reason
        self.history.append(status)

    async def load_transcript(self, meeting_id):
        return self.transcript

    async def save_draft(self, meeting_id, minutes, corrections, model, prompt_version):
        self.drafts.append(DraftRecord(minutes, corrections, model, prompt_version))
        return len(self.drafts)

    async def create_action_items(self, meeting_id, draft_id, items):
        if self.fail_on_items:
            raise self.fail_on_items
        self.items = list(items)

    @asynccontextmanager
    async def transaction(self):
        snap = copy.deepcopy((self.drafts, self.items, self.status, self.reason, self.history))
        try:
            yield
        except BaseException:
            self.drafts, self.items, self.status, self.reason, self.history = snap
            raise


class Notifier:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    async def notify_draft_ready(self, meeting_id):
        if self.fail:
            raise RuntimeError("notification down")
        self.sent.append(meeting_id)
