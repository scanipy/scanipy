"""SQLAlchemy ORM models for the scan/findings subsystem (CMP-FND-02).

Defines the declarative ``Base`` shared by the findings-store models. The
Alembic migration environment (``db/migrations/env.py``) deliberately ships
hand-authored DDL with ``target_metadata = None`` (the findings table is created
by CMP-CP-03's migration ``20260524_0001`` — the declared FND-02 vehicle), so
this ``Base`` is NOT wired into autogenerate. It exists so application code and
tests can introspect / map onto the existing ``findings`` table; the ORM model
mirrors that shipped DDL verbatim (column shapes, nullability, CHECK/constraint
names, indexes).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for scan-subsystem ORM models."""


__all__ = ["Base"]
