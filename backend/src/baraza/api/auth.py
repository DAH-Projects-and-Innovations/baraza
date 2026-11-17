"""Sign in with an email and a password, kept as a server-side session in a cookie.

The cookie is HttpOnly (scripts cannot read it) and SameSite=Lax. Requests that change data
must also come from an allowed origin (see ``reject_foreign_origin`` in ``baraza.main``).
There is no public sign up: people are created by an administrator (``python -m baraza.cli``).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update

from baraza.config import get_settings
from baraza.core.auth import (
    LoginThrottle,
    PasswordRejected,
    check_password_policy,
    dummy_hash,
    hash_password,
    hash_token,
    new_session_token,
    normalize_email,
    verify_password,
)
from baraza.db.session import Database, DatabaseDep, get_database
from baraza.storage.auth import SessionRow, UserRow

COOKIE_NAME = "baraza_session"
TOUCH_AFTER = timedelta(minutes=5)

router = APIRouter(prefix="/auth", tags=["auth"])
throttle = LoginThrottle()


class CurrentUser(BaseModel):
    id: str
    email: str
    name: str


# Used when sign in is switched off for a local rehearsal (development only).
LOCAL_USER = CurrentUser(id="local-user", email="local-user", name="Local user")


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def user_for_token(database: Database, token: str | None) -> CurrentUser | None:
    if not token:
        return None
    now = _now()
    async with database.sessions() as session, session.begin():
        row = (
            await session.execute(
                select(SessionRow, UserRow)
                .join(UserRow, SessionRow.user_id == UserRow.id)
                .where(SessionRow.token_hash == hash_token(token), UserRow.is_active.is_(True))
            )
        ).first()
        if row is None:
            return None
        found, user = row
        if _aware(found.expires_at) <= now:
            return None
        if now - _aware(found.last_seen_at) > TOUCH_AFTER:
            await session.execute(
                update(SessionRow)
                .where(SessionRow.token_hash == found.token_hash)
                .values(last_seen_at=now)
            )
        return CurrentUser(id=user.id, email=user.email, name=user.name)


async def require_user(request: Request) -> CurrentUser:
    """The person making the request, or 401."""
    if not get_settings().auth_enabled:
        return LOCAL_USER
    user = await user_for_token(get_database(request), request.cookies.get(COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return user


UserDep = Annotated[CurrentUser, Depends(require_user)]


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )


@router.post("/login")
async def login(
    payload: LoginRequest, request: Request, response: Response, database: DatabaseDep
) -> CurrentUser:
    settings = get_settings()
    throttle.max_failures = settings.login_max_failures
    throttle.window = settings.login_lockout_minutes * 60
    try:
        email = normalize_email(payload.email)
    except ValueError:
        email = payload.email.strip().lower()[:320]
    key = (email, request.client.host if request.client else "unknown")

    wait = throttle.retry_after(key)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    async with database.sessions() as session:
        user = await session.scalar(select(UserRow).where(UserRow.email == email))
    # Same cost whether or not the account exists.
    stored = user.password_hash if user is not None and user.is_active else dummy_hash()
    valid = await asyncio.to_thread(verify_password, payload.password, stored)
    if user is None or not user.is_active or not valid:
        throttle.failure(key)
        raise HTTPException(status_code=401, detail="Email or password is incorrect")

    throttle.success(key)
    token, token_hash = new_session_token()
    now = _now()
    async with database.sessions() as session, session.begin():
        await session.execute(delete(SessionRow).where(SessionRow.expires_at <= now))
        session.add(
            SessionRow(
                token_hash=token_hash,
                user_id=user.id,
                created_at=now,
                expires_at=now + timedelta(days=settings.session_ttl_days),
                last_seen_at=now,
            )
        )
    _set_cookie(response, token)
    return CurrentUser(id=user.id, email=user.email, name=user.name)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, database: DatabaseDep) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        async with database.sessions() as session, session.begin():
            await session.execute(
                delete(SessionRow).where(SessionRow.token_hash == hash_token(token))
            )
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me")
async def me(user: UserDep) -> CurrentUser:
    return user


@router.post("/password", status_code=204)
async def change_password(
    payload: PasswordChange, request: Request, user: UserDep, database: DatabaseDep
) -> None:
    """Change your own password. Every other session of yours is signed out."""
    if not get_settings().auth_enabled:
        raise HTTPException(status_code=409, detail="Sign in is switched off")
    async with database.sessions() as session:
        row = await session.get(UserRow, user.id)
    valid = row is not None and await asyncio.to_thread(
        verify_password, payload.current_password, row.password_hash
    )
    if row is None or not valid:
        raise HTTPException(status_code=403, detail="The current password is incorrect")
    try:
        check_password_policy(payload.new_password, row.email)
    except PasswordRejected as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    new_hash = await asyncio.to_thread(hash_password, payload.new_password)
    keep = hash_token(request.cookies.get(COOKIE_NAME, ""))
    async with database.sessions() as session, session.begin():
        await session.execute(
            update(UserRow).where(UserRow.id == user.id).values(password_hash=new_hash)
        )
        await session.execute(
            delete(SessionRow).where(SessionRow.user_id == user.id, SessionRow.token_hash != keep)
        )
