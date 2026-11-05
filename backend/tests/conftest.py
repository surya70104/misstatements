"""Shared fixtures.

Tests never read backend/.env or the OAK_* environment variables for settings:
``IsolatedSettings`` keeps only the values a test passes in, so a developer's real
configuration cannot leak into a test.

Database tests (marked ``db``) are the exception: they need OAK_TEST_DATABASE_URL, and
optionally OAK_TEST_APP_DATABASE_URL. ``TestDatabaseUrls`` reads those two names, and only
those, from the shell environment first and then from backend/.env. Both must name
oak_misstatements_test on localhost as the right role, checked by the same guard the
application uses. Without them the tests are skipped, never silently passed.

The ``api`` fixture runs the whole API against oak_misstatements_test when it is configured,
inside one transaction that is rolled back. When it is not (pending decision O2), it falls
back to SQLite in memory built from the models (architecture D24): that proves the service
and API logic, not the PostgreSQL rules, and the fixture says which it is using.
"""

from __future__ import annotations

import io
import warnings
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from sqlalchemy import Connection, create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from oak_misstatements.config import (
    APP_ROLE,
    OWNER_ROLE,
    TEST_DATABASE,
    Settings,
    check_database_url,
)
from oak_misstatements.db import Base, make_engine
from oak_misstatements.main import create_app
from tests.fake_spine import FakeSpine

APP_URL = "postgresql+psycopg://oak_misstatements_app:placeholder@localhost:5432/oak_misstatements"
MIGRATION_URL = (
    "postgresql+psycopg://oak_misstatements_owner:placeholder@localhost:5432/oak_misstatements_test"
)
RAISER = "senior@firm"

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


class IsolatedSettings(Settings):
    """Settings whose only source is the constructor: no .env, no environment variables."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


class TestDatabaseUrls(BaseSettings):
    """The two test connection strings. Environment variables win over backend/.env, as in
    pydantic-settings generally. Nothing else from .env is read here."""

    __test__ = False  # not a test class, despite the name

    model_config = SettingsConfigDict(
        env_prefix="OAK_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    test_database_url: str | None = None
    test_app_database_url: str | None = None


def test_url(variable: str) -> str | None:
    """The validated URL for OAK_TEST_DATABASE_URL or OAK_TEST_APP_DATABASE_URL, or None."""
    field = variable.removeprefix("OAK_").lower()
    url = getattr(TestDatabaseUrls(), field)
    if not url:
        return None
    role = APP_ROLE if field == "test_app_database_url" else OWNER_ROLE
    return check_database_url(url, allowed=frozenset({TEST_DATABASE}), role=role, name=variable)


def alembic_config(url: str, *, output: io.StringIO | None = None) -> Config:
    """Alembic configuration driven from code: the URL goes through env.py's guard."""
    cfg = Config(str(ALEMBIC_INI), output_buffer=output)
    cfg.attributes["migration_url"] = url
    cfg.attributes["skip_logging_config"] = True
    return cfg


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if test_url("OAK_TEST_DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="OAK_TEST_DATABASE_URL is not set; database tests skipped")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    """Build Settings from explicit values only. Validation runs exactly as in production."""

    def _make(**values: Any) -> Settings:
        return IsolatedSettings(**values)

    return _make


@pytest.fixture
def settings(make_settings: Callable[..., Settings]) -> Settings:
    return make_settings(
        env="test",
        database_url=APP_URL,
        migration_database_url=MIGRATION_URL,
        dev_user="test@localhost",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


# --- database fixtures: only when OAK_TEST_DATABASE_URL is set -------------------------------


def _url_from_env(variable: str) -> str:
    url = test_url(variable)
    if not url:
        pytest.skip(f"{variable} is not set; database tests skipped")
    return url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Owner connection to oak_misstatements_test: migrates and inserts."""
    return _url_from_env("OAK_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def migrated_database(test_database_url: str) -> str:
    """oak_misstatements_test at migration head. Only ``upgrade head`` runs, which applies
    any migration not yet applied and is otherwise a no-op; nothing is dropped."""
    command.upgrade(alembic_config(test_database_url), "head")
    return test_database_url


def _rolled_back_connection(url: str) -> Iterator[Connection]:
    engine = make_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def db(migrated_database: str) -> Iterator[Connection]:
    """Owner connection inside a transaction that is rolled back after the test."""
    yield from _rolled_back_connection(migrated_database)


@pytest.fixture
def app_db(migrated_database: str) -> Iterator[Connection]:
    """Application-role connection (oak_misstatements_app), rolled back after the test."""
    yield from _rolled_back_connection(_url_from_env("OAK_TEST_APP_DATABASE_URL"))


# --- the whole API --------------------------------------------------------------------------


@pytest.fixture
def api(make_settings: Callable[..., Settings]) -> Iterator[TestClient]:
    """The API with no Spine configured; ``use_spine`` gives it the double.

    Against oak_misstatements_test when OAK_TEST_DATABASE_URL is set: every request's session
    is bound to one connection inside one transaction; commits become savepoint releases and
    the transaction is rolled back after the test. Otherwise against SQLite in memory, built
    from the models (D24): logic only, no PostgreSQL rules.
    """
    settings = make_settings(env="test", database_url=APP_URL, dev_user=RAISER)
    app = create_app(settings)
    app.state.engine.dispose()
    owner_url = test_url("OAK_TEST_DATABASE_URL")
    if owner_url:
        command.upgrade(alembic_config(owner_url), "head")
        url = test_url("OAK_TEST_APP_DATABASE_URL") or owner_url
        engine = make_engine(url)
        with engine.connect() as connection:
            transaction = connection.begin()
            app.state.session_factory = sessionmaker(
                bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
            )
            app.state.backing_store = "postgresql"
            try:
                with TestClient(app) as test_client:
                    yield test_client
            finally:
                transaction.rollback()
        engine.dispose()
        return
    engine = create_engine(
        "sqlite+pysqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # SQLite has no Decimal; the stand-in is logic only
        Base.metadata.create_all(engine)
    app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.state.backing_store = "sqlite"
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def act_as(api: TestClient, user: str | None) -> None:
    """Change the development identity the API records as the acting person."""
    cast(FastAPI, api.app).state.settings.dev_user = user


def use_spine(api: TestClient, spine: FakeSpine | None = None) -> FakeSpine:
    """Give the running app a Financial Spine double (D11)."""
    double = spine or FakeSpine()
    cast(FastAPI, api.app).state.spine_client = double.client()
    return double
