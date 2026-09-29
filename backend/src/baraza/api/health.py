from fastapi import APIRouter

from baraza import __version__
from baraza.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "llm_is_external": settings.llm_is_external,
    }
