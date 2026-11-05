"""A stand-in for the Financial Spine (architecture D11), in memory, speaking the Spine's own
shapes: ``GET /api/engagements/{id}``, ``GET /api/spine-versions/{id}``, ``.../balances``,
``.../adjustments``, ``POST .../adjustments``, ``POST .../adjustments/{id}/decision`` and
``GET /api/schedule-iii/tree``, as ``D:\\CAF\\backend\\src\\oak_spine\\api\\spine.py`` and
``spine/chain.py`` serve them.

It reproduces the rules the module depends on, each cited to the Spine's code:

- an adjustment is ``proposed`` on insert and decided once, to ``accepted`` or ``refused``
  (``api/spine.py:366``; migration 0004, OAKIM);
- nothing can be proposed or decided on a locked version (migration 0004, OAKLK);
- a line names an import ledger by ``line_no`` only, or introduces a ledger by name, chain and
  a mappable head; each line carries one side above zero; the lines balance (``api/spine.py:321``,
  D23 there);
- only accepted adjustments post to the chain (``spine/chain.py``), so the balances move on
  acceptance and not before;
- the tree gives each head its nature, BS or PL (``api/schedule3.py:34``).

Every call is recorded in ``calls`` so a test can assert what was sent. Nothing here is
live data; the ids and head ids are the double's own.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx

from oak_misstatements.services.spine_client import SpineClient

ENGAGEMENT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_ENGAGEMENT_ID = uuid.UUID("11111111-1111-4111-8111-222222222222")
OPEN_VERSION_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
LOCKED_VERSION_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
OTHER_VERSION_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
SPINE_USER = "spine-dev@localhost"
PROPOSED_AT = dt.datetime(2026, 11, 4, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))

# The double's Schedule III heads, a realistic slice of the Spine's Division I tree
# (``D:\\CAF\\backend\\src\\oak_spine\\schedule3\\division1.py``): id, label, parent, nature,
# mappable, and the face item reference where Schedule III gives one. Equity (I(1)), share
# application money pending allotment (I(2)), liabilities (I(3), I(4)), assets (II), tax
# expense (X) and discontinuing operations (XII, XIII) are all present so every section of
# architecture D31 can be exercised.
HEADS: tuple[tuple[str, str, str | None, str, bool, str | None], ...] = (
    ("bs", "Balance sheet", None, "BS", False, None),
    ("bs.liabilities", "Equity and liabilities", "bs", "BS", False, "I"),
    (
        "bs.liabilities.shareholders_funds",
        "Shareholders' funds",
        "bs.liabilities",
        "BS",
        False,
        "I(1)",
    ),
    (
        "bs.liabilities.shareholders_funds.share_capital",
        "Share capital",
        "bs.liabilities.shareholders_funds",
        "BS",
        True,
        "I(1)(a)",
    ),
    (
        "bs.liabilities.shareholders_funds.reserves",
        "Reserves and surplus",
        "bs.liabilities.shareholders_funds",
        "BS",
        False,
        "I(1)(b)",
    ),
    (
        "bs.liabilities.shareholders_funds.reserves.general",
        "General reserve",
        "bs.liabilities.shareholders_funds.reserves",
        "BS",
        True,
        None,
    ),
    (
        "bs.liabilities.shareholders_funds.reserves.capital",
        "Capital reserve",
        "bs.liabilities.shareholders_funds.reserves",
        "BS",
        True,
        None,
    ),
    (
        "bs.liabilities.share_application_money",
        "Share application money pending allotment",
        "bs.liabilities",
        "BS",
        True,
        "I(2)",
    ),
    (
        "bs.liabilities.non_current",
        "Non-current liabilities",
        "bs.liabilities",
        "BS",
        False,
        "I(3)",
    ),
    (
        "bs.liabilities.non_current.deferred_tax_liabilities",
        "Deferred tax liabilities (net)",
        "bs.liabilities.non_current",
        "BS",
        True,
        "I(3)(b)",
    ),
    ("bs.liabilities.current", "Current liabilities", "bs.liabilities", "BS", False, "I(4)"),
    (
        "bs.liabilities.current.trade_payables",
        "Trade payables",
        "bs.liabilities.current",
        "BS",
        True,
        "I(4)(b)",
    ),
    (
        "bs.liabilities.current.other",
        "Other current liabilities",
        "bs.liabilities.current",
        "BS",
        False,
        "I(4)(c)",
    ),
    (
        "bs.liabilities.current.other.share_application_refundable",
        "Share application money refundable",
        "bs.liabilities.current.other",
        "BS",
        True,
        None,
    ),
    (
        "bs.liabilities.current.provisions",
        "Short-term provisions",
        "bs.liabilities.current",
        "BS",
        True,
        "I(4)(d)",
    ),
    (
        "bs.liabilities.current.provision_for_tax",
        "Provision for taxation",
        "bs.liabilities.current",
        "BS",
        True,
        None,
    ),
    ("bs.assets", "Assets", "bs", "BS", False, "II"),
    ("bs.assets.non_current", "Non-current assets", "bs.assets", "BS", False, "II(1)"),
    (
        "bs.assets.non_current.ppe",
        "Property, plant and equipment",
        "bs.assets.non_current",
        "BS",
        False,
        "II(1)(a)",
    ),
    (
        "bs.assets.non_current.ppe.gross",
        "Plant and machinery",
        "bs.assets.non_current.ppe",
        "BS",
        True,
        None,
    ),
    (
        "bs.assets.non_current.ppe.accumulated_depreciation",
        "Accumulated depreciation",
        "bs.assets.non_current.ppe",
        "BS",
        True,
        None,
    ),
    (
        "bs.assets.non_current.deferred_tax_assets",
        "Deferred tax assets (net)",
        "bs.assets.non_current",
        "BS",
        True,
        "II(1)(c)",
    ),
    ("bs.assets.current", "Current assets", "bs.assets", "BS", False, "II(2)"),
    (
        "bs.assets.current.trade_receivables",
        "Trade receivables",
        "bs.assets.current",
        "BS",
        True,
        "II(2)(c)",
    ),
    (
        "bs.assets.current.cash",
        "Cash and cash equivalents",
        "bs.assets.current",
        "BS",
        True,
        "II(2)(d)",
    ),
    ("pl", "Statement of profit and loss", None, "PL", False, None),
    ("pl.revenue", "Revenue from operations", "pl", "PL", False, "I"),
    ("pl.revenue.operations", "Sale of products", "pl.revenue", "PL", True, None),
    ("pl.expenses", "Expenses", "pl", "PL", False, "IV"),
    ("pl.expenses.employee", "Employee benefits expense", "pl.expenses", "PL", True, None),
    ("pl.expenses.depreciation", "Depreciation and amortisation", "pl.expenses", "PL", True, None),
    ("pl.expenses.other", "Other expenses", "pl.expenses", "PL", True, None),
    ("pl.tax_expense", "Tax expense", "pl", "PL", False, "X"),
    ("pl.tax_expense.current", "Current tax", "pl.tax_expense", "PL", True, None),
    ("pl.tax_expense.deferred", "Deferred tax", "pl.tax_expense", "PL", True, None),
    ("pl.discontinuing_operations", "Discontinuing operations", "pl", "PL", False, "XII-XIII"),
    (
        "pl.discontinuing_operations.profit_or_loss",
        "Profit or loss from discontinuing operations",
        "pl.discontinuing_operations",
        "PL",
        True,
        "XII",
    ),
)
TREE_VERSION = "double-division1-2026-11-04"

# The sealed import of the open version: line_no, name, parent chain, head (None = unmapped),
# unadjusted balance (debit positive). Lines 1 to 7 are the Stage 1 ledgers; 8 onwards were
# added for the D31 effects matrix.
IMPORT: tuple[tuple[int, str, tuple[str, ...], str | None, str], ...] = (
    (1, "Alpha Traders", ("Sundry Debtors",), "bs.assets.current.trade_receivables", "500000.00"),
    (2, "Kotak Bank", ("Bank Accounts",), "bs.assets.current.cash", "120000.00"),
    (
        3,
        "Provision for expenses",
        ("Provisions",),
        "bs.liabilities.current.provisions",
        "-80000.00",
    ),
    (4, "Sales", ("Sales Accounts",), "pl.revenue.operations", "-900000.00"),
    (5, "Rent", ("Indirect Expenses",), "pl.expenses.other", "60000.00"),
    (6, "Salaries", ("Indirect Expenses",), "pl.expenses.employee", "300000.00"),
    (7, "Suspense", ("Suspense A/c",), None, "0.00"),
    (
        8,
        "Trade payables",
        ("Sundry Creditors",),
        "bs.liabilities.current.trade_payables",
        "-150000.00",
    ),
    (
        9,
        "General reserve",
        ("Reserves & Surplus",),
        "bs.liabilities.shareholders_funds.reserves.general",
        "-200000.00",
    ),
    (
        10,
        "Capital reserve",
        ("Reserves & Surplus",),
        "bs.liabilities.shareholders_funds.reserves.capital",
        "-50000.00",
    ),
    (
        11,
        "Share application money",
        ("Share Application",),
        "bs.liabilities.share_application_money",
        "-30000.00",
    ),
    (
        12,
        "Provision for tax",
        ("Provisions",),
        "bs.liabilities.current.provision_for_tax",
        "-40000.00",
    ),
    (
        13,
        "Deferred tax liability",
        ("Provisions",),
        "bs.liabilities.non_current.deferred_tax_liabilities",
        "-20000.00",
    ),
    (
        14,
        "Accumulated depreciation",
        ("Fixed Assets",),
        "bs.assets.non_current.ppe.accumulated_depreciation",
        "-90000.00",
    ),
    (15, "Depreciation", ("Indirect Expenses",), "pl.expenses.depreciation", "90000.00"),
    (16, "Current tax", ("Taxes",), "pl.tax_expense.current", "40000.00"),
    (17, "Deferred tax expense", ("Taxes",), "pl.tax_expense.deferred", "20000.00"),
    (
        18,
        "Deferred tax asset",
        ("Fixed Assets",),
        "bs.assets.non_current.deferred_tax_assets",
        "10000.00",
    ),
    (19, "Plant and machinery", ("Fixed Assets",), "bs.assets.non_current.ppe.gross", "400000.00"),
    (
        20,
        "Share application refundable",
        ("Current Liabilities",),
        "bs.liabilities.current.other.share_application_refundable",
        "-5000.00",
    ),
)


def ledger_key(name: str) -> str:
    """The double's normaliser: lower case, single spaces."""
    return re.sub(r"\s+", " ", name.strip().lower())


def amount(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):f}"


@dataclass
class Adjustment:
    adjustment_id: uuid.UUID
    version_id: uuid.UUID
    kind: str
    narration: str
    working_paper_ref: str
    finding_ref: str | None
    lines: list[dict[str, Any]]
    status: str = "proposed"
    decided_by: str | None = None
    decided_at: str | None = None
    decision_note: str | None = None

    def json(self) -> dict[str, Any]:
        return {
            "adjustment_id": str(self.adjustment_id),
            "version_id": str(self.version_id),
            "kind": self.kind,
            "status": self.status,
            "narration": self.narration,
            "working_paper_ref": self.working_paper_ref,
            "finding_ref": self.finding_ref,
            "proposed_by": SPINE_USER,
            "proposed_at": PROPOSED_AT.isoformat(),
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
            "copied_from_id": None,
            "lines": [dict(line) for line in self.lines],
        }


@dataclass
class Version:
    version_id: uuid.UUID
    engagement_id: uuid.UUID
    version_no: int
    label: str
    is_locked: bool
    performance_materiality: str | None = None

    def json(self, adjustments: list[Adjustment]) -> dict[str, Any]:
        return {
            "version_id": str(self.version_id),
            "engagement_id": str(self.engagement_id),
            "entity_id": "55555555-5555-4555-8555-555555555555",
            "base_import_id": "44444444-4444-4444-8444-444444444444",
            "version_no": self.version_no,
            "label": self.label,
            "supersedes_id": None,
            "supersede_reason": None,
            "prior_version_id": None,
            "performance_materiality": self.performance_materiality,
            "pm_source": "C-1 Materiality memo" if self.performance_materiality else None,
            "is_locked": self.is_locked,
            "locked_by": SPINE_USER if self.is_locked else None,
            "locked_at": PROPOSED_AT.isoformat() if self.is_locked else None,
            "hash": "f" * 64 if self.is_locked else None,
            "tree_version": 3 if self.is_locked else None,
            "snapshot_sha256": "f" * 64 if self.is_locked else None,
            "created_by": SPINE_USER,
            "created_at": PROPOSED_AT.isoformat(),
            "adjustments": {
                "proposed": sum(1 for a in adjustments if a.status == "proposed"),
                "accepted": sum(1 for a in adjustments if a.status == "accepted"),
                "refused": sum(1 for a in adjustments if a.status == "refused"),
            },
        }


def _refusal(status: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(status, json={"detail": {"code": code, "message": message}})


def _validation(message: str) -> httpx.Response:
    return httpx.Response(422, json={"detail": [{"loc": ["body"], "msg": message}]})


@dataclass
class FakeSpine:
    versions: dict[uuid.UUID, Version] = field(default_factory=dict)
    adjustments: dict[uuid.UUID, Adjustment] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)
    unreachable: bool = False
    # A status the decision endpoint answers instead of deciding (a test hook): the reads
    # still work, so a failure exactly at the decision can be simulated.
    decision_failure: int | None = None
    timing_out: bool = False
    broken_json: bool = False

    def __post_init__(self) -> None:
        # Instance-level copies so a test can remap a ledger, move the tree or re-key a
        # ledger between reads, as the real Spine may between two days (D32).
        self.heads: list[tuple[str, str, str | None, str, bool, str | None]] = list(HEADS)
        self.tree_version: str = TREE_VERSION
        self.head_overrides: dict[str, str | None] = {}  # ledger name -> head id now
        self.rekey: dict[str, str] = {}  # ledger name -> ledger key the Spine now gives
        self.rechain: dict[str, list[str]] = {}  # ledger name -> parent chain it now gives
        self.versions = {
            OPEN_VERSION_ID: Version(
                OPEN_VERSION_ID, ENGAGEMENT_ID, 1, "Draft", False, "250000.00"
            ),
            LOCKED_VERSION_ID: Version(
                LOCKED_VERSION_ID, ENGAGEMENT_ID, 2, "Final", True, "250000.00"
            ),
            OTHER_VERSION_ID: Version(OTHER_VERSION_ID, OTHER_ENGAGEMENT_ID, 1, "Other", False),
        }

    # ---- changes between reads (D32) ------------------------------------------------------

    def remap(self, ledger_name: str, head_id: str | None) -> None:
        """The client remapped an import ledger to another head (or unmapped it)."""
        self.head_overrides[ledger_name] = head_id

    def retire_head(self, head_id: str, *, tree_version: str) -> None:
        """A new tree without this head: ledgers mapped to it have no classification."""
        self.heads = [head for head in self.heads if head[0] != head_id]
        self.tree_version = tree_version

    def move_head(self, head_id: str, *, parent: str, item: str | None, tree_version: str) -> None:
        """A new tree where this head sits under another parent, with another item."""
        self.heads = [
            (
                hid,
                label,
                parent if hid == head_id else par,
                nature,
                mappable,
                item if hid == head_id else it,
            )
            for hid, label, par, nature, mappable, it in self.heads
        ]
        self.tree_version = tree_version

    def rekey_ledger(self, ledger_name: str, ledger_key: str) -> None:
        """The Spine now derives a different key for this ledger (a changed normaliser)."""
        self.rekey[ledger_name] = ledger_key

    def rechain_ledger(self, ledger_name: str, parent_chain: list[str]) -> None:
        """The Spine now serves this ledger under another parent chain, key unchanged. The
        real Spine cannot do this (its adjustment lines are immutable); the hook exists so
        the module's refusal to guess is proven for the other half of a ledger's identity."""
        self.rechain[ledger_name] = list(parent_chain)

    def _rekeyed(self, body: dict[str, Any]) -> dict[str, Any]:
        if not self.rekey and not self.rechain:
            return body
        return {
            **body,
            "lines": [
                {
                    **line,
                    "ledger_key": self.rekey.get(line["ledger_name"], line["ledger_key"]),
                    "parent_chain": self.rechain.get(line["ledger_name"], line["parent_chain"]),
                }
                for line in body["lines"]
            ],
        }

    # ---- the client ----------------------------------------------------------------------

    def client(self, credential: str | None = None) -> SpineClient:
        http = httpx.Client(transport=httpx.MockTransport(self.handle))
        return SpineClient("http://spine.test", http, credential)

    # ---- the HTTP surface ----------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        if self.unreachable:
            raise httpx.ConnectError("refused")
        if self.timing_out:
            raise httpx.ReadTimeout("slow")
        if self.broken_json:
            return httpx.Response(200, content=b"<html>not json</html>")
        path = request.url.path
        if request.method == "GET" and path == "/api/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.method == "GET" and path == "/api/schedule-iii/tree":
            return httpx.Response(200, json=self.tree_json())
        if (m := re.fullmatch(r"/api/engagements/([0-9a-f-]+)", path)) and request.method == "GET":
            return self._engagement(m.group(1))
        if (
            m := re.fullmatch(r"/api/spine-versions/([0-9a-f-]+)", path)
        ) and request.method == "GET":
            return self._version(m.group(1))
        if m := re.fullmatch(r"/api/spine-versions/([0-9a-f-]+)/balances", path):
            return self._balances(m.group(1))
        if m := re.fullmatch(r"/api/spine-versions/([0-9a-f-]+)/adjustments", path):
            if request.method == "GET":
                return self._list(m.group(1))
            if request.method == "POST":
                return self._propose(m.group(1), json.loads(request.content))
        if (
            m := re.fullmatch(
                r"/api/spine-versions/([0-9a-f-]+)/adjustments/([0-9a-f-]+)/decision", path
            )
        ) and request.method == "POST":
            return self._decide(m.group(1), m.group(2), json.loads(request.content))
        return httpx.Response(404, json={"detail": f"no route for {request.method} {path}"})

    def tree_json(self) -> dict[str, Any]:
        depth = {head_id: head_id.count(".") for head_id, *_rest in self.heads}
        return {
            "division": "I",
            "version": self.tree_version,
            "heads": [
                {
                    "id": head_id,
                    "label": label,
                    "parent": parent,
                    "statement": "balance_sheet" if nature == "BS" else "profit_and_loss",
                    "nature": nature,
                    "side": "debit"
                    if head_id.startswith("bs.assets") or nature == "PL"
                    else "credit",
                    "item": item,
                    "note": None,
                    "mappable": mappable,
                    "basis": "statute",
                    "depth": depth[head_id],
                }
                for head_id, label, parent, nature, mappable, item in self.heads
            ],
        }

    def _engagement(self, raw_id: str) -> httpx.Response:
        if uuid.UUID(raw_id) in (ENGAGEMENT_ID, OTHER_ENGAGEMENT_ID):
            return httpx.Response(
                200, json={"id": raw_id, "label": "FY 2025-26 statutory audit", "entity_id": "x"}
            )
        return _refusal(404, "engagement.not_found", f"No engagement {raw_id}")

    def _version(self, raw_id: str) -> httpx.Response:
        version = self.versions.get(uuid.UUID(raw_id))
        if version is None:
            return _refusal(404, "spine_version.not_found", f"No spine_version {raw_id}")
        return httpx.Response(200, json=version.json(self._of(version.version_id)))

    def _of(self, version_id: uuid.UUID) -> list[Adjustment]:
        return [a for a in self.adjustments.values() if a.version_id == version_id]

    def _nature_of(self, head_id: str | None) -> str | None:
        for entry_id, _label, _parent, nature, _mappable, _item in self.heads:
            if entry_id == head_id:
                return nature
        return None

    def _balances(self, raw_id: str) -> httpx.Response:
        version = self.versions.get(uuid.UUID(raw_id))
        if version is None:
            return _refusal(404, "spine_version.not_found", f"No spine_version {raw_id}")
        rows: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
        for line_no, name, chain, imported_head, unadjusted in IMPORT:
            head_id = self.head_overrides.get(name, imported_head)
            rows[(ledger_key(name), chain)] = {
                "line_no": line_no,
                "ledger_key": ledger_key(name),
                "ledger_name": name,
                "parent_chain": list(chain),
                "in_import": True,
                "absent": False,
                "head_id": head_id,
                "face_head": None,
                "sub_head": None,
                "nature": self._nature_of(head_id),
                "side": None,
                "opening": None,
                "movement": None,
                "unadjusted": Decimal(unadjusted),
                "reclass": Decimal("0.00"),
                "corrections": Decimal("0.00"),
            }
        next_line = len(IMPORT) + 1
        for adjustment in self._of(version.version_id):
            if adjustment.status != "accepted":
                continue
            column = "reclass" if adjustment.kind == "reclass" else "corrections"
            for line in adjustment.lines:
                key = (line["ledger_key"], tuple(line["parent_chain"]))
                if key not in rows:
                    rows[key] = {
                        "line_no": next_line,
                        "ledger_key": line["ledger_key"],
                        "ledger_name": line["ledger_name"],
                        "parent_chain": list(line["parent_chain"]),
                        "in_import": False,
                        "absent": False,
                        "head_id": line["head_id"],
                        "face_head": None,
                        "sub_head": None,
                        "nature": self._nature_of(line["head_id"]),
                        "side": None,
                        "opening": None,
                        "movement": None,
                        "unadjusted": Decimal("0.00"),
                        "reclass": Decimal("0.00"),
                        "corrections": Decimal("0.00"),
                    }
                    next_line += 1
                rows[key][column] += Decimal(line["dr"]) - Decimal(line["cr"])
        ledgers = []
        for row in rows.values():
            adjusted = row["unadjusted"] + row["reclass"] + row["corrections"]
            ledgers.append(
                {
                    **row,
                    "unadjusted": amount(row["unadjusted"]),
                    "reclass": amount(row["reclass"]),
                    "corrections": amount(row["corrections"]),
                    "adjusted": amount(adjusted),
                    "prior_closing": None,
                    "prior_regrouped": None,
                    "regroup_reason": None,
                }
            )
        return httpx.Response(
            200,
            json={
                "version_id": raw_id,
                "base_import_id": "44444444-4444-4444-8444-444444444444",
                "is_locked": version.is_locked,
                "source": "stored" if version.is_locked else "computed",
                "tree_version": 3,
                "hash": None,
                "ledgers": ledgers,
                "groups": [],
                "totals": {},
            },
        )

    def _list(self, raw_id: str) -> httpx.Response:
        version = self.versions.get(uuid.UUID(raw_id))
        if version is None:
            return _refusal(404, "spine_version.not_found", f"No spine_version {raw_id}")
        return httpx.Response(
            200, json=[self._rekeyed(a.json()) for a in self._of(version.version_id)]
        )

    def _propose(self, raw_id: str, body: dict[str, Any]) -> httpx.Response:
        version = self.versions.get(uuid.UUID(raw_id))
        if version is None:
            return _refusal(404, "spine_version.not_found", f"No spine_version {raw_id}")
        if version.is_locked:
            return _refusal(
                409,
                "spine.locked",
                f"spine_version {raw_id} is locked; nothing can be added to it",
            )
        if body.get("kind") not in ("reclass", "correction"):
            return _validation("kind must be 'reclass' or 'correction'")
        if not str(body.get("narration") or "").strip():
            return _validation("narration must not be blank")
        if not str(body.get("working_paper_ref") or "").strip():
            return _validation("working_paper_ref must not be blank")
        raw_lines = body.get("lines")
        if not isinstance(raw_lines, list) or len(raw_lines) < 2:
            return _validation("lines must hold at least two lines")
        lines: list[dict[str, Any]] = []
        debits = credits = Decimal("0")
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for raw in raw_lines:
            dr, cr = raw.get("dr"), raw.get("cr")
            if (dr is None) == (cr is None):
                return _validation("a line carries exactly one of dr and cr, above zero")
            value = Decimal(str(dr if dr is not None else cr))
            if value <= 0 or value != value.quantize(Decimal("0.01")):
                return _validation("amounts are positive with at most two decimal places")
            if raw.get("line_no") is not None:
                if raw.get("ledger_name") or raw.get("head_id") or raw.get("parent_chain"):
                    return _validation("an import line must not send a name, chain or head")
                found = [entry for entry in IMPORT if entry[0] == raw["line_no"]]
                if not found:
                    return _validation(f"line_no {raw['line_no']} is not in the sealed import")
                _line_no, name, chain, head_id, _unadjusted = found[0]
                key, chain_t, head = ledger_key(name), chain, None  # the map decides the head
                line = {
                    "line_no": raw["line_no"],
                    "ledger_key": key,
                    "ledger_name": name,
                    "parent_chain": list(chain_t),
                    "head_id": head,
                    "in_import": True,
                }
            else:
                name = str(raw.get("ledger_name") or "")
                head_id = raw.get("head_id")
                mappable = any(h[0] == head_id and h[4] for h in self.heads)
                if not name or not mappable:
                    return _validation(
                        "a ledger the import lacks needs a name and a mappable leaf head"
                    )
                chain_t = tuple(str(p) for p in raw.get("parent_chain") or [])
                key = ledger_key(name)
                if any(ledger_key(e[1]) == key and e[2] == chain_t for e in IMPORT):
                    return _validation(f"{name!r} is a sealed line; reference it by line_no")
                line = {
                    "line_no": 0,
                    "ledger_key": key,
                    "ledger_name": name,
                    "parent_chain": list(chain_t),
                    "head_id": head_id,
                    "in_import": False,
                }
            if (key, chain_t) in seen:
                return _validation("the same ledger appears on more than one line")
            seen.add((key, chain_t))
            line["dr"] = amount(Decimal(str(dr))) if dr is not None else "0.00"
            line["cr"] = amount(Decimal(str(cr))) if cr is not None else "0.00"
            debits += Decimal(line["dr"])
            credits += Decimal(line["cr"])
            lines.append(line)
        if debits != credits:
            return _validation(f"the lines do not balance: Dr {debits} Cr {credits}")
        adjustment = Adjustment(
            adjustment_id=uuid.uuid4(),
            version_id=version.version_id,
            kind=str(body["kind"]),
            narration=str(body["narration"]),
            working_paper_ref=str(body["working_paper_ref"]),
            finding_ref=body.get("finding_ref"),
            lines=lines,
        )
        self.adjustments[adjustment.adjustment_id] = adjustment
        return httpx.Response(201, json=adjustment.json())

    def _decide(self, raw_version: str, raw_id: str, body: dict[str, Any]) -> httpx.Response:
        if self.decision_failure is not None:
            return httpx.Response(self.decision_failure, json={"detail": "decision failed"})
        version = self.versions.get(uuid.UUID(raw_version))
        adjustment = self.adjustments.get(uuid.UUID(raw_id))
        if version is None or adjustment is None or adjustment.version_id != version.version_id:
            return _refusal(404, "adjustment.not_found", f"No adjustment {raw_id}")
        if version.is_locked:
            return _refusal(
                409, "spine.locked", f"adjustment {raw_id}: its spine_version is locked"
            )
        if adjustment.status != "proposed":
            return _refusal(
                409,
                "adjustment.already_decided",
                f"adjustment {raw_id} was decided ({adjustment.status}) and cannot be changed",
            )
        if body.get("status") not in ("accepted", "refused"):
            return _validation("status must be 'accepted' or 'refused'")
        note = body.get("note")
        if note is not None and not 0 < len(str(note).strip()) <= 2000:
            return _validation("note must hold 1 to 2000 characters when given")
        adjustment.status = str(body["status"])
        adjustment.decided_by = SPINE_USER
        adjustment.decided_at = PROPOSED_AT.isoformat()
        adjustment.decision_note = body.get("note")
        return httpx.Response(200, json=adjustment.json())

    # ---- helpers for tests ----------------------------------------------------------------

    def adjusted_balance(self, version_id: uuid.UUID, ledger_name: str) -> Decimal:
        """The ledger's adjusted balance as the balances endpoint would show it."""
        body = self._balances(str(version_id)).json()
        for row in body["ledgers"]:
            if row["ledger_name"] == ledger_name:
                return Decimal(row["adjusted"])
        raise KeyError(ledger_name)
