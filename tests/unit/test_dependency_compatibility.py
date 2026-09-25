"""Fresh-install HTTP/DB compatibility; no live database is contacted."""

import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("extra", "name"),
    [
        ("dev", "pytest"),
        ("dev", "sqlalchemy"),
        ("http", "anyio"),
        ("oracle", "anyio"),
        ("oracle", "sqlalchemy"),
    ],
)
def test_installed_dependencies_satisfy_declared_compatibility(extra, name):
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = [
        Requirement(value) for value in project["project"]["optional-dependencies"][extra]
    ]
    constraint = next(item for item in requirements if item.name == name)
    assert constraint.specifier.contains(version(name))


def test_http_client_works_with_warnings_as_errors():
    async def health(request):
        return PlainTextResponse("ready")

    # No warning filter: importing and using the pinned stack must remain clean
    # under the repository-wide warnings-as-errors setting.
    application = Starlette(routes=[Route("/health", health)])
    with TestClient(application) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.text == "ready"


def test_bare_postgresql_url_uses_the_declared_psycopg2_driver():
    url = URL.create("postgresql", username="test", host="localhost", database="not_opened")
    engine = create_engine(url)
    try:
        assert engine.dialect.driver == "psycopg2"
        assert engine.dialect.dbapi.__name__ == "psycopg2"
    finally:
        engine.dispose()
