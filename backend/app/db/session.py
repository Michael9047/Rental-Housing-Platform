from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=getattr(settings, "db_pool_size", 20),
    max_overflow=getattr(settings, "db_max_overflow", 10),
    pool_timeout=getattr(settings, "db_pool_timeout", 30),
    pool_recycle=1800,
    pool_pre_ping=True,
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass
