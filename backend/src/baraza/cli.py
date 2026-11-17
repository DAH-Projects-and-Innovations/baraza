"""Administration commands.

    python -m baraza.cli create-user --email awa@example.org --name "Awa Example"
    python -m baraza.cli reset-password --email awa@example.org
    python -m baraza.cli deactivate-user --email awa@example.org

The password is asked on the terminal, or read from standard input when it is piped
(``echo ... | python -m baraza.cli create-user ...``). It is never an argument, so it does not
end up in the shell history.
"""

import argparse
import asyncio
import getpass
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from baraza.config import get_settings
from baraza.core.auth import (
    PasswordRejected,
    check_password_policy,
    hash_password,
    normalize_email,
)
from baraza.db.session import Database
from baraza.storage.auth import SessionRow, UserRow


def read_password() -> str:
    if sys.stdin.isatty():
        first = getpass.getpass("Password: ")
        if first != getpass.getpass("Repeat the password: "):
            raise SystemExit("The two passwords differ.")
        return first
    return sys.stdin.readline().rstrip("\r\n")


async def create_user(database: Database, email: str, name: str, password: str) -> str:
    async with database.sessions() as session, session.begin():
        user = UserRow(
            id=str(uuid.uuid4()),
            email=email,
            name=name.strip()[:200],
            password_hash=hash_password(password),
            is_active=True,
            created_at=datetime.now(UTC),
        )
        session.add(user)
    return user.id


async def reset_password(database: Database, email: str, password: str) -> bool:
    async with database.sessions() as session, session.begin():
        user = await session.scalar(select(UserRow).where(UserRow.email == email))
        if user is None:
            return False
        user.password_hash = hash_password(password)
        await session.execute(delete(SessionRow).where(SessionRow.user_id == user.id))
        return True


async def deactivate_user(database: Database, email: str) -> bool:
    async with database.sessions() as session, session.begin():
        user = await session.scalar(select(UserRow).where(UserRow.email == email))
        if user is None:
            return False
        user.is_active = False
        await session.execute(delete(SessionRow).where(SessionRow.user_id == user.id))
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="baraza.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="Create a person who can sign in")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    reset = commands.add_parser("reset-password", help="Set a new password and sign the person out")
    reset.add_argument("--email", required=True)
    deactivate = commands.add_parser("deactivate-user", help="Block sign in and end every session")
    deactivate.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    try:
        email = normalize_email(args.email)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    async def run() -> int:
        database = Database(get_settings().database_url)
        try:
            if args.command == "deactivate-user":
                done = await deactivate_user(database, email)
                print("Deactivated." if done else "No such user.", file=sys.stderr)
                return 0 if done else 1
            password = read_password()
            try:
                check_password_policy(password, email)
            except PasswordRejected as error:
                print(error, file=sys.stderr)
                return 2
            if args.command == "create-user":
                try:
                    await create_user(database, email, args.name, password)
                except IntegrityError:
                    print("A user with this email already exists.", file=sys.stderr)
                    return 1
                print(f"Created {email}.")
                return 0
            done = await reset_password(database, email, password)
            print("Password changed." if done else "No such user.", file=sys.stderr)
            return 0 if done else 1
        finally:
            await database.dispose()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
