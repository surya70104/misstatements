"""The Financial Spine over HTTP (architecture D1, D11).

Reads: an engagement, a version, a version's ledgers with their heads (from the chain),
its adjustments with their lines, and the Schedule III tree with each head's nature. Writes:
propose an adjustment, and decide one, once, as accepted or refused (Stage 3, D41). Nothing
else is sent; the test double records every call and the
tests assert no other verb or path is ever used. The module never imports Spine code or
reads its database.

Errors are mapped once: transport faults, timeouts, 429 and 5xx become ``ServiceUnavailable``
(503); 404 becomes ``NotFound`` with the Spine's message; 401 and 403 say the credential was
refused; 409 becomes ``Conflict`` (a locked version, a second decision); other 4xx become
``Invalid``; a non-JSON body is "an unexpected answer".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx

from oak_misstatements.config import Settings
from oak_misstatements.core.effects import Section
from oak_misstatements.errors import Conflict, Invalid, NotFound, ServiceUnavailable

Nature = Literal["BS", "PL"]
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0


@dataclass(frozen=True)
class SpineVersion:
    version_id: uuid.UUID
    engagement_id: uuid.UUID
    version_no: int
    label: str
    is_locked: bool
    performance_materiality: Decimal | None
    pm_source: str | None
    hash: str | None
    supersedes_id: uuid.UUID | None


@dataclass(frozen=True)
class SpineLedger:
    """One ledger of a version's chain: identity and the head the client's map gives it."""

    line_no: int
    ledger_key: str
    ledger_name: str
    parent_chain: tuple[str, ...]
    head_id: str | None
    nature: Nature | None


@dataclass(frozen=True)
class SpineAdjustmentLine:
    line_no: int
    ledger_key: str
    ledger_name: str
    parent_chain: tuple[str, ...]
    head_id: str | None  # only for a ledger the import lacks; the map decides the rest
    in_import: bool
    dr: Decimal
    cr: Decimal


@dataclass(frozen=True)
class SpineAdjustment:
    adjustment_id: uuid.UUID
    version_id: uuid.UUID
    kind: str
    status: str
    narration: str
    working_paper_ref: str
    finding_ref: str | None
    proposed_by: str
    proposed_at: datetime | None
    decided_by: str | None
    decided_at: datetime | None
    decision_note: str | None
    lines: tuple[SpineAdjustmentLine, ...]


@dataclass(frozen=True)
class SpineHead:
    """One head of the Spine's Schedule III tree, with the metadata ``api/schedule3.py``
    serves: its parent, statement, nature, expected side and face item reference."""

    id: str
    label: str
    parent: str | None
    nature: Nature | None
    mappable: bool
    statement: str | None = None
    side: str | None = None
    item: str | None = None


# Schedule III Division I face items as the Spine's tree carries them (architecture D31).
# The item reference is the stable key; the dotted ids are the fallback when a chain has none.
EQUITY_ITEMS = frozenset({"I(1)"})
SHARE_APPLICATION_ITEMS = frozenset({"I(2)"})  # neither equity nor liability in the tree
LIABILITY_ITEMS = frozenset({"I(3)", "I(4)"})
ASSET_ITEMS = frozenset({"II"})
AFTER_PBT_ITEMS = frozenset({"X", "XI", "XII", "XIII", "XIV", "XV", "XII-XIII"})


@dataclass(frozen=True)
class SpineTree:
    division: str | None
    version: str | None
    heads: dict[str, SpineHead]

    def chain(self, head_id: str) -> list[SpineHead]:
        """The head and its ancestors, nearest first; stops at an unknown parent or a cycle."""
        found: list[SpineHead] = []
        seen: set[str] = set()
        current: str | None = head_id
        while current is not None and current in self.heads and current not in seen:
            seen.add(current)
            head = self.heads[current]
            found.append(head)
            current = head.parent
        return found

    def section(self, head_id: str | None) -> Section:
        """Which part of the Schedule III format a head belongs to (D31). Nothing is guessed:
        a head the tree does not know, or share application money pending allotment, is
        ``unresolved``."""
        if head_id is None or head_id not in self.heads:
            return "unresolved"
        for head in self.chain(head_id):
            item = head.item
            if item in AFTER_PBT_ITEMS:
                return "pl_after_tax"
            if item in EQUITY_ITEMS:
                return "equity"
            if item in SHARE_APPLICATION_ITEMS:
                return "unresolved"
            if item in LIABILITY_ITEMS:
                return "liabilities"
            if item in ASSET_ITEMS:
                return "assets"
        if head_id.startswith("bs.assets"):
            return "assets"
        if head_id.startswith("bs.liabilities.shareholders_funds"):
            return "equity"
        if head_id.startswith("bs.liabilities.share_application_money"):
            return "unresolved"
        if head_id.startswith("bs.liabilities"):
            return "liabilities"
        if head_id.startswith(("pl.tax_expense", "pl.discontinuing_operations")):
            return "pl_after_tax"
        if head_id == "pl" or head_id.startswith("pl."):
            return "pl_before_tax"
        return "unresolved"


def _unexpected(what: str) -> ServiceUnavailable:
    return ServiceUnavailable(f"the Financial Spine gave an unexpected answer for {what}")


def _uuid(value: Any, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise _unexpected(what) from exc


def _optional_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _amount(value: Any, what: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise _unexpected(what) from exc


def _optional_amount(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _nature(value: Any) -> Nature | None:
    return value if value in ("BS", "PL") else None


def _chain(value: Any) -> tuple[str, ...]:
    return tuple(str(part) for part in value) if isinstance(value, list) else ()


def parse_version(raw: Any) -> SpineVersion:
    if not isinstance(raw, dict):
        raise _unexpected("a version")
    return SpineVersion(
        version_id=_uuid(raw.get("version_id"), "a version"),
        engagement_id=_uuid(raw.get("engagement_id"), "a version"),
        version_no=int(raw.get("version_no") or 0),
        label=str(raw.get("label") or ""),
        is_locked=bool(raw.get("is_locked", False)),
        performance_materiality=_optional_amount(raw.get("performance_materiality")),
        pm_source=raw.get("pm_source") if isinstance(raw.get("pm_source"), str) else None,
        hash=raw.get("hash") if isinstance(raw.get("hash"), str) else None,
        supersedes_id=_optional_uuid(raw.get("supersedes_id")),
    )


def parse_ledgers(raw: Any) -> list[SpineLedger]:
    if not isinstance(raw, dict) or not isinstance(raw.get("ledgers"), list):
        raise _unexpected("the balances")
    ledgers: list[SpineLedger] = []
    for entry in raw["ledgers"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("line_no"), int):
            raise _unexpected("the balances")
        ledgers.append(
            SpineLedger(
                line_no=entry["line_no"],
                ledger_key=str(entry.get("ledger_key") or ""),
                ledger_name=str(entry.get("ledger_name") or ""),
                parent_chain=_chain(entry.get("parent_chain")),
                head_id=entry.get("head_id") if isinstance(entry.get("head_id"), str) else None,
                nature=_nature(entry.get("nature")),
            )
        )
    return ledgers


def parse_adjustment(raw: Any) -> SpineAdjustment:
    if not isinstance(raw, dict) or not isinstance(raw.get("lines"), list):
        raise _unexpected("an adjustment")
    lines: list[SpineAdjustmentLine] = []
    for entry in raw["lines"]:
        if not isinstance(entry, dict):
            raise _unexpected("an adjustment")
        lines.append(
            SpineAdjustmentLine(
                line_no=int(entry.get("line_no") or 0),
                ledger_key=str(entry.get("ledger_key") or ""),
                ledger_name=str(entry.get("ledger_name") or ""),
                parent_chain=_chain(entry.get("parent_chain")),
                head_id=entry.get("head_id") if isinstance(entry.get("head_id"), str) else None,
                in_import=bool(entry.get("in_import", False)),
                dr=_amount(entry.get("dr", "0"), "an adjustment"),
                cr=_amount(entry.get("cr", "0"), "an adjustment"),
            )
        )
    return SpineAdjustment(
        adjustment_id=_uuid(raw.get("adjustment_id"), "an adjustment"),
        version_id=_uuid(raw.get("version_id"), "an adjustment"),
        kind=str(raw.get("kind") or ""),
        status=str(raw.get("status") or ""),
        narration=str(raw.get("narration") or ""),
        working_paper_ref=str(raw.get("working_paper_ref") or ""),
        finding_ref=raw.get("finding_ref") if isinstance(raw.get("finding_ref"), str) else None,
        proposed_by=str(raw.get("proposed_by") or ""),
        proposed_at=_time(raw.get("proposed_at")),
        decided_by=raw.get("decided_by") if isinstance(raw.get("decided_by"), str) else None,
        decided_at=_time(raw.get("decided_at")),
        decision_note=(
            raw.get("decision_note") if isinstance(raw.get("decision_note"), str) else None
        ),
        lines=tuple(lines),
    )


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def parse_tree(raw: Any) -> SpineTree:
    if not isinstance(raw, dict) or not isinstance(raw.get("heads"), list):
        raise _unexpected("the Schedule III tree")
    heads: dict[str, SpineHead] = {}
    for entry in raw["heads"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            raise _unexpected("the Schedule III tree")
        heads[entry["id"]] = SpineHead(
            id=entry["id"],
            label=str(entry.get("label") or entry["id"]),
            parent=_optional_text(entry.get("parent")),
            nature=_nature(entry.get("nature")),
            mappable=bool(entry.get("mappable", False)),
            statement=_optional_text(entry.get("statement")),
            side=_optional_text(entry.get("side")),
            item=_optional_text(entry.get("item")),
        )
    version = raw.get("version")
    return SpineTree(
        division=_optional_text(raw.get("division")),
        version=None if version is None else str(version),
        heads=heads,
    )


def _message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"the Financial Spine answered {response.status_code}"
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return str(detail["message"])
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = [
            str(item.get("msg")) for item in detail if isinstance(item, dict) and "msg" in item
        ]
        if parts:
            return "; ".join(parts)
    return f"the Financial Spine answered {response.status_code}"


class SpineClient:
    def __init__(self, base_url: str, http: httpx.Client, credential: str | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._http = http
        self._credential = credential

    def __repr__(self) -> str:
        return f"SpineClient({self._base!r})"  # never the credential

    def _request(self, method: str, path: str, *, what: str, json: Any = None) -> Any:
        headers = {"Accept": "application/json"}
        if self._credential:
            headers["Authorization"] = f"Bearer {self._credential}"
        try:
            response = self._http.request(method, f"{self._base}{path}", headers=headers, json=json)
        except httpx.TimeoutException as exc:
            raise ServiceUnavailable(
                f"the Financial Spine did not answer in time for {what}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ServiceUnavailable(f"the Financial Spine cannot be reached for {what}") from exc
        if response.status_code == 404:
            raise NotFound(_message(response))
        if response.status_code in (401, 403):
            raise ServiceUnavailable("the Financial Spine refused the configured credential")
        if response.status_code == 409:
            raise Conflict(_message(response))
        if response.status_code == 429 or response.status_code >= 500:
            raise ServiceUnavailable(
                f"the Financial Spine answered {response.status_code} for {what}"
            )
        if response.status_code >= 400:
            raise Invalid(_message(response))
        try:
            return response.json()
        except ValueError as exc:
            raise _unexpected(what) from exc

    def health(self) -> Any:
        return self._request("GET", "/api/health", what="the health check")

    def engagement(self, engagement_id: uuid.UUID) -> Any:
        """The Spine's engagement record as served; only its existence matters here."""
        return self._request("GET", f"/api/engagements/{engagement_id}", what="an engagement")

    def version(self, version_id: uuid.UUID) -> SpineVersion:
        return parse_version(
            self._request("GET", f"/api/spine-versions/{version_id}", what="a version")
        )

    def ledgers(self, version_id: uuid.UUID) -> list[SpineLedger]:
        """Every ledger of the version's chain with the head the client's map gives it."""
        return parse_ledgers(
            self._request("GET", f"/api/spine-versions/{version_id}/balances", what="the balances")
        )

    def adjustments(self, version_id: uuid.UUID) -> list[SpineAdjustment]:
        raw = self._request(
            "GET", f"/api/spine-versions/{version_id}/adjustments", what="the adjustments"
        )
        if not isinstance(raw, list):
            raise _unexpected("the adjustments")
        return [parse_adjustment(entry) for entry in raw]

    def adjustment(self, version_id: uuid.UUID, adjustment_id: uuid.UUID) -> SpineAdjustment:
        """One adjustment of the version. The Spine lists them per version, so this filters."""
        for entry in self.adjustments(version_id):
            if entry.adjustment_id == adjustment_id:
                return entry
        raise NotFound(
            f"the Financial Spine has no adjustment {adjustment_id} on version {version_id}"
        )

    def tree(self) -> SpineTree:
        return parse_tree(self._request("GET", "/api/schedule-iii/tree", what="the tree"))

    def propose(
        self,
        version_id: uuid.UUID,
        *,
        kind: str,
        narration: str,
        working_paper_ref: str,
        finding_ref: str | None,
        lines: list[dict[str, Any]],
    ) -> SpineAdjustment:
        """Propose an adjustment; the Spine inserts it ``proposed`` and re-checks every rule."""
        body = {
            "kind": kind,
            "narration": narration,
            "working_paper_ref": working_paper_ref,
            "finding_ref": finding_ref,
            "lines": lines,
        }
        return parse_adjustment(
            self._request(
                "POST",
                f"/api/spine-versions/{version_id}/adjustments",
                what="the proposal",
                json=body,
            )
        )

    def decide(
        self,
        version_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        *,
        status: Literal["accepted", "refused"],
        note: str | None,
    ) -> SpineAdjustment:
        """Accept or refuse an adjustment. The Spine decides once: a second decision and a
        locked version both answer 409, mapped to ``Conflict``. Accepting posts the lines
        to the chain; refusing posts nothing."""
        return parse_adjustment(
            self._request(
                "POST",
                f"/api/spine-versions/{version_id}/adjustments/{adjustment_id}/decision",
                what="the decision",
                json={"status": status, "note": note},
            )
        )


def build_spine_client(settings: Settings, http: httpx.Client | None = None) -> SpineClient | None:
    """A client when OAK_SPINE_URL names a Spine; None means no Spine is configured."""
    if not settings.spine_url:
        return None
    client = http or httpx.Client(timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT))
    return SpineClient(settings.spine_url, client, settings.spine_credential)
