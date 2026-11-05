"""What a misstatement does to the figures (spec section 3.1; architecture D31). Pure: no
database, no HTTP.

Every Dr/Cr line is resolved, before it reaches here, to a *section* of the Schedule III
Division I format, taken from the Financial Spine's tree by ancestry and item reference:

- ``assets``: under item II;
- ``liabilities``: under items I(3) and I(4);
- ``equity``: under item I(1), shareholders' funds;
- ``pl_before_tax``: a profit-and-loss head above the profit-before-tax line, item IX;
- ``pl_after_tax``: tax expense (X, XIII) and discontinuing operations (XII), below it;
- ``unresolved``: no head, a head the tree does not know, or share application money
  pending allotment (I(2)), which the tree does not classify as equity or liability and this
  module does not guess.

From the sections, debit positive as the Spine signs everything:

- effect on **profit before tax**: credits less debits on ``pl_before_tax`` lines, the
  Spine's own rule narrowed to the heads above item IX;
- effect on **net assets**: assets less liabilities, so the signed movement of every
  ``assets`` and ``liabilities`` line. Equity lines are outside the sum, which is why a direct
  equity entry moves net assets while leaving profit alone. Because the lines balance, this
  always equals the credits to profit-and-loss and equity heads less the debits to them;
- **per caption**: the signed movement on each head;
- **classification only**: both effects reliably known and both nil.

When any line is unresolved, neither effect is reliable, because the missing line's side
of the balance sheet is unknown even though its amount is. Both are then ``None`` with the
unresolved ledgers named; no partial total is offered, and nothing is substituted with zero.
Tax is never imputed: a tax line counts only when the entry carries one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Nature = Literal["BS", "PL"]
Section = Literal["assets", "liabilities", "equity", "pl_before_tax", "pl_after_tax", "unresolved"]
ZERO = Decimal("0.00")

PROFIT_BASIS = (
    "credits less debits on profit-and-loss heads above the Schedule III profit-before-tax "
    "line (item IX); tax expense (items X, XIII) and discontinuing operations (XII) are "
    "excluded (architecture D31)"
)
NET_ASSETS_BASIS = (
    "assets less liabilities: the signed movement, debit positive, of every line on an asset "
    "head (item II) or a liability head (items I(3), I(4)); equity heads (I(1)) are outside "
    "the sum, so a direct equity entry moves net assets; tax lines count only when the entry "
    "carries them, nothing is imputed (architecture D31)"
)
PARTIAL_BASIS = (
    "not computed: {names} cannot be classified, so neither effect is reliable and no partial "
    "total is offered (architecture D31)"
)


@dataclass(frozen=True, slots=True)
class Line:
    """One Dr or Cr line as the Spine holds it, with its head, nature and section resolved."""

    ledger_key: str
    ledger_name: str
    parent_chain: tuple[str, ...]
    head_id: str | None
    nature: Nature | None
    section: Section
    dr: Decimal
    cr: Decimal

    @property
    def signed(self) -> Decimal:
        """Debit positive, as the Spine's chain signs balances."""
        return self.dr - self.cr


@dataclass(frozen=True, slots=True)
class CaptionEffect:
    head_id: str
    nature: Nature
    signed: Decimal


@dataclass(frozen=True, slots=True)
class Effects:
    profit_before_tax: Decimal | None
    net_assets: Decimal | None
    partial: bool
    unresolved: tuple[str, ...]  # ledger names whose section could not be determined
    captions: tuple[CaptionEffect, ...]
    classification_only: bool
    profit_basis: str
    net_assets_basis: str

    @property
    def profit_partial(self) -> bool:
        """Kept for the API's earlier field name; the same flag as ``partial``."""
        return self.partial


def balanced(lines: Sequence[Line]) -> bool:
    return sum((line.dr for line in lines), ZERO) == sum((line.cr for line in lines), ZERO)


def compute(lines: Sequence[Line]) -> Effects:
    unresolved = tuple(line.ledger_name for line in lines if line.section == "unresolved")
    by_head: dict[tuple[str, Nature], Decimal] = {}
    for line in lines:
        if line.head_id is not None and line.nature is not None:
            key = (line.head_id, line.nature)
            by_head[key] = by_head.get(key, ZERO) + line.signed
    captions = tuple(
        CaptionEffect(head, nature, value) for (head, nature), value in by_head.items()
    )
    if unresolved:
        basis = PARTIAL_BASIS.format(names=", ".join(unresolved))
        return Effects(None, None, True, unresolved, captions, False, basis, basis)
    profit = sum((line.cr - line.dr for line in lines if line.section == "pl_before_tax"), ZERO)
    net_assets = sum(
        (line.signed for line in lines if line.section in ("assets", "liabilities")), ZERO
    )
    return Effects(
        profit_before_tax=profit,
        net_assets=net_assets,
        partial=False,
        unresolved=(),
        captions=captions,
        classification_only=bool(lines) and profit == ZERO and net_assets == ZERO,
        profit_basis=PROFIT_BASIS,
        net_assets_basis=NET_ASSETS_BASIS,
    )
