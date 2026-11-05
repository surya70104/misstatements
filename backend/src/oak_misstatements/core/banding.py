"""The band of a misstatement against the three lines (spec section 4; architecture D33).
Pure: no database, no HTTP. The band is computed, never chosen (spec line 86).

The spec's wording, applied literally:

- below CTT is clearly trivial (line 81: "below it, not accumulated"), so an amount exactly
  at CTT accumulates;
- from CTT to PM accumulates (line 82);
- above PM is individually significant (lines 83, 146, 232), so an amount exactly at PM
  accumulates;
- the aggregate gates are inclusive: at or above PM the soft gate fires (line 141), at or
  above overall materiality the hard gate fires (line 139). The asymmetry between the
  individual test and the aggregate tests is the spec's own wording and is kept as written.

Profit and net assets are evaluated separately (line 93): each effect is banded on its
absolute value, and the item's band is the higher of the two, the conservative reading.
Nothing is banded when either effect is unresolved; a null band is the only honest answer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from oak_misstatements.core.effects import Effects

BAND_BASIS = (
    "each effect banded on its absolute value against the current threshold version: below CTT "
    "clearly trivial, from CTT to PM inclusive accumulated, above PM individually significant "
    "(spec section 4); the item's band is the higher of the two (architecture D33)"
)
NO_THRESHOLDS_BASIS = (
    "no band: no thresholds have been set for this engagement yet (spec section 4)"
)
UNRESOLVED_BASIS = (
    "no band: the effects are unresolved ({names}), and nothing is banded on a guess "
    "(architecture D31, D32, D33)"
)
NO_EFFECTS_BASIS = "no band: the Financial Spine could not be read, so there are no effects to band"
CLASSIFICATION_ONLY_BASIS = (
    "clearly trivial on amount: both effects are nil, so the item moves balances between "
    "captions only; proposed to the Spine as a reclassification; its significance is "
    "qualitative (spec section 5, Pass 2) and its gross size is shown as measure (D37)"
)


class Band(StrEnum):
    CLEARLY_TRIVIAL = "clearly_trivial"
    ACCUMULATED = "accumulated"
    INDIVIDUALLY_SIGNIFICANT = "individually_significant"


RANK = {Band.CLEARLY_TRIVIAL: 0, Band.ACCUMULATED: 1, Band.INDIVIDUALLY_SIGNIFICANT: 2}


@dataclass(frozen=True, slots=True)
class Lines:
    """The three lines of one threshold version."""

    ctt: Decimal
    pm: Decimal
    om: Decimal

    def __post_init__(self) -> None:
        if not Decimal(0) < self.ctt < self.pm:
            raise ValueError("CTT must be above zero and below PM (spec section 4)")
        if self.om <= 0:
            raise ValueError("OM must be above zero")


def band_for(amount: Decimal, lines: Lines) -> Band:
    """The band of a non-negative amount, the spec's wording applied literally."""
    if amount < 0:
        raise ValueError("an amount is a size, never negative; pass its absolute value")
    if amount < lines.ctt:
        return Band.CLEARLY_TRIVIAL
    if amount <= lines.pm:
        return Band.ACCUMULATED
    return Band.INDIVIDUALLY_SIGNIFICANT


def higher(first: Band, second: Band) -> Band:
    return first if RANK[first] >= RANK[second] else second


@dataclass(frozen=True, slots=True)
class BandResult:
    band: Band
    profit_band: Band
    net_assets_band: Band
    profit_amount: Decimal  # the absolute effect that was banded
    net_assets_amount: Decimal
    threshold_id: uuid.UUID
    threshold_version_no: int
    basis: str


def band_item(
    effects: Effects, lines: Lines, *, threshold_id: uuid.UUID, threshold_version_no: int
) -> BandResult | None:
    """Both effects banded separately, the item's band the higher of the two; None when
    either effect is unresolved. Classification-only items, both effects nil, come out
    clearly trivial on amount; their significance is qualitative (spec section 5)."""
    if effects.partial or effects.profit_before_tax is None or effects.net_assets is None:
        return None
    profit_amount = abs(effects.profit_before_tax)
    net_assets_amount = abs(effects.net_assets)
    profit_band = band_for(profit_amount, lines)
    net_assets_band = band_for(net_assets_amount, lines)
    return BandResult(
        band=higher(profit_band, net_assets_band),
        profit_band=profit_band,
        net_assets_band=net_assets_band,
        profit_amount=profit_amount,
        net_assets_amount=net_assets_amount,
        threshold_id=threshold_id,
        threshold_version_no=threshold_version_no,
        basis=BAND_BASIS,
    )


def soft_gate_fires(aggregate: Decimal, lines: Lines) -> bool:
    """Spec line 141: the aggregate at or above performance materiality."""
    return aggregate >= lines.pm


def hard_gate_fires(aggregate: Decimal, lines: Lines) -> bool:
    """Spec line 139: the aggregate at or above overall materiality."""
    return aggregate >= lines.om


def range_crosses_pm(
    range_low: Decimal | None, range_high: Decimal | None, lines: Lines
) -> bool | None:
    """For a judgemental item: whether either end of the auditor's range, in absolute
    terms, lies above PM. Information beside the band, never the band itself (D33)."""
    if range_low is None or range_high is None:
        return None
    return max(abs(range_low), abs(range_high)) > lines.pm
