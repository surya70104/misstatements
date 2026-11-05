"""The configuration guards (architecture D5, D7, D11, D12).

Every test builds settings through ``make_settings`` (see conftest), which reads neither
backend/.env nor the environment, so the results do not depend on the developer's machine.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from oak_misstatements.config import Settings

APP = "postgresql+psycopg://oak_misstatements_app:x@localhost:5432/oak_misstatements"
TEST_OWNER = "postgresql+psycopg://oak_misstatements_owner:x@localhost:5432/oak_misstatements_test"
TEST_APP = "postgresql+psycopg://oak_misstatements_app:x@localhost:5432/oak_misstatements_test"
MIGRATION = "postgresql+psycopg://oak_misstatements_owner:x@localhost:5432/oak_misstatements"

MakeSettings = Callable[..., Settings]


@pytest.fixture
def dev(make_settings: MakeSettings) -> MakeSettings:
    """Development settings with a valid application URL, overridable per test."""

    def _dev(**overrides: Any) -> Settings:
        values: dict[str, Any] = {"env": "development", "database_url": APP}
        values.update(overrides)
        return make_settings(**values)

    return _dev


def test_own_database_is_accepted(dev: MakeSettings) -> None:
    assert dev().database_url == APP
    assert dev(migration_database_url=MIGRATION).migration_database_url == MIGRATION


def test_missing_database_url_is_refused(make_settings: MakeSettings) -> None:
    with pytest.raises(ValidationError, match="OAK_DATABASE_URL is not set"):
        make_settings(env="development")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://oak_misstatements_app:x@localhost:5432/oak_spine",
        "postgresql+psycopg://oak_misstatements_app:x@localhost:5432/oak_binder",
        "postgresql+psycopg://oak_misstatements_app:x@localhost:5432/oak_binder_test",
        "postgresql+psycopg://oak_misstatements_app:x@localhost:5432/postgres",
    ],
)
def test_other_databases_are_refused(dev: MakeSettings, url: str) -> None:
    with pytest.raises(ValidationError, match="never connects to any other database"):
        dev(database_url=url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://oak_misstatements_owner:x@localhost:5432/oak_spine_test",
        "postgresql+psycopg://oak_misstatements_owner:x@localhost:5432/oak_binder",
    ],
)
def test_migration_to_other_databases_is_refused(dev: MakeSettings, url: str) -> None:
    with pytest.raises(ValidationError, match="never connects to any other database"):
        dev(migration_database_url=url)


def test_other_modules_roles_are_refused(dev: MakeSettings) -> None:
    with pytest.raises(ValidationError, match="must connect as oak_misstatements_app"):
        dev(database_url="postgresql+psycopg://oak_app:x@localhost:5432/oak_misstatements")
    with pytest.raises(ValidationError, match="must connect as oak_misstatements_owner"):
        dev(
            migration_database_url=(
                "postgresql+psycopg://oak_binder_owner:x@localhost:5432/oak_misstatements"
            )
        )
    # The application URL may not connect as the owner: the API never runs with DDL rights.
    with pytest.raises(ValidationError, match="must connect as oak_misstatements_app"):
        dev(database_url=MIGRATION)


def test_hosts_off_the_loopback_interface_are_refused(dev: MakeSettings) -> None:
    with pytest.raises(ValidationError, match="loopback interface"):
        dev(
            database_url="postgresql+psycopg://oak_misstatements_app:x@db.example:5432/oak_misstatements"
        )
    assert dev(
        database_url="postgresql+psycopg://oak_misstatements_app:x@127.0.0.1:5432/oak_misstatements"
    ).database_url.endswith("/oak_misstatements")


def test_test_database_urls_must_name_the_test_database(dev: MakeSettings) -> None:
    assert dev(test_database_url=TEST_OWNER).test_database_url == TEST_OWNER
    assert dev(test_app_database_url=TEST_APP).test_app_database_url == TEST_APP
    with pytest.raises(ValidationError, match="oak_misstatements_test"):
        dev(test_database_url=MIGRATION)
    with pytest.raises(ValidationError, match="oak_misstatements_test"):
        dev(test_app_database_url=APP)
    with pytest.raises(ValidationError, match="must connect as oak_misstatements_owner"):
        dev(test_database_url=TEST_APP)
    with pytest.raises(ValidationError, match="must connect as oak_misstatements_app"):
        dev(test_app_database_url=TEST_OWNER)


def test_driver_host_and_port_are_required(dev: MakeSettings) -> None:
    with pytest.raises(ValidationError, match="postgresql\\+psycopg"):
        dev(database_url="postgresql://oak_misstatements_app:x@localhost:5432/oak_misstatements")
    with pytest.raises(ValidationError, match="host and port"):
        dev(database_url="postgresql+psycopg://oak_misstatements_app:x@localhost/oak_misstatements")
    with pytest.raises(ValidationError, match="not a valid database URL"):
        dev(database_url="not a url")


def test_pm_gate_defaults_to_the_standards_own_test(dev: MakeSettings) -> None:
    assert dev().pm_gate == "soft"
    assert dev(pm_gate="hard").pm_gate == "hard"
    with pytest.raises(ValidationError, match="Input should be 'soft' or 'hard'"):
        dev(pm_gate="warning")


def test_service_urls_are_origins_or_unset(dev: MakeSettings) -> None:
    assert dev().spine_url is None
    assert dev(spine_url=" http://127.0.0.1:8000/ ").spine_url == "http://127.0.0.1:8000"
    assert dev(binder_url="").binder_url is None
    with pytest.raises(ValidationError, match="OAK_WORKMIND_URL must be an http"):
        dev(workmind_url="127.0.0.1:8002")


def test_header_auth_needs_a_header_and_valid_proxies(dev: MakeSettings) -> None:
    assert dev(auth="header", trusted_proxies="10.0.0.5, 10.0.1.0/24").trusted_networks()
    with pytest.raises(ValidationError, match="OAK_AUTH=header needs OAK_AUTH_HEADER"):
        dev(auth="header", auth_header="  ")
    with pytest.raises(ValidationError, match="comma-separated list of IP addresses"):
        dev(trusted_proxies="the proxy")


def test_production_guards(dev: MakeSettings) -> None:
    production = dict(env="production", dev_user=None, auth="header", trusted_proxies="10.0.0.5")
    assert dev(**production).env == "production"
    with pytest.raises(ValidationError, match="OAK_DEV_USER must not be set"):
        dev(**{**production, "dev_user": "dev@localhost"})
    with pytest.raises(ValidationError, match="OAK_AUTH=dev is not allowed"):
        dev(**{**production, "auth": "dev"})
    with pytest.raises(ValidationError, match="OAK_TRUSTED_PROXIES must list"):
        dev(**{**production, "trusted_proxies": ""})
    with pytest.raises(ValidationError, match="OAK_SPINE_URL must use https"):
        dev(**{**production, "spine_url": "http://spine.example:8000"})
    assert dev(**{**production, "spine_url": "http://127.0.0.1:8000"}).spine_url
    with pytest.raises(
        ValidationError, match="must name oak_misstatements when OAK_ENV=production"
    ):
        dev(**{**production, "database_url": TEST_APP})


def test_the_role_claim_needs_both_names_and_header_mode(dev: MakeSettings) -> None:
    """D39: a role claim is believed from an authenticating proxy and from nothing else."""
    assert dev().partner_actions_available() is False
    with pytest.raises(ValidationError, match="go together"):
        dev(auth="header", auth_roles_header="X-Authenticated-Roles")
    with pytest.raises(ValidationError, match="go together"):
        dev(auth="header", partner_role="partner")
    with pytest.raises(ValidationError, match="only when OAK_AUTH=header"):
        dev(auth_roles_header="X-Authenticated-Roles", partner_role="partner")
    with pytest.raises(ValidationError, match="must differ"):
        dev(auth="header", auth_roles_header="x-authenticated-user", partner_role="partner")
    configured = dev(
        auth="header",
        trusted_proxies="10.0.0.5",
        auth_roles_header=" X-Authenticated-Roles ",
        partner_role=" partner ",
    )
    assert configured.partner_actions_available() is True
    unlisted = dev(auth="header", auth_roles_header="X-Authenticated-Roles", partner_role="p")
    assert unlisted.partner_actions_available() is False  # D40: no proxy address listed
    assert (configured.auth_roles_header, configured.partner_role) == (
        "X-Authenticated-Roles",
        "partner",
    )
    blank = dev(auth="header", auth_roles_header="  ", partner_role="")
    assert blank.partner_actions_available() is False


def test_the_strategy_band_has_no_default_and_is_a_fraction(dev: MakeSettings) -> None:
    """Pending decision B5: no band is assumed."""
    assert dev().strategy_trigger_fraction is None
    assert dev(strategy_trigger_fraction="0.75").strategy_trigger_fraction == Decimal("0.75")
    for bad in ("0", "1", "1.5", "-0.1"):
        with pytest.raises(ValidationError):
            dev(strategy_trigger_fraction=bad)
