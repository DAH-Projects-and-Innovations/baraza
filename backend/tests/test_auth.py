"""Sign in, sessions, protected routes and the administration commands."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import update

from baraza.adapters.base import CaptureStatus
from baraza.api import auth as auth_api
from baraza.api.dependencies import get_meeting_store
from baraza.cli import create_user, deactivate_user, reset_password
from baraza.config import Settings, get_settings
from baraza.core.auth import (
    LoginThrottle,
    PasswordRejected,
    check_password_policy,
    hash_password,
    hash_token,
    new_session_token,
    normalize_email,
    verify_password,
)
from baraza.core.meeting_record import Meeting
from baraza.core.minutes import ActionItem, Minutes, SourceRef
from baraza.core.minutes_review import record_generated
from baraza.core.transcript import Transcript
from baraza.db.migrations import upgrade_database
from baraza.db.session import Database
from baraza.main import create_app
from baraza.storage.auth import SessionRow
from baraza.storage.sql import SqlMeetingStore

EMAIL = "awa@association-demo.org"
PASSWORD = "a long passphrase here"
ORIGIN = "http://localhost:3000"


@pytest.fixture(autouse=True)
def sign_in_switched_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("BARAZA_AUTH_ENABLED", "true")
    get_settings.cache_clear()
    auth_api.throttle.clear()  # the throttle is per process: tests must not share failures
    yield
    auth_api.throttle.clear()


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    asyncio.run(upgrade_database(db.engine))
    asyncio.run(create_user(db, EMAIL, "Awa Example", PASSWORD))
    yield db
    asyncio.run(db.dispose())


@pytest.fixture
def client(database: Database) -> Iterator[TestClient]:
    app = create_app()
    store = SqlMeetingStore(database.engine)
    app.dependency_overrides[get_meeting_store] = lambda: store
    with patch("baraza.main.Database", return_value=database), TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, password: str = PASSWORD, email: str = EMAIL):
    return client.post("/auth/login", json={"email": email, "password": password})


# --- protected routes ---------------------------------------------------------------------


def test_health_is_public_and_everything_else_needs_sign_in(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    for method, path in [
        ("get", "/meetings"),
        ("get", "/meetings/m1/minutes"),
        ("get", "/meetings/m1/minutes/meta"),
        ("put", "/meetings/m1/minutes"),
        ("post", "/meetings/m1/minutes/validate"),
        ("get", "/meetings/m1/segments"),
        ("post", "/captures"),
        ("get", "/captures/m1"),
        ("post", "/meetings/m1/capture"),
        ("get", "/auth/me"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, (method, path, response.status_code)


def test_signing_in_opens_the_routes(client: TestClient) -> None:
    assert client.get("/meetings").status_code == 401
    assert login(client).status_code == 200
    assert client.get("/meetings").status_code == 200
    me = client.get("/auth/me").json()
    assert me["email"] == EMAIL and me["name"] == "Awa Example"
    assert "password" not in str(me)


# --- sign in ------------------------------------------------------------------------------


def test_the_cookie_is_http_only_and_same_site(client: TestClient) -> None:
    cookie = login(client).headers["set-cookie"].lower()
    assert "baraza_session=" in cookie
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert "secure" not in cookie  # development on plain http


def test_the_cookie_is_secure_outside_development(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BARAZA_ENV", "production")
    get_settings.cache_clear()
    assert "secure" in login(client).headers["set-cookie"].lower()


def test_wrong_password_and_unknown_email_look_the_same(client: TestClient) -> None:
    wrong = login(client, password="not the password!!")
    unknown = login(client, email="nobody@association-demo.org")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "set-cookie" not in wrong.headers and "set-cookie" not in unknown.headers


def test_email_is_not_case_sensitive(client: TestClient) -> None:
    assert login(client, email="  AWA@Association-Demo.org ").status_code == 200


def test_repeated_failures_pause_sign_in(client: TestClient) -> None:
    for _ in range(5):
        assert login(client, password="wrong wrong wrong").status_code == 401
    blocked = login(client, password="wrong wrong wrong")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    # Even the right password waits, and another account is not affected.
    assert login(client).status_code == 429
    assert login(client, email="other@association-demo.org").status_code == 401


def test_a_session_ends_on_logout_and_cannot_be_reused(client: TestClient) -> None:
    token = login(client).cookies["baraza_session"]
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401
    client.cookies.set("baraza_session", token)
    assert client.get("/auth/me").status_code == 401  # the server forgot it


def test_logout_without_a_session_is_harmless(client: TestClient) -> None:
    assert client.post("/auth/logout").status_code == 204


def test_an_expired_session_is_refused(client: TestClient, database: Database) -> None:
    token = login(client).cookies["baraza_session"]

    async def expire() -> None:
        async with database.sessions() as session, session.begin():
            await session.execute(
                update(SessionRow)
                .where(SessionRow.token_hash == hash_token(token))
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )

    asyncio.run(expire())
    assert client.get("/auth/me").status_code == 401


def test_only_the_hash_of_the_token_is_stored(client: TestClient, database: Database) -> None:
    token = login(client).cookies["baraza_session"]

    async def stored() -> list[str]:
        from sqlalchemy import select

        async with database.sessions() as session:
            return list((await session.scalars(select(SessionRow.token_hash))).all())

    hashes = asyncio.run(stored())
    assert hashes == [hash_token(token)] and token not in hashes


# --- administration -----------------------------------------------------------------------


def test_a_deactivated_person_is_signed_out_and_cannot_return(
    client: TestClient, database: Database
) -> None:
    assert login(client).status_code == 200
    assert asyncio.run(deactivate_user(database, EMAIL)) is True
    assert client.get("/auth/me").status_code == 401
    assert login(client).status_code == 401
    assert asyncio.run(deactivate_user(database, "nobody@association-demo.org")) is False


def test_resetting_a_password_signs_everyone_out(client: TestClient, database: Database) -> None:
    assert login(client).status_code == 200
    assert asyncio.run(reset_password(database, EMAIL, "another long passphrase")) is True
    assert client.get("/auth/me").status_code == 401
    assert login(client).status_code == 401
    assert login(client, password="another long passphrase").status_code == 200


# --- changing your own password -----------------------------------------------------------


def test_changing_the_password(client: TestClient, database: Database) -> None:
    assert login(client).status_code == 200
    other = TestClient(client.app)
    with patch("baraza.main.Database", return_value=database), other:
        assert login(other).status_code == 200

        url = "/auth/password"
        wrong = client.post(
            url, json={"current_password": "nope nope nope", "new_password": "x" * 20}
        )
        assert wrong.status_code == 403
        weak = client.post(url, json={"current_password": PASSWORD, "new_password": "short"})
        assert weak.status_code == 422

        changed = client.post(
            url, json={"current_password": PASSWORD, "new_password": "a brand new passphrase"}
        )
        assert changed.status_code == 204
        assert client.get("/auth/me").status_code == 200  # this session stays
        assert other.get("/auth/me").status_code == 401  # the other one is ended
    client.post("/auth/logout")
    assert login(client).status_code == 401
    assert login(client, password="a brand new passphrase").status_code == 200


# --- writes from another page -------------------------------------------------------------


def test_a_write_from_an_unknown_origin_is_refused(client: TestClient) -> None:
    refused = client.post(
        "/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert refused.status_code == 403
    assert "set-cookie" not in refused.headers
    allowed = client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}, headers={"Origin": ORIGIN}
    )
    assert allowed.status_code == 200


def test_a_signed_in_browser_cannot_be_used_by_another_page(client: TestClient) -> None:
    assert login(client).status_code == 200
    hostile = {"Origin": "https://evil.example"}
    assert client.post("/auth/logout", headers=hostile).status_code == 403
    assert client.post("/meetings/m1/minutes/validate", headers=hostile).status_code == 403
    assert client.get("/auth/me").status_code == 200  # still signed in


def test_credentials_are_allowed_for_the_known_origin_only(client: TestClient) -> None:
    ok = client.options(
        "/meetings",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers["access-control-allow-credentials"] == "true"
    assert ok.headers["access-control-allow-origin"] == ORIGIN
    bad = client.options(
        "/meetings",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers


# --- the person is recorded in the history ------------------------------------------------


def test_the_revision_history_names_the_person(
    client: TestClient, database: Database, transcript: Transcript
) -> None:
    store = SqlMeetingStore(database.engine)
    meeting = Meeting(
        capture_id="m1",
        title="Pilot committee",
        meeting_url="https://meet.google.com/abc-defg-hij",
        adapter="fake",
        participants_informed=True,
        status=CaptureStatus.DONE,
        transcript=transcript,
    )
    draft = Minutes(
        summary="Draft",
        actions=[ActionItem(text="Do it", source=SourceRef(segment_indices=[0]))],
    )
    record_generated(meeting, draft)
    asyncio.run(store.save(meeting))

    assert login(client).status_code == 200
    edited = draft.model_copy(update={"summary": "Reviewed"})
    saved = client.put(
        "/meetings/m1/minutes", json=edited.model_dump(mode="json"), headers={"If-Match": '"1"'}
    )
    assert saved.status_code == 200, saved.text
    revisions = client.get("/meetings/m1/minutes/revisions").json()
    assert [(r["version"], r["saved_by"]) for r in revisions] == [(1, "assistant"), (2, EMAIL)]
    validated = client.post("/meetings/m1/minutes/validate", headers={"If-Match": '"2"'})
    assert validated.json()["validated_by"] == EMAIL


# --- units --------------------------------------------------------------------------------


def test_passwords_are_salted_and_verified() -> None:
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second and first.startswith("scrypt$")
    assert verify_password(PASSWORD, first) and verify_password(PASSWORD, second)
    assert not verify_password("a different passphrase", first)
    assert not verify_password(PASSWORD, "not a hash")
    assert not verify_password(PASSWORD, "bcrypt$1$2$3$aa$bb")


def test_the_password_policy() -> None:
    check_password_policy("a long passphrase here", EMAIL)
    for bad in ["short", "x" * 200, EMAIL, "awa", "aaaaaaaaaaaaaaaaaaaa"]:
        with pytest.raises(PasswordRejected):
            check_password_policy(bad, EMAIL)


def test_email_normalisation() -> None:
    assert normalize_email("  Awa@Example.ORG ") == "awa@example.org"
    for bad in ["", "no-at-sign", "a@b", "a b@c.d", "x" * 400 + "@a.bc"]:
        with pytest.raises(ValueError, match="valid email"):
            normalize_email(bad)


def test_session_tokens_are_random_and_hashed() -> None:
    token_a, hash_a = new_session_token()
    token_b, _ = new_session_token()
    assert token_a != token_b and len(token_a) >= 40
    assert hash_a == hash_token(token_a) and hash_a != token_a


def test_the_throttle_forgets_after_its_window() -> None:
    throttle = LoginThrottle(max_failures=3, window_seconds=60)
    key = ("a@b.c", "1.2.3.4")
    for moment in (0.0, 1.0, 2.0):
        assert throttle.retry_after(key, now=moment) == 0
        throttle.failure(key, now=moment)
    assert 0 < throttle.retry_after(key, now=3.0) <= 60
    assert throttle.retry_after(key, now=70.0) == 0
    throttle.failure(key, now=70.0)
    throttle.success(key)
    assert throttle.retry_after(key, now=71.0) == 0


def test_sign_in_cannot_be_switched_off_outside_development() -> None:
    Settings(_env_file=None, auth_enabled=False, env="development")
    with pytest.raises(ValidationError, match="only allowed"):
        Settings(_env_file=None, auth_enabled=False, env="production")
