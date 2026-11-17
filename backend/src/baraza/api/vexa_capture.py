"""Vexa-specific capture control with durable handles shared with the polling worker.

The frontend contract lives in ``baraza.api.captures`` (``/captures``, adapter based).
"""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from baraza.adapters.vexa import VexaAdapter
from baraza.config import get_settings
from baraza.core.captures import VexaCaptureService
from baraza.db.session import DatabaseDep
from baraza.storage.captures import SqlCaptureStore, StoredMeeting
from baraza.storage.sql import SqlSegmentStore
from baraza.vexa.client import VexaClient

router = APIRouter(prefix="/meetings/{meeting_id}", tags=["vexa-capture"])


class StartCapture(BaseModel):
    meeting_url: str = Field(pattern=r"^https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}/?$")


class CaptureStarted(BaseModel):
    capture_id: str


def get_capture_store(database: DatabaseDep) -> SqlCaptureStore:
    return SqlCaptureStore(database.engine)


async def get_capture_service(database: DatabaseDep) -> AsyncIterator[VexaCaptureService]:
    settings = get_settings()
    if not settings.vexa_enabled or not settings.vexa_api_key.get_secret_value():
        raise HTTPException(status_code=503, detail="Vexa capture is not configured")
    client = VexaClient(settings)
    try:
        yield VexaCaptureService(
            VexaAdapter(client, settings),
            SqlCaptureStore(database.engine),
            SqlSegmentStore(database.engine),
        )
    finally:
        await client.aclose()


ServiceDep = Annotated[VexaCaptureService, Depends(get_capture_service)]
StoreDep = Annotated[SqlCaptureStore, Depends(get_capture_store)]


@router.post("/capture", status_code=201)
async def start_capture(
    meeting_id: str, request: StartCapture, service: ServiceDep
) -> CaptureStarted:
    try:
        capture_id = await service.start(meeting_id, request.meeting_url)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Meeting already has a capture") from None
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Vexa could not start the capture") from None
    return CaptureStarted(capture_id=capture_id)


@router.post("/capture/stop", status_code=202)
async def stop_capture(meeting_id: str, service: ServiceDep) -> dict[str, str]:
    try:
        await service.stop(meeting_id)
    except ValueError:
        raise HTTPException(
            status_code=409, detail="No active capture or invalid Vexa response"
        ) from None
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Vexa could not stop the capture") from None
    return {"status": "stopping"}


@router.get("/status")
async def meeting_status(meeting_id: str, store: StoreDep) -> StoredMeeting:
    try:
        return await store.get(meeting_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unknown meeting") from None
