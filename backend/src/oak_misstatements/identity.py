"""Who is acting (architecture D7).

One mechanism, two sources, chosen by OAK_AUTH:

- ``dev``: the fixed identity in OAK_DEV_USER. For development and tests; refused in
  production by the settings guard.
- ``header``: the identity an authenticating reverse proxy places in the configured header
  after signing the user in. The module trusts the header and verifies nothing about the
  person itself. It does check that the request reached the API from a trusted proxy address
  (OAK_TRUSTED_PROXIES; required in production), that the header appears exactly once, and
  that the value is a plausible name: non-blank, bounded, printable.

Every action that records a person depends on ``current_user``, so without an identity those
actions refuse rather than record an empty name.

Partner-only actions (D39) depend on ``current_partner``: the proxy's role claim in
OAK_AUTH_ROLES_HEADER, believed under the same conditions as the identity header, must name
the value OAK_PARTNER_ROLE. Without that configuration, in dev mode, or when the claim is
missing, duplicated or does not name a partner, the action answers 403 and nothing is
written. No role is ever read from a request body, inferred from a name, or taken from a
development setting.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from oak_misstatements.config import Settings

MAX_IDENTITY_LENGTH = 254


def plausible(value: str) -> bool:
    """A name a person or identity provider would present: printable, bounded."""
    if not 0 < len(value) <= MAX_IDENTITY_LENGTH:
        return False
    return all(ch == " " or (not ch.isspace() and ord(ch) >= 32 and ord(ch) != 127) for ch in value)


def from_trusted_proxy(settings: Settings, client_host: str | None) -> bool:
    """True when no proxy list is configured (development) or the immediate client address
    is in it. The address is the socket peer, never a forwarded header."""
    networks = settings.trusted_networks()
    if not networks:
        return True
    if not client_host:
        return False
    try:
        address = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    return any(address in network for network in networks)


@dataclass(frozen=True)
class Resolution:
    user: str | None
    status_code: int
    detail: str


def resolve(settings: Settings, headers: list[str], client_host: str | None) -> Resolution:
    """The identity for a request, or why there is none and which status says so.
    ``headers`` holds every value of the configured identity header, in order."""
    if settings.auth == "header":
        name = settings.auth_header
        if not from_trusted_proxy(settings, client_host):
            return Resolution(
                None,
                status.HTTP_401_UNAUTHORIZED,
                "Request did not arrive through a trusted proxy, so its identity header "
                "cannot be believed (OAK_TRUSTED_PROXIES; architecture D7).",
            )
        if len(headers) > 1:
            return Resolution(
                None,
                status.HTTP_401_UNAUTHORIZED,
                f"{name} was presented {len(headers)} times; the proxy must replace, not "
                "append, the header (architecture D7).",
            )
        value = headers[0].strip() if headers else ""
        if not value:
            return Resolution(
                None,
                status.HTTP_401_UNAUTHORIZED,
                f"No authenticated identity: the proxy did not present {name} (architecture D7).",
            )
        if not plausible(value):
            return Resolution(
                None,
                status.HTTP_401_UNAUTHORIZED,
                f"{name} does not hold a usable identity (blank, too long or not printable).",
            )
        return Resolution(value, status.HTTP_200_OK, "")
    user = (settings.dev_user or "").strip() or None
    if user:
        return Resolution(user, status.HTTP_200_OK, "")
    return Resolution(
        None,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "No identity is configured: set OAK_DEV_USER for development, "
        "or OAK_AUTH=header behind an authenticating proxy (architecture D7).",
    )


def resolve_request(request: Request) -> Resolution:
    settings: Settings = request.app.state.settings
    client_host = request.client.host if request.client else None
    return resolve(settings, request.headers.getlist(settings.auth_header), client_host)


def current_user(request: Request) -> str:
    """FastAPI dependency: the acting identity, or an error that says why there is none."""
    found = resolve_request(request)
    if found.user is None:
        raise HTTPException(found.status_code, found.detail)
    return found.user


UNAVAILABLE = (
    "partner authorisation is unavailable: no trusted role claim is configured. It needs "
    "OAK_AUTH=header behind an authenticating proxy whose address is listed in "
    "OAK_TRUSTED_PROXIES, that proxy presenting the signed-in user's roles in "
    "OAK_AUTH_ROLES_HEADER (replacing any value a client sent), and OAK_PARTNER_ROLE naming "
    "the identity provider's value for an engagement partner (pending decision B9; "
    "architecture D39, D40). Nothing was written."
)


def parse_roles(value: str) -> frozenset[str]:
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def resolve_partner(
    settings: Settings, user: str, role_headers: list[str], client_host: str | None
) -> Resolution:
    """Whether ``user``, already authenticated, holds the partner role. ``role_headers``
    holds every value of the configured roles header; ``client_host`` is the socket peer.
    Fails closed at every step, and checks the peer itself even though the identity check
    already did: a role claim is believed from a listed proxy address and from nowhere else."""
    if not settings.partner_actions_available():
        return Resolution(None, status.HTTP_403_FORBIDDEN, UNAVAILABLE)
    if not settings.trusted_networks() or not from_trusted_proxy(settings, client_host):
        return Resolution(
            None,
            status.HTTP_403_FORBIDDEN,
            "the role claim did not arrive from a listed proxy address (OAK_TRUSTED_PROXIES), "
            "so it cannot be believed. Nothing was written (architecture D40).",
        )
    name = settings.auth_roles_header
    if len(role_headers) > 1:
        return Resolution(
            None,
            status.HTTP_403_FORBIDDEN,
            f"{name} was presented {len(role_headers)} times; the proxy must replace, not "
            "append, the header. Nothing was written (architecture D39).",
        )
    if not role_headers or not role_headers[0].strip():
        return Resolution(
            None,
            status.HTTP_403_FORBIDDEN,
            f"the proxy presented no role claim in {name} for {user!r}, so partner "
            "authorisation cannot be verified. Nothing was written (architecture D39).",
        )
    if not plausible(role_headers[0]):
        return Resolution(
            None,
            status.HTTP_403_FORBIDDEN,
            f"{name} does not hold a usable role claim. Nothing was written (architecture D39).",
        )
    roles = parse_roles(role_headers[0])
    if settings.partner_role not in roles:
        return Resolution(
            None,
            status.HTTP_403_FORBIDDEN,
            f"{user!r} does not hold the partner role {settings.partner_role!r} according to "
            "the identity provider; this action is reserved to a partner (spec section 7). "
            "Nothing was written (architecture D39).",
        )
    return Resolution(user, status.HTTP_200_OK, "")


def current_partner(request: Request) -> str:
    """FastAPI dependency for partner-only actions: the acting identity, proven a partner by
    the proxy's role claim, or 401/403 saying why not."""
    user = current_user(request)
    settings: Settings = request.app.state.settings
    role_headers = (
        request.headers.getlist(settings.auth_roles_header) if settings.auth_roles_header else []
    )
    client_host = request.client.host if request.client else None
    found = resolve_partner(settings, user, role_headers, client_host)
    if found.user is None:
        raise HTTPException(found.status_code, found.detail)
    return found.user
