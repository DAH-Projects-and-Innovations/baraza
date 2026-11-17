"""Passwords, session tokens and login throttling. Standard library only.

Design choices:
- Passwords are hashed with scrypt (memory hard, in the standard library: no new dependency).
- A session token is random and only its SHA-256 is stored, so a leaked database does not
  hand out live sessions.
- A login against an unknown email costs the same as one against a known email, so the answer
  does not reveal which addresses have an account.
"""

import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict
from functools import lru_cache

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LEN = 32
SCRYPT_MAXMEM = 64 * 1024 * 1024

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PasswordRejected(ValueError):
    """The password does not meet the policy. The message is safe to show."""


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or not EMAIL.fullmatch(email):
        raise ValueError("Enter a valid email address")
    return email


def check_password_policy(password: str, email: str) -> None:
    """Length matters more than composition rules; refuse the obvious reuse of the email."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordRejected(f"Use at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordRejected(f"Use at most {MAX_PASSWORD_LENGTH} characters")
    if password.lower() in {email.lower(), email.split("@")[0].lower()}:
        raise PasswordRejected("The password must not be your email address")
    if len(set(password)) < 4:
        raise PasswordRejected("Choose a less repetitive password")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_LEN,
        maxmem=SCRYPT_MAXMEM,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        expected = bytes.fromhex(digest)
        candidate = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return scheme == "scrypt" and hmac.compare_digest(candidate, expected)


@lru_cache
def dummy_hash() -> str:
    """A valid hash to verify against when the email is unknown (constant-cost answer)."""
    return hash_password(secrets.token_urlsafe(16))


def new_session_token() -> tuple[str, str]:
    """Return ``(token, token_hash)``: the token goes to the browser, the hash to the database."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginThrottle:
    """Pause sign in after repeated failures for one email from one address.

    Kept in memory: it is per process and resets on restart. Enough to slow down guessing on a
    single API instance; put a shared store behind it before running several instances.
    """

    def __init__(self, max_failures: int = 5, window_seconds: int = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[tuple[str, str], list[float]] = defaultdict(list)

    def _recent(self, key: tuple[str, str], now: float) -> list[float]:
        recent = [t for t in self._failures[key] if now - t < self.window]
        self._failures[key] = recent
        return recent

    def retry_after(self, key: tuple[str, str], now: float | None = None) -> int:
        """Seconds to wait before another attempt, or 0 when sign in is allowed."""
        now = time.monotonic() if now is None else now
        recent = self._recent(key, now)
        if len(recent) < self.max_failures:
            return 0
        return max(1, int(self.window - (now - recent[0])))

    def failure(self, key: tuple[str, str], now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._recent(key, now).append(now)

    def success(self, key: tuple[str, str]) -> None:
        self._failures.pop(key, None)

    def clear(self) -> None:
        self._failures.clear()
