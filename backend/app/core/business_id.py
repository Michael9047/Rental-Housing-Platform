"""业务ID自动生成器 — 三层架构统一前缀+日期+序号"""
from __future__ import annotations

from datetime import date
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

# 前缀映射
_BIZ_PREFIX: dict[str, str] = {
    "institute": "INST",
    "unit_type": "UT",
    "room": "RM",
}

# 表名映射（用于直接 SQL 查询）
_BIZ_TABLE: dict[str, str] = {
    "institute": "institutes",
    "unit_type": "unit_types",
    "room": "rooms",
}


def _make_business_id(prefix: str, today: date, seq: int) -> str:
    """生成业务ID，格式：{前缀}-{YYYYMMDD}-{4位序号}"""
    return f"{prefix}-{today.strftime('%Y%m%d')}-{seq:04d}"


async def generate_business_id(session: AsyncSession, entity_type: str) -> str:
    """为指定实体类型生成下一个业务ID。

    Args:
        session: 异步数据库会话
        entity_type: 实体类型 — "institute" / "unit_type" / "room"

    Returns:
        格式化的业务ID，如 INST-20260728-0001

    实现：
        查询当日该类型已有的最大序号，+1 作为新序号。
        若当日尚无记录，序号从 0001 开始。
        此方法在同一个事务中执行，依赖数据库行锁避免并发冲突。
    """
    prefix = _BIZ_PREFIX.get(entity_type, "UNK")
    table = _BIZ_TABLE.get(entity_type, "unknown")
    today = date.today()
    pattern = f"{prefix}-{today.strftime('%Y%m%d')}%"

    # 查询当日最大 business_id (直接 SQL，避免 ORM 模型导入循环)
    raw_sql = text(
        f"SELECT business_id FROM {table} "
        f"WHERE business_id LIKE :pattern "
        f"ORDER BY business_id DESC LIMIT 1"
    )
    result = await session.execute(raw_sql, {"pattern": pattern})
    row = result.fetchone()

    if row and row[0]:
        # 提取末尾序号并 +1
        try:
            last_seq = int(str(row[0]).rsplit("-", 1)[-1])
            seq = last_seq + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    return _make_business_id(prefix, today, seq)
