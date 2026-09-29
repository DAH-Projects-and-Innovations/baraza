"""Draft minutes generation from a transcript."""

from importlib import resources

from baraza.core.minutes import Minutes
from baraza.core.transcript import Transcript
from baraza.llm.client import LLMClient


def load_prompt(name: str, language: str) -> str:
    return resources.files("baraza.prompts").joinpath(language, f"{name}.md").read_text("utf-8")


def render_transcript(transcript: Transcript) -> str:
    return "\n".join(
        f"[{i}] {seg.speaker} ({seg.start:.0f}s): {seg.text}"
        for i, seg in enumerate(transcript.segments)
    )


async def generate_minutes(transcript: Transcript, llm: LLMClient) -> Minutes:
    # TODO: split long meetings into chunks, then synthesize.
    raw = await llm.complete_json(
        load_prompt("minutes", transcript.language), render_transcript(transcript)
    )
    return Minutes.model_validate_json(raw)
