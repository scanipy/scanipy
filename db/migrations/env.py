"""Alembic migration environment for Scanipy v3.2 (CMP-CP-03).

The database URL is sourced exclusively from the ``SCANIPY_DATABASE_URL``
environment variable (DOC-DB §2). No URL is baked into ``alembic.ini`` so the
identical migration sequence runs against the CI Postgres service, staging, and
production, each driven by its own secret-injected URL.

CMP-CP-03 ships DDL only; there is no SQLAlchemy ORM ``target_metadata`` because
the table shapes are authored by hand from ``DOC-DB §4`` (the column-shape
source of truth) rather than reflected from models. ``--autogenerate`` is
therefore unsupported by design.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# Inject the runtime URL from the environment. Fail loudly rather than silently
# running against a stray default — an unpinned target is an INV-2-adjacent
# foot-gun.
_database_url = os.environ.get("SCANIPY_DATABASE_URL")
if _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)

# No ORM metadata: hand-authored DDL only (see module docstring).
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' (``--sql``) mode, emitting SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("SCANIPY_DATABASE_URL is not set; cannot run offline migrations.")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection (the normal upgrade/downgrade path)."""
    section = config.get_section(config.config_ini_section) or {}
    if not section.get("sqlalchemy.url"):
        raise RuntimeError("SCANIPY_DATABASE_URL is not set; cannot run online migrations.")
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
