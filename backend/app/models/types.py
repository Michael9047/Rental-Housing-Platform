"""跨方言的列类型。

生产库是 PostgreSQL，但测试用内存 SQLite 建表（tests/conftest.py），
PG 专属类型必须给 SQLite 一个等价实现，否则 create_all 直接编译失败、
整个 API 层测试套件全部 error。

用 SQLAlchemy 原生的 with_variant：PostgreSQL 上 DDL 与行为和直接写
ARRAY / JSONB 完全一致，只有 sqlite 方言换成 JSON。

注意：PG 专属的数组/JSONB 运算符（如 `@>` 包含判断）在 SQLite 下依然不可用，
这里只保证建表与读写可用，不保证运算符跨方言等价。
"""
from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB


def string_array(length: int = 30):
    """PostgreSQL 上是 ARRAY(String(length))，SQLite 上退化成 JSON 数组。"""
    return ARRAY(String(length)).with_variant(JSON(), "sqlite")


def jsonb():
    """PostgreSQL 上是 JSONB，SQLite 上退化成 JSON。"""
    return JSONB().with_variant(JSON(), "sqlite")
