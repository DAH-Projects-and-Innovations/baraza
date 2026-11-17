"""Minutes templates available when starting a capture."""

from fastapi import APIRouter
from pydantic import BaseModel

from baraza.config import get_settings
from baraza.core.templates import TEMPLATES

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateInfo(BaseModel):
    id: str
    name: dict[str, str]
    description: dict[str, str]
    default: bool


@router.get("")
async def list_templates() -> list[TemplateInfo]:
    default = get_settings().default_template
    return [
        TemplateInfo(id=t.id, name=t.name, description=t.description, default=t.id == default)
        for t in TEMPLATES.values()
    ]
