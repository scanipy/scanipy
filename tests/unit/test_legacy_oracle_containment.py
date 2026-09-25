"""#396: contained legacy HTTP routes, using DB doubles and no native tools."""

from __future__ import annotations

import asyncio
import concurrent.futures
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType
from typing import NoReturn

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.selectable import Select

pytestmark = pytest.mark.unit
APP_PATH = Path(__file__).resolve().parents[2] / "deploy/scanipy_oracle/app.py"
MESSAGE = "Native scanning is unavailable pending the reviewed capture and worker cutover."
ERROR = {"code": "native_scan_unavailable", "error": MESSAGE, "retryable": False}


def forbidden(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("prohibited native/staging/scan scheduling path reached")


class HostileArgument:
    __str__ = __repr__ = __fspath__ = __iter__ = __len__ = forbidden


@dataclass
class Rows:
    rows: list[dict[str, object]] = field(default_factory=list)
    rowcount: int = 3

    def mappings(self) -> Rows:
        return self

    def first(self) -> dict[str, object] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, object]]:
        return self.rows


@dataclass
class Database:
    """Records real SQLAlchemy statements; never connects to any database."""

    statements: list[object] = field(default_factory=list)
    scans: dict[str, dict[str, object]] = field(default_factory=dict)
    findings: list[dict[str, object]] = field(default_factory=list)
    begins: int = 0
    fail_begin: bool = False
    fail_execute: bool = False

    @contextmanager
    def begin(self) -> Iterator[Database]:
        self.begins += 1
        if self.fail_begin:
            raise RuntimeError("controlled database begin failure")
        yield self

    def execute(self, statement: object) -> Rows:
        self.statements.append(statement)
        if self.fail_execute:
            raise RuntimeError("controlled database execute failure")
        if isinstance(statement, Select):
            params = statement.compile().params
            if statement.get_final_froms()[0].name == "scan":
                row = self.scans.get(params["id_1"])
                return Rows([row] if row is not None else [])
            return Rows(self.findings)
        return Rows()


