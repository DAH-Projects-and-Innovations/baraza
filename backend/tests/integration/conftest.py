"""Opt-in real services: fresh Postgres database per session, rollback per test."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from baraza.db.migrations import upgrade_database
from baraza.db.session import Database


@pytest.fixture(scope="session")
def postgres_url():
    url = os.environ.get("BARAZA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set BARAZA_TEST_DATABASE_URL to run real Postgres integration tests")
    name = "baraza_test_" + uuid4().hex
    test_url = make_url(url).set(database=name).render_as_string(hide_password=False)

    async def manage(create):
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                statement = f'CREATE DATABASE "{name}"' if create else f'DROP DATABASE "{name}"'
                await connection.execute(text(statement))
        finally:
            await engine.dispose()

    async def migrate():
        database = Database(test_url)
        try:
            await upgrade_database(database.engine)
        finally:
            await database.dispose()

    asyncio.run(manage(True))
    try:
        asyncio.run(migrate())
        yield test_url
    finally:
        asyncio.run(manage(False))


@pytest.fixture
async def postgres_database(postgres_url):
    database = Database(postgres_url)
    try:
        yield database
    finally:
        await database.dispose()


@pytest.fixture
async def postgres_session(postgres_database):
    async with postgres_database.engine.connect() as connection:
        transaction = await connection.begin()
        sessions = async_sessionmaker(
            connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            async with sessions() as session:
                yield session
        finally:
            await transaction.rollback()
