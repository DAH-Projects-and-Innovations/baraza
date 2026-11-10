"""Run Alembic on an existing engine (test/bootstrap tooling, never per request)."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command


def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))


async def upgrade_database(engine: AsyncEngine) -> None:
    def upgrade(connection: Connection) -> None:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    async with engine.begin() as connection:
        await connection.run_sync(upgrade)
