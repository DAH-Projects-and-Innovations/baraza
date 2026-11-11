"""One async engine per app/worker, with transactional request sessions."""

from collections.abc import AsyncIterator
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from sqlalchemy import Connection, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url, pool_pre_ping=True)
        if self.engine.dialect.name == "sqlite":
            # SQLite's legacy driver mode otherwise releases a SAVEPOINT outside BEGIN,
            # defeating outer rollbacks in local tests. Also enforce its foreign keys.
            @event.listens_for(self.engine.sync_engine, "connect")
            def sqlite_connect(connection: Any, record: Any) -> None:
                connection.isolation_level = None
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            @event.listens_for(self.engine.sync_engine, "begin")
            def sqlite_begin(connection: Connection) -> None:
                connection.exec_driver_sql("BEGIN")

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        await self.engine.dispose()


def get_database(request: Request) -> Database:
    return cast(Database, request.app.state.database)


DatabaseDep = Annotated[Database, Depends(get_database)]


async def get_session(database: DatabaseDep) -> AsyncIterator[AsyncSession]:
    # A response commits only after successful completion; exceptions roll back.
    async with database.sessions() as session, session.begin():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
