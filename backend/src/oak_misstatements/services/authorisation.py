"""What the module can and cannot say about who is allowed to act (B9; architecture D36).

What is in place: every write needs an identity, resolved by ``identity.py`` from the
configured source and refused when missing or implausible; the identity is recorded on the
row it creates, taken from the request's identity and never from its body; and every audit
column is frozen at the database. What is **not** in place, and is declared on every answer
so the gap is never mistaken for approval: a general role or permission model. Any identity
may raise, link and set thresholds; the spec defines no roles for those.

The one action the spec reserves to a partner that exists so far, the soft-gate
acknowledgement, **is** enforced (D39): it needs the proxy's role claim to name the acting
identity a partner, and fails closed otherwise. Whether that claim exists is a deployment
fact (OAK_AUTH_ROLES_HEADER, OAK_PARTNER_ROLE) reported in ``partner_actions``; until the
firm wires its identity provider, partner actions are unavailable, never open.
"""

from __future__ import annotations

from typing import Any

from oak_misstatements.config import Settings

POLICY = (
    "pending decision B9: no general role or permission model is enforced; any identity may "
    "raise, link and set thresholds; the acting identity is required on every write, recorded "
    "on the row, and frozen there; partner-only actions are enforced from the proxy's role "
    "claim and fail closed without it (docs/DECISIONS_PENDING.md)"
)
MISSING = (
    "the firm's identity provider presenting a role claim through the authenticating proxy "
    "(OAK_AUTH_ROLES_HEADER) and the firm naming the value that means engagement partner "
    "(OAK_PARTNER_ROLE); and the firm's policy for who may raise, communicate and set "
    "thresholds, which the spec leaves open (spec sections 6.4, 7, 12)"
)
PARTNER_ACTIONS = ("soft_gate_acknowledgement", "conclusion")


def identity_mode(settings: Settings) -> str:
    return settings.auth


def production_grade(settings: Settings) -> bool:
    """True only when the identity comes from an authenticating proxy in production. A
    development identity is never evidence of authorisation (D36)."""
    return settings.env == "production" and settings.auth == "header"


def partner_actions_json(settings: Settings) -> dict[str, Any]:
    available = settings.partner_actions_available()
    return {
        "enforced": True,
        "available": available,
        "actions": list(PARTNER_ACTIONS),
        "source": (
            f"the proxy's role claim in {settings.auth_roles_header}, value "
            f"{settings.partner_role!r}"
            if available
            else None
        ),
        "detail": (
            "a partner-only action succeeds only when the trusted proxy's role claim names the "
            "acting identity a partner"
            if available
            else "unavailable: no trusted role claim is configured, so every partner-only "
            "action fails closed (403) until the firm wires its identity provider (B9, D39)"
        ),
    }


def authorisation_json(settings: Settings) -> dict[str, Any]:
    return {
        "enforced": False,  # the general model (who may raise, link, set thresholds)
        "policy": POLICY,
        "identity_mode": identity_mode(settings),
        "production_grade": production_grade(settings),
        "missing": MISSING,
        "partner_actions": partner_actions_json(settings),
    }
