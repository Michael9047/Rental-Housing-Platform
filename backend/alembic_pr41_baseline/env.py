"""PR41 本地基线迁移环境，仅供本地开发数据库初始化。"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 显式导入 PR41 的全部模型，确保 autogenerate 读取完整元数据。
from app.db.session import Base
import app.models  # noqa: F401
from app.models.university import University  # noqa: F401
from app.models.visit_message import VisitMessage  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """保留原历史迁移的版本表，避免基线迁移尝试删除它。"""
    return not (type_ == "table" and name in {"alembic_version", "alembic_pr41_baseline_version"})


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_pr41_baseline_version",
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_pr41_baseline_version",
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
