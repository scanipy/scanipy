"""Legacy Docker API: historical reads and explicit native-scan unavailability.

The unsafe in-process Git/Semgrep route is removed under #396. The current
contract is docs/bhmea/LEGACY-APP-CUTOVER.md. This is containment, not the
completed Black Hat deployment: the capture/accepted-input/worker cutover is
still required. Existing database schema and historical response fields are
not upgraded to new structural or provenance guarantees.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
    text,
    update,
)

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
DATABASE_URL = os.environ.get(
    "SCANIPY_DATABASE_URL", "postgresql://scanipy:scanipy_dev@localhost:5432/scanipy_dev"
)
S_VERSION = os.environ.get("SCANIPY_S_VERSION", "oracle-2026.08")
NATIVE_SCAN_ERROR: Final = (
    "Native scanning is unavailable pending the reviewed capture and worker cutover."
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("scanipy.oracle")

_engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
_meta = MetaData(schema="oracle")

scan_tbl = Table(
    "scan",
    _meta,
    Column("id", String(36), primary_key=True),
    Column("repo_url", Text, nullable=False),
    Column("commit_sha", String(40)),
    Column("status", String(16), nullable=False),  # running | done | error
    Column("phase", String(16), nullable=False),  # queued | cloning | detecting | done
    Column("error", Text),
    Column("s_version", Text, nullable=False),
    Column("env_digest", Text, nullable=False),
    Column("files", Integer),
    Column("duration_s", Float),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
finding_tbl = Table(
    "finding",
    _meta,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("scan_id", String(36), nullable=False, index=True),
    Column("origin", String(32), nullable=False),  # always oracle-passthrough
    Column("engine", String(32), nullable=False),  # semgrep
    Column("cwe", String(32)),
    Column("rule_id", Text, nullable=False),
    Column("severity", String(16), nullable=False),
    Column("title", Text),
    Column("message", Text),
    Column("file", Text, nullable=False),
    Column("line", Integer, nullable=False),
    Column("snippet", Text),
    Column("snippet_start_line", Integer),
    Column("slice_fingerprint", String(64), nullable=False),
    Column("fingerprint_class", String(8), nullable=False),  # weak (never strong here)
)


class NativeScanUnavailableError(RuntimeError):
    """The legacy native route has no reviewed execution profile."""


def _compute_env_digest() -> str:
    """Compatibility refusal: no version/rule probe or fabricated digest."""
    raise NativeScanUnavailableError(NATIVE_SCAN_ERROR)


def _init_db() -> None:
    with _engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS oracle"))
    _meta.create_all(_engine)


def _run_semgrep(src: Path) -> dict[str, object]:
    """Compatibility refusal before even inspecting a supplied source path."""
    raise NativeScanUnavailableError(NATIVE_SCAN_ERROR)


def _run_scan(scan_id: str, repo_url: str) -> None:
    """Compatibility refusal before ID/URL handling, staging or persistence."""
    raise NativeScanUnavailableError(NATIVE_SCAN_ERROR)


def _startup() -> None:
    _init_db()
    # Preserve legacy restart handling; this is not durable queue recovery.
    with _engine.begin() as conn:
        reaped = conn.execute(
            update(scan_tbl)
            .where(scan_tbl.c.status == "running")
            .values(status="error", phase="done", error="interrupted by a restart")
        ).rowcount
    logger.info("startup complete; native scans unavailable; reaped %s orphaned scan(s)", reaped)


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    _startup()
    yield


app = FastAPI(title="Scanipy — legacy read API (DOCKER-01)", lifespan=_lifespan)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "env_digest": None,
        "env_digest_status": "not-observed",
        "s_version": S_VERSION,
        "s_version_status": "configured-only",
        "capabilities": {"native_scan": "unavailable", "historical_read": "legacy"},
        "unavailable_reason": NATIVE_SCAN_ERROR,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.post("/api/scan")
def post_scan() -> JSONResponse:
    """No request-model parsing or background work while this route is disabled."""
    return JSONResponse(
        {"code": "native_scan_unavailable", "error": NATIVE_SCAN_ERROR, "retryable": False},
        status_code=503,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/scan/{scan_id}")
def get_scan(scan_id: str) -> JSONResponse:
    with _engine.begin() as conn:
        row = conn.execute(select(scan_tbl).where(scan_tbl.c.id == scan_id)).mappings().first()
        if row is None:
            return JSONResponse({"error": "unknown scan id"}, status_code=404)
        findings = [
            dict(f)
            for f in conn.execute(
                select(finding_tbl)
                .where(finding_tbl.c.scan_id == scan_id)
                .order_by(finding_tbl.c.file, finding_tbl.c.line, finding_tbl.c.rule_id)
            )
            .mappings()
            .all()
        ]
    return JSONResponse(
        {
            "id": scan_id,
            "status": row["status"],
            "phase": row["phase"],
            "error": row["error"],
            "repo": row["repo_url"],
            "commit_sha": row["commit_sha"],
            "s_version": row["s_version"],
            "env_digest": row["env_digest"],
            "stats": {"files": row["files"], "duration_s": row["duration_s"]},
            "findings": findings,
        }
    )
