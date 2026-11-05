"""Settings for the Misstatements Rollup backend.

Values come from the environment and from ``backend/.env`` (see ``.env.example``). Nothing in
this module opens a connection. Three guards live here because they are configuration, not
features: a database URL may only name this module's own databases, on the loopback
interface, as the role the URL is for (architecture D5); production refuses a development
identity (D7); and a service URL must be a plain http or https origin (D11).
"""

from __future__ import annotations

import ipaddress
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

MODULE = "misstatements-rollup"
APP_DATABASE = "oak_misstatements"
TEST_DATABASE = "oak_misstatements_test"
OWNER_ROLE = "oak_misstatements_owner"
APP_ROLE = "oak_misstatements_app"
DRIVER = "postgresql+psycopg"
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def check_database_url(url: str, *, allowed: frozenset[str], role: str, name: str) -> str:
    """Return ``url`` if it uses the psycopg driver, gives host and port explicitly, is on the
    loopback interface, connects as ``role`` and names one of ``allowed``. Raise
    ``ValueError`` otherwise. Nothing is connected to."""
    if not url:
        raise ValueError(f"{name} is not set: copy backend\\.env.example to backend\\.env")
    try:
        parsed = make_url(url)
    except ArgumentError as exc:
        raise ValueError(f"{name} is not a valid database URL") from exc
    if parsed.drivername != DRIVER:
        raise ValueError(f"{name} must start with {DRIVER}://")
    if not parsed.host or parsed.port is None:
        raise ValueError(f"{name} must give the host and port explicitly")
    if parsed.host.lower() not in LOOPBACK_HOSTS:
        raise ValueError(
            f"{name} must be on the loopback interface (localhost), not {parsed.host!r}: "
            "the module never connects to a database elsewhere"
        )
    if parsed.database not in allowed:
        raise ValueError(
            f"{name} must name one of {sorted(allowed)}, not {parsed.database!r}: "
            "the module never connects to any other database"
        )
    if parsed.username != role:
        raise ValueError(
            f"{name} must connect as {role}, not {parsed.username!r} (architecture D5)"
        )
    return url