@pytest.fixture
def subject(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[ModuleType, Database, list[object]]]:
    db = Database()
    create_calls: list[object] = []
    metadata_calls: list[object] = []

    def create_engine(*args: object, **kwargs: object) -> Database:
        create_calls.append((args, kwargs))
        return db

    # Replace the engine factory BEFORE importing the app; no real connection
    # or even real connection pool is constructed by these tests.
    monkeypatch.setattr(sqlalchemy, "create_engine", create_engine)
    monkeypatch.setenv("SCANIPY_DATABASE_URL", "postgresql://unused/unused")
    monkeypatch.setenv("SCANIPY_S_VERSION", "legacy-configured-test-label")
    monkeypatch.setenv("SEMGREP_BIN", "must-not-be-used")
    monkeypatch.setenv("SCANIPY_RULES_DIR", "/must-not-be-read")
    for owner, name in (
        (subprocess, "run"),
        (subprocess, "Popen"),
        (asyncio, "create_subprocess_exec"),
        (asyncio, "create_subprocess_shell"),
        (os, "system"),
        (shutil, "which"),
        (shutil, "rmtree"),
        (tempfile, "mkdtemp"),
        (concurrent.futures, "ThreadPoolExecutor"),
        (uuid, "uuid4"),
        (Path, "read_bytes"),
        (Path, "read_text"),
        (Path, "glob"),
        (Path, "rglob"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    spec = importlib.util.spec_from_file_location("scanipy_legacy_containment_subject", APP_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    assert len(create_calls) == 1
    assert db.begins == 0 and not db.statements
    monkeypatch.setattr(module._meta, "create_all", metadata_calls.append)
    yield module, db, metadata_calls


def test_import_constructs_no_native_or_background_worker(subject: tuple) -> None:
    module, db, metadata_calls = subject
    assert db.begins == 0 and not metadata_calls
    for name in ("_pool", "GIT", "RULES_DIR", "SEMGREP_BIN", "_ENV_DIGEST", "_map_findings"):
        assert not hasattr(module, name)


@pytest.mark.parametrize("helper", ["_compute_env_digest", "_run_semgrep", "_run_scan"])
def test_direct_legacy_helpers_refuse_without_touching_arguments(
    subject: tuple, helper: str
) -> None:
    module, db, _ = subject
    db.fail_begin = True
    args = {
        "_compute_env_digest": (),
        "_run_semgrep": (HostileArgument(),),
        "_run_scan": (HostileArgument(), HostileArgument()),
    }[helper]
    with pytest.raises(module.NativeScanUnavailableError) as error:
        getattr(module, helper)(*args)
    assert str(error.value) == MESSAGE
    assert db.begins == 0


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"{",
        b"null",
        b"[]",
        b"{}",
        b'"not-a-repository"',
        b'{"repo_url":"https://github.com/owner/repository"}',
        b'{"repo_url":"ext::credential-marker"}',
        b'{"repo_url":{"argv":["git","clone"]},"enable_native":true}',
        b'{"repo_url":"<script>secret-marker</script>"}',
        b"\xff\xfe",
        b"x" * 65_536,
    ],
    ids=[
        "absent",
        "malformed",
        "null",
        "array",
        "empty",
        "string",
        "github",
        "ext",
        "switch",
        "html",
        "non-utf8",
        "bounded-large",
    ],
)
def test_http_submission_is_constant_and_has_no_scan_side_effects(
    subject: tuple, body: bytes
) -> None:
    module, db, metadata_calls = subject
    db.fail_begin = True
    # Not entering the TestClient context intentionally isolates request handling
    # from lifespan's separately tested, explicitly allowed legacy DB startup.
    client = TestClient(module.app)
    response = client.post(
        "/api/scan?enable_native=true",
        content=body,
        headers={"Content-Type": "application/json", "X-Enable-Native": "true"},
    )
    assert response.status_code == 503
    assert response.json() == ERROR
    assert response.headers["cache-control"] == "no-store"
    assert "retry-after" not in response.headers
    assert db.begins == 0 and not db.statements and not metadata_calls


def test_asgi_submission_does_not_consume_body(subject: tuple) -> None:
    module, db, _ = subject
    messages: list[dict[str, object]] = []

    async def receive() -> NoReturn:
        raise AssertionError("disabled scan handler must not read the request body")

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/scan",
        "raw_path": b"/api/scan",
        "root_path": "",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    asyncio.run(module.app(scope, receive, send))
    assert messages[0]["status"] == 503
    assert json.loads(messages[1]["body"]) == ERROR
    assert db.begins == 0


def test_health_is_liveness_not_analysis_or_database_readiness(subject: tuple) -> None:
    module, db, _ = subject
    db.fail_begin = True
    response = TestClient(module.app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "env_digest": None,
        "env_digest_status": "not-observed",
        "s_version": "legacy-configured-test-label",
        "s_version_status": "configured-only",
        "capabilities": {"native_scan": "unavailable", "historical_read": "legacy"},
        "unavailable_reason": MESSAGE,
    }
    assert db.begins == 0


def test_lifespan_initializes_and_reaps_once_without_tool_probe(subject: tuple) -> None:
    module, db, metadata_calls = subject
    with TestClient(module.app) as client:
        assert db.begins == 2
        assert metadata_calls == [db]
        assert len(db.statements) == 2
        assert isinstance(db.statements[0], TextClause)
        assert str(db.statements[0]) == "CREATE SCHEMA IF NOT EXISTS oracle"
        reap = db.statements[1].compile()
        assert str(reap) == (
            "UPDATE oracle.scan SET status=:status, phase=:phase, error=:error "
            "WHERE oracle.scan.status = :status_1"
        )
        assert reap.params == {
            "status": "error",
            "phase": "done",
            "error": "interrupted by a restart",
            "status_1": "running",
        }
        assert client.get("/healthz").status_code == 200
        assert client.post("/api/scan").status_code == 503
        assert db.begins == 2
    assert db.begins == 2 and len(db.statements) == 2


@pytest.mark.parametrize("stage", ["begin", "execute", "metadata", "reap"])
def test_lifespan_failure_propagates(
    subject: tuple, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    module, db, _ = subject
    if stage == "begin":
        db.fail_begin = True
    elif stage == "execute":
        db.fail_execute = True
    elif stage == "metadata":

        def bad_metadata(engine: object) -> NoReturn:
            raise RuntimeError("controlled metadata failure")

        monkeypatch.setattr(module._meta, "create_all", bad_metadata)
    else:
        monkeypatch.setattr(module, "_init_db", lambda: None)
        db.fail_execute = True
    with pytest.raises(RuntimeError, match="controlled"):
        with TestClient(module.app):
            pytest.fail("failed startup must not yield a ready application")


def test_historical_get_preserves_fields_and_bound_sql(subject: tuple) -> None:
    module, db, _ = subject
    scan_id = "old' OR '1'='1"
    row = {
        "status": "done",
        "phase": "done",
        "error": None,
        "repo_url": "https://github.com/old/repository",
        "commit_sha": "0" * 40,
        "s_version": "historic-label",
        "env_digest": "historic-partial-digest",
        "files": 0,
        "duration_s": 4.2,
    }
    finding = {
        "id": 7,
        "scan_id": scan_id,
        "origin": "oracle-passthrough",
        "engine": "semgrep",
        "cwe": "CWE-78",
        "rule_id": "old-rule",
        "severity": "critical",
        "title": "old",
        "message": "<script>inert historic text</script>",
        "file": "old.py",
        "line": 8,
        "snippet": "historical source text",
        "snippet_start_line": 6,
        "slice_fingerprint": "1" * 64,
        "fingerprint_class": "weak",
    }
    db.scans[scan_id] = row
    db.findings.append(finding)
    response = TestClient(module.app).get("/api/scan/" + scan_id)
    assert response.status_code == 200
    assert response.json() == {
        "id": scan_id,
        "status": "done",
        "phase": "done",
        "error": None,
        "repo": row["repo_url"],
        "commit_sha": row["commit_sha"],
        "s_version": row["s_version"],
        "env_digest": row["env_digest"],
        "stats": {"files": 0, "duration_s": 4.2},
        "findings": [finding],
    }
    assert db.begins == 1 and len(db.statements) == 2
    first, second = (statement.compile() for statement in db.statements)
    assert first.params == {"id_1": scan_id}
    assert second.params == {"scan_id_1": scan_id}
    assert scan_id not in str(first) and scan_id not in str(second)
    assert str(second).endswith(
        "ORDER BY oracle.finding.file, oracle.finding.line, oracle.finding.rule_id"
    )


def test_historical_missing_scan_stays_404(subject: tuple) -> None:
    module, db, _ = subject
    response = TestClient(module.app).get("/api/scan/missing")
    assert response.status_code == 404 and response.json() == {"error": "unknown scan id"}
    assert len(db.statements) == 1


def test_legacy_table_column_shapes_are_preserved(subject: tuple) -> None:
    module, _, _ = subject
    assert module._meta.schema == "oracle"
    assert list(module._meta.tables) == ["oracle.scan", "oracle.finding"]
    assert list(module.scan_tbl.c.keys()) == [
        "id",
        "repo_url",
        "commit_sha",
        "status",
        "phase",
        "error",
        "s_version",
        "env_digest",
        "files",
        "duration_s",
        "created_at",
    ]
    assert list(module.finding_tbl.c.keys()) == [
        "id",
        "scan_id",
        "origin",
        "engine",
        "cwe",
        "rule_id",
        "severity",
        "title",
        "message",
        "file",
        "line",
        "snippet",
        "snippet_start_line",
        "slice_fingerprint",
        "fingerprint_class",
    ]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def test_static_shell_has_no_submission_or_remote_execution_path(subject: tuple) -> None:
    module, db, _ = subject
    response = TestClient(module.app).get("/")
    assert response.status_code == 200
    assert "New scans are unavailable" in response.text
    assert "Existing stored scans remain available" in response.text
    assert "GET /api/scan/{scan_id}" in response.text
    parser = PageParser()
    parser.feed(response.text)
    assert not {"script", "form", "iframe", "object", "embed", "link", "img"}.intersection(
        tag for tag, _ in parser.tags
    )
    controls = [(tag, attrs) for tag, attrs in parser.tags if tag in {"input", "button"}]
    assert {tag for tag, _ in controls} == {"input", "button"}
    assert all("disabled" in attrs for _, attrs in controls)
    assert all(not key.startswith("on") for _, attrs in parser.tags for key in attrs)
    assert [(tag, attrs["href"]) for tag, attrs in parser.tags if "href" in attrs] == [
        ("a", "/healthz")
    ]
    assert "url(" not in response.text and "@import" not in response.text
    assert db.begins == 0
