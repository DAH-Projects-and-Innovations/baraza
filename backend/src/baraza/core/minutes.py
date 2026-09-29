"""Schema of the minutes returned by the language model.

Hard rule: the system never invents anything. Information missing from the
transcript is ``None`` and rendered as "Not specified" in the user's language.
"""

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Link back to the transcript passage (segment indices)."""

    segment_indices: list[int] = Field(min_length=1)


class Decision(BaseModel):
    text: str
    source: SourceRef


class ActionItem(BaseModel):
    text: str
    owner: str | None = None
    due_date: str | None = None
    source: SourceRef


class OpenPoint(BaseModel):
    text: str
    source: SourceRef


class Topic(BaseModel):
    title: str
    summary: str
    source: SourceRef


class Minutes(BaseModel):
    summary: str
    topics: list[Topic] = []
    decisions: list[Decision] = []
    actions: list[ActionItem] = []
    open_points: list[OpenPoint] = []
