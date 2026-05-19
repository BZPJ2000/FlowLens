"""数据库连接和会话管理 — 支持 SQLite (本地开发) 和 MySQL (生产)"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
    pool_size=1,            # SQLite only supports one writer at a time
    pool_timeout=30,
)

if settings.database_url.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _set_wal(dbapi_connection, connection_record):
        """Enable WAL mode for concurrent reads during writes."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
