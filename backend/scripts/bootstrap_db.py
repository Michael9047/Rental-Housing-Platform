"""全新数据库引导脚本 — 从当前 SQLAlchemy 模型直接建库，并把 alembic stamp 到 head。

用于正式部署 / 新环境：对**空库**执行一次即可，之后照常使用 alembic 增量迁移。

背景：alembic 历史迁移链在空库上无法跑通（version_num 列长度、重复列操作等问题），
开发库是历史手工补表拼出来的，不可复现。本脚本绕过历史链，用当前模型一次建全，
保证新环境 schema 与代码完全一致。

运行: cd backend && .venv/Scripts/python.exe scripts/bootstrap_db.py
如要引导到其他库，先设置环境变量 DATABASE_URL / ALEMBIC_DATABASE_URL 再运行。
"""
import asyncio
import importlib
import logging
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 抑制 SQLAlchemy echo 噪音
for _name in ("sqlalchemy", "sqlalchemy.engine", "sqlalchemy.engine.Engine"):
    logging.getLogger(_name).setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("bootstrap")

from sqlalchemy import text

import app.models  # 命名空间包，供下方 pkgutil 遍历其子模块


def _import_all_models() -> None:
    """导入 app.models 下全部模块，确保所有 SQLAlchemy 模型注册进 Base.metadata。"""
    for m in pkgutil.iter_modules(app.models.__path__):
        importlib.import_module(f"app.models.{m.name}")
    log.info("已导入全部模型")


async def _build_schema() -> None:
    """建 pgvector 扩展 + 加宽的 alembic_version 表 + 全部业务表。"""
    from app.db.base import Base
    from app.db.session import engine

    async with engine.begin() as conn:
        # pgvector 扩展（embedding 向量列依赖）
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # 预建加宽版本的 alembic_version 表，避免超长 revision id 插入失败
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(255) NOT NULL PRIMARY KEY)"
        ))
        await conn.run_sync(Base.metadata.create_all)
    log.info("建表完成")


def _stamp_head() -> None:
    """调用 alembic CLI 把版本 stamp 到 head，之后的增量迁移照常链上。"""
    from app.core.config import get_settings

    settings = get_settings()
    env = {**os.environ, "ALEMBIC_DATABASE_URL": settings.alembic_database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "stamp", "head"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"alembic stamp head 失败:\n{result.stderr}")
    log.info("alembic 已 stamp 到 head")


async def main() -> None:
    _import_all_models()
    await _build_schema()
    _stamp_head()
    print("数据库引导完成：业务表已建全，alembic 已 stamp 到当前 head。")


if __name__ == "__main__":
    asyncio.run(main())
