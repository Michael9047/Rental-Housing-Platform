from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# 连接池：面向高并发场景显式配置，避免默认 pool_size=5 在大量客户时被瞬间占满导致请求排队。
# - pool_pre_ping：取连接前先 ping，丢弃被 DB 端关闭的死连接
# - pool_recycle：30 分钟回收，规避云数据库/连接代理的空闲超时
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=1800,
    pool_pre_ping=True,
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass
