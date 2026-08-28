"""FastAPI oracle-scan service for the one-command Docker deployment (DOCKER-01).

Launch: ``uvicorn deploy.scanipy_oracle.app:app`` (the entrypoint does this after
running Alembic migrations against the same Postgres). NO AWS: detection is the
Semgrep binary baked into the image; persistence is the compose Postgres.

Routes:
  GET  /                     → the scan UI (static/index.html)
  GET  /healthz              → liveness
  POST /api/scan {repo_url}  → start an oracle scan, returns {id}
  GET  /api/scan/{id}        → status + findings (polled by the UI)

Honesty contract: every finding is ``origin = oracle-passthrough`` (engine
``semgrep``), ``fingerprint_class = weak`` (a same-source content id, never a
canonical-CPG claim). Results live in the ``oracle`` schema, kept separate from
the tenanted deterministic-core ``findings`` table (which the staged CPG pipeline
owns).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
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
    insert,
    select,
    text,
    update,
)

# ---------------------------------------------------------------------------
# Configuration (all env-driven; safe defaults for docker-compose)
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
RULES_DIR = Path(os.environ.get("SCANIPY_RULES_DIR", "/app/deploy/rules"))
SEMGREP_BIN = os.environ.get("SEMGREP_BIN", "semgrep")
DATABASE_URL = os.environ.get(
    "SCANIPY_DATABASE_URL", "postgresql://scanipy:scanipy_dev@localhost:5432/scanipy_dev"
)
S_VERSION = os.environ.get("SCANIPY_S_VERSION", "oracle-2026.08")

GITHUB_URL_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
CLONE_TIMEOUT_S = 120
SCAN_TIMEOUT_S = 600
# Semgrep severity → display band (ERROR/WARNING/INFO).
_SEV_BAND = {"ERROR": "critical", "WARNING": "high", "INFO": "medium"}

_engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
_meta = MetaData(schema="oracle")
_pool = ThreadPoolExecutor(max_workers=4)

scan_tbl = Table(
    "scan", _meta,
    Column("id", String(36), primary_key=True),
    Column("repo_url", Text, nullable=False),
    Column("commit_sha", String(40)),
    Column("status", String(16), nullable=False),   # running | done | error
    Column("phase", String(16), nullable=False),    # queued | cloning | detecting | done
    Column("error", Text),
    Column("s_version", Text, nullable=False),
    Column("env_digest", Text, nullable=False),
    Column("files", Integer),
    Column("duration_s", Float),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
finding_tbl = Table(
    "finding", _meta,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("scan_id", String(36), nullable=False, index=True),
    Column("origin", String(32), nullable=False),        # always oracle-passthrough
    Column("engine", String(32), nullable=False),        # semgrep
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

_ENV_DIGEST = "sha256:" + "0" * 64  # replaced at startup with a real analysis-env digest


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _compute_env_digest() -> str:
    """A real, reproducible digest of the analysis environment: the Semgrep
    version + the ruleset content. This is the honest env_digest for the oracle
    path (INV-2) — the identity that a re-run must match to be comparable."""
    try:
        ver = subprocess.run(
            [SEMGREP_BIN, "--version"], capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - best-effort; digest still deterministic
        ver = "unknown"
    h = hashlib.sha256()
    h.update(f"semgrep={ver}\n".encode())
    for p in sorted(RULES_DIR.glob("*.y*ml")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return "sha256:" + h.hexdigest()


def _init_db() -> None:
    with _engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS oracle"))
    _meta.create_all(_engine)


def _snippet(path: Path, line: int, context: int = 2):
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return None, None
    start = max(1, line - context)
    end = min(len(lines), line + context)
    return "\n".join(lines[start - 1:end]), start


def _run_semgrep(src: Path) -> dict:
    proc = subprocess.run(
        [
            SEMGREP_BIN, "scan", "--config", str(RULES_DIR),
            "--json", "--quiet", "--no-git-ignore",
            "--metrics=off", "--disable-version-check", str(src),
        ],
        capture_output=True, timeout=SCAN_TIMEOUT_S,
        env={**os.environ, "SEMGREP_SEND_METRICS": "off"},
    )
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise RuntimeError(
            "semgrep produced no parseable output: "
            + proc.stderr.decode(errors="replace")[-1000:]
        ) from exc


def _map_findings(data: dict, src: Path, commit_sha: str) -> list[dict]:
    out: list[dict] = []
    for r in data.get("results", []):
        rel = r["path"]
        rel = rel[len(str(src)) + 1:] if rel.startswith(str(src)) else Path(rel).name
        meta = r["extra"].get("metadata", {})
        line = r["start"]["line"]
        snip, snip_start = _snippet(src / rel, line)
        title = meta.get("title") or r["check_id"].split(".")[-1].replace("-", " ").title()
        # weak same-source fingerprint: a stable id for this finding, NOT a
        # canonical-CPG claim (fingerprint_class = weak makes that explicit).
        fp = hashlib.sha256(
            f"{commit_sha}|{r['check_id']}|{rel}|{line}".encode()
        ).hexdigest()
        out.append({
            "origin": "oracle-passthrough",
            "engine": "semgrep",
            "cwe": meta.get("cwe", ""),
            "rule_id": r["check_id"],
            "severity": _SEV_BAND.get(r["extra"].get("severity", "WARNING"), "high"),
            "title": title,
            "message": (r["extra"].get("message") or "").strip(),
            "file": rel,
            "line": line,
            "snippet": snip,
            "snippet_start_line": snip_start,
            "slice_fingerprint": fp,
            "fingerprint_class": "weak",
        })
    out.sort(key=lambda f: (f["file"], f["line"], f["rule_id"]))
    return out


def _set_scan(scan_id: str, **kv) -> None:
    with _engine.begin() as conn:
        conn.execute(update(scan_tbl).where(scan_tbl.c.id == scan_id).values(**kv))


def _run_scan(scan_id: str, repo_url: str) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="scanipy-oracle-"))
    src = workdir / "src"
    started = _now()
    try:
        _set_scan(scan_id, phase="cloning")
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(src)],
            check=True, capture_output=True, timeout=CLONE_TIMEOUT_S,
        )
        commit_sha = subprocess.run(
            ["git", "-C", str(src), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip() or ("0" * 40)
        shutil.rmtree(src / ".git", ignore_errors=True)
        py_files = sum(1 for _ in src.rglob("*.py"))

        _set_scan(scan_id, phase="detecting", commit_sha=commit_sha)
        findings = _map_findings(_run_semgrep(src), src, commit_sha)

        with _engine.begin() as conn:
            if findings:
                conn.execute(
                    insert(finding_tbl),
                    [{"scan_id": scan_id, **f} for f in findings],
                )
            conn.execute(
                update(scan_tbl).where(scan_tbl.c.id == scan_id).values(
                    status="done", phase="done", files=py_files,
                    duration_s=round((_now() - started).total_seconds(), 1),
                )
            )
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode(errors="replace")[-400:]
        _set_scan(scan_id, status="error", phase="done", error=f"clone failed: {err}")
    except subprocess.TimeoutExpired:
        _set_scan(scan_id, status="error", phase="done", error="analysis timed out")
    except Exception as exc:  # noqa: BLE001 - surface, never crash the worker thread
        _set_scan(scan_id, status="error", phase="done", error=str(exc)[:1200])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------
app = FastAPI(title="Scanipy — self-host oracle scan (DOCKER-01)")


class ScanRequest(BaseModel):
    repo_url: str


@app.on_event("startup")
def _startup() -> None:
    global _ENV_DIGEST
    _init_db()
    _ENV_DIGEST = _compute_env_digest()


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "env_digest": _ENV_DIGEST, "s_version": S_VERSION}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.post("/api/scan")
def post_scan(req: ScanRequest) -> JSONResponse:
    url = req.repo_url.strip().rstrip("/")
    if not GITHUB_URL_RE.match(url):
        return JSONResponse(
            {"error": "expected a public GitHub repo URL like https://github.com/owner/repo"},
            status_code=400,
        )
    scan_id = str(uuid.uuid4())
    with _engine.begin() as conn:
        conn.execute(insert(scan_tbl).values(
            id=scan_id, repo_url=url, status="running", phase="queued",
            s_version=S_VERSION, env_digest=_ENV_DIGEST, created_at=_now(),
        ))
    _pool.submit(_run_scan, scan_id, url)
    return JSONResponse({"id": scan_id}, status_code=202)


@app.get("/api/scan/{scan_id}")
def get_scan(scan_id: str) -> JSONResponse:
    with _engine.begin() as conn:
        row = conn.execute(select(scan_tbl).where(scan_tbl.c.id == scan_id)).mappings().first()
        if row is None:
            return JSONResponse({"error": "unknown scan id"}, status_code=404)
        findings = [
            dict(f) for f in conn.execute(
                select(finding_tbl).where(finding_tbl.c.scan_id == scan_id)
                .order_by(finding_tbl.c.file, finding_tbl.c.line, finding_tbl.c.rule_id)
            ).mappings().all()
        ]
    return JSONResponse({
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
    })
