"""Read the stored minutes schema consumed by the existing frontend."""

from fastapi import APIRouter, HTTPException, Response

from baraza.core.minute_versions import MinutesNotFound, MinutesService
from baraza.core.minutes import Minutes
from baraza.db.session import SessionDep

router = APIRouter(prefix="/meetings/{meeting_id}/minutes", tags=["minutes"])


@router.get("")
async def get_minutes(meeting_id: str, response: Response, session: SessionDep) -> Minutes:
    try:
        stored = await MinutesService(session).get(meeting_id)
    except MinutesNotFound:
        raise HTTPException(status_code=404, detail="No minutes for this meeting") from None
    response.headers["ETag"] = f'"{stored.version}"'
    return stored.content
