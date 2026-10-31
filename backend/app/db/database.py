from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from backend.app.core.config import settings

# Serverless Postgres: no pool kept in a frozen function; the Neon pooler (PgBouncer) does the pooling,
# and it does not allow server-side prepared statements.
PG_ARGS = {"poolclass": NullPool, "connect_args": {"prepare_threshold": None}} if settings.is_postgres else {}

engine = create_async_engine(settings.db_url(sync=False), **PG_ARGS)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
