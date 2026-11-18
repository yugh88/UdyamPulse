"""Alembic environment: migrates the database named by UP_DB_URL using the ORM metadata."""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from api.models.db import Base
from core.settings import get_settings

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().db_url.replace("%", "%%"))
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Monthly partitions of account_scores (and their indexes) are managed by raw SQL, not the ORM."""
    table = getattr(obj, "table", obj) if type_ == "index" else obj
    return not (reflected and compare_to is None and str(getattr(table, "name", "")).startswith("account_scores_"))


def run_migrations_offline() -> None:
    context.configure(url=get_settings().db_url, target_metadata=target_metadata, literal_binds=True, compare_type=True,
                      include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section) or {}, prefix="sqlalchemy.",
                                     poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                          include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