def service_url_is_secure(url: str) -> bool:
    """https anywhere, or plain http only to the loopback interface (D11)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" or host in LOOPBACK_HOSTS or host.startswith("127.")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OAK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    env: Literal["development", "test", "production"] = "development"
    # Empty by default so Settings() needs no arguments; the validator refuses an empty value.
    database_url: str = ""
    migration_database_url: str | None = None
    test_database_url: str | None = None
    test_app_database_url: str | None = None
    # Who is acting (D7).
    #   dev     the fixed identity in OAK_DEV_USER; development and tests only
    #   header  the identity an authenticating reverse proxy places in OAK_AUTH_HEADER on
    #           every request, after it has signed the user in
    auth: Literal["dev", "header"] = "dev"
    auth_header: str = "X-Authenticated-User"
    # In header mode, the only addresses whose identity header is believed: the proxy's, as
    # a comma-separated list of IPs or networks. Empty means any peer, which production
    # refuses.
    trusted_proxies: str = ""
    dev_user: str | None = None
    # The role claim (D39, B9). In header mode the proxy may also present the signed-in
    # user's roles, comma-separated, in OAK_AUTH_ROLES_HEADER; OAK_PARTNER_ROLE names the
    # value the firm's identity provider gives an engagement partner. Partner-only actions
    # are available only when both are set; otherwise they fail closed. Never read in dev
    # mode: a development identity is never evidence of authorisation (D36).
    auth_roles_header: str | None = None
    partner_role: str | None = None
    # The gate at performance materiality (spec section 7; D12). The gate itself is Stage 5.
    pm_gate: Literal["soft", "hard"] = "soft"
    # The strategy trigger (spec section 7; SA 450 paragraph 6): the fraction of overall
    # materiality at which the aggregate is "approaching materiality". There is no default:
    # what the band should be is pending decision B5, and unset means the trigger is not
    # evaluated and says so.
    strategy_trigger_fraction: Decimal | None = Field(default=None, gt=0, lt=1)
    # Other modules, each reached over HTTP when its URL is set (D1, D11). Unset means not
    # configured: every dependent action says so instead of failing. Credentials are
    # optional bearers, sent when set and never printed.
    spine_url: str | None = None
    spine_credential: str | None = None
    binder_url: str | None = None
    binder_credential: str | None = None
    workmind_url: str | None = None
    workmind_credential: str | None = None

    @field_validator("database_url", "test_app_database_url")
    @classmethod
    def _app_role_url(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field = info.field_name or "database_url"
        allowed = (
            frozenset({TEST_DATABASE})
            if field == "test_app_database_url"
            else frozenset({APP_DATABASE, TEST_DATABASE})
        )
        return check_database_url(
            value, allowed=allowed, role=APP_ROLE, name=f"OAK_{field.upper()}"
        )

    @field_validator("migration_database_url", "test_database_url")
    @classmethod
    def _owner_role_url(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field = info.field_name or "migration_database_url"
        allowed = (
            frozenset({TEST_DATABASE})
            if field == "test_database_url"
            else frozenset({APP_DATABASE, TEST_DATABASE})
        )
        return check_database_url(
            value, allowed=allowed, role=OWNER_ROLE, name=f"OAK_{field.upper()}"
        )

    @field_validator("spine_url", "binder_url", "workmind_url")
    @classmethod
    def _service_url(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None or not value.strip():
            return None
        parsed = urlparse(value.strip())
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            name = f"OAK_{(info.field_name or 'spine_url').upper()}"
            raise ValueError(
                f"{name} must be an http:// or https:// URL with a host, "
                "for example http://127.0.0.1:8000"
            )
        return value.strip().rstrip("/")

    def trusted_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [
            ipaddress.ip_network(part.strip(), strict=False)
            for part in self.trusted_proxies.split(",")
            if part.strip()
        ]

    @model_validator(mode="after")
    def _auth_guard(self) -> Settings:
        # dev mode without OAK_DEV_USER is allowed outside production: the identity
        # dependency answers 503 until it is set.
        if self.auth == "header" and not self.auth_header.strip():
            raise ValueError("OAK_AUTH=header needs OAK_AUTH_HEADER, the header the proxy sets")
        try:
            self.trusted_networks()
        except ValueError as exc:
            raise ValueError(
                "OAK_TRUSTED_PROXIES must be a comma-separated list of IP addresses or networks"
            ) from exc
        roles_header = (self.auth_roles_header or "").strip() or None
        partner_role = (self.partner_role or "").strip() or None
        self.auth_roles_header = roles_header
        self.partner_role = partner_role
        if (roles_header is None) != (partner_role is None):
            raise ValueError(
                "OAK_AUTH_ROLES_HEADER and OAK_PARTNER_ROLE go together: the header the proxy "
                "sets and the value in it that means engagement partner (architecture D39)"
            )
        if roles_header is not None and self.auth != "header":
            raise ValueError(
                "OAK_AUTH_ROLES_HEADER is read only when OAK_AUTH=header: a role claim is "
                "believed from an authenticating proxy and from nothing else (architecture D39)"
            )
        if roles_header is not None and roles_header.lower() == self.auth_header.lower():
            raise ValueError("OAK_AUTH_ROLES_HEADER must differ from OAK_AUTH_HEADER")
        return self

    def partner_actions_available(self) -> bool:
        """True only when the identity source is an authenticating proxy at an explicitly
        listed address and the firm has named the role claim and the partner value (D39,
        D40). A configured header is not enough: without OAK_TRUSTED_PROXIES any client could
        present the claim itself."""
        return (
            self.auth == "header"
            and bool(self.trusted_networks())
            and self.auth_roles_header is not None
            and self.partner_role is not None
        )

    @model_validator(mode="after")
    def _production_guard(self) -> Settings:
        if self.env != "production":
            return self
        if self.dev_user:
            raise ValueError(
                "OAK_DEV_USER must not be set when OAK_ENV=production: "
                "every action needs real authentication (architecture D7)"
            )
        if self.auth == "dev":
            raise ValueError(
                "OAK_AUTH=dev is not allowed when OAK_ENV=production: set OAK_AUTH=header "
                "behind an authenticating proxy (architecture D7)"
            )
        if not self.trusted_networks():
            raise ValueError(
                "OAK_TRUSTED_PROXIES must list the proxy's address(es) when OAK_ENV=production: "
                "otherwise anyone who can reach the API can name themselves (architecture D7)"
            )
        for name, url in (
            ("OAK_SPINE_URL", self.spine_url),
            ("OAK_BINDER_URL", self.binder_url),
            ("OAK_WORKMIND_URL", self.workmind_url),
        ):
            if url and not service_url_is_secure(url):
                raise ValueError(
                    f"{name} must use https:// when OAK_ENV=production unless the service is "
                    "on the loopback interface (architecture D11)"
                )
        if make_url(self.database_url).database != APP_DATABASE:
            raise ValueError(f"OAK_DATABASE_URL must name {APP_DATABASE} when OAK_ENV=production")
        return self


def get_settings() -> Settings:
    """Read settings from the environment and ``backend/.env``."""
    return Settings()
