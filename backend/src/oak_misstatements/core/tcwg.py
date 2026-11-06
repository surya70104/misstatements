"""The TCWG extract (SA 450 paragraph 12; spec section 2 row 12, section 6 item 2;
acceptance 9; architecture D62). Pure.

"Communicate uncorrected misstatements to TCWG, identifying material ones individually, and
request correction" (spec section 2). "The TCWG extract: uncorrected misstatements, material
ones individually named, with the effect on the opinion, and the request to correct" (spec
section 6). "The TCWG extract names every individually material item" (acceptance 9).

Every uncorrected misstatement (raised, communicated or refused: the aggregate's own
reading, F3) falls into exactly one of four places:

- **named individually**: banded individually significant, that is above PM, which spec
  section 4 says is "listed by name in the TCWG communication"; or escalated on a
  qualitative factor, which spec section 5 lists "individually regardless of size". Each
  says why it is named, and whether its own effect is at or above overall materiality;
- **undetermined**: it could not be banded, so whether it is above PM is not known. It is
  named too, as undetermined, and the extract is marked incomplete: an item is never left
  off the individual list on a guess;
- **other uncorrected**: accumulated and not named. Summarised by type, since spec section
  3.2 keeps the three types apart, and listed;
- **clearly trivial, not accumulated**: below the clearly-trivial threshold and left out of
  the aggregate (spec section 4). Not part of the communication; named apart with what
  they come to, so the extract can be reconciled to the schedule.

The module shows both individual tests, above PM and at or above overall materiality, and
chooses neither as the meaning of "material individually": the determination is the
partner's (register B14). Every item at or above overall materiality is above PM, so naming
the wider set names every individually material item on either reading.

Nothing here decides the effect on the opinion: that is the opinion gate's
(``core/gates.py``), read as it stands.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from oak_misstatements.core.banding import Band
from oak_misstatements.core.gates import Aggregate, Item, items_at_or_above

ZERO = Decimal("0.00")

ABOVE_PM: Final[str] = "above_pm"
AT_OR_ABOVE_OM: Final[str] = "at_or_above_om"
ESCALATED: Final[str] = "escalated"

REASON_TEXT: Final[dict[str, str]] = {
    ABOVE_PM: "above performance materiality on its own (individually significant)",
    AT_OR_ABOVE_OM: "at or above overall materiality on its own",
    ESCALATED: "escalated on a qualitative factor, whatever its amount",
}

TYPES: Final[tuple[str, ...]] = ("factual", "judgemental", "projected")

TCWG_BASIS: Final[str] = (
    "the uncorrected misstatements of the engagement (raised, communicated or refused; the "
    "F3 reading), for communication to those charged with governance (SA 450 paragraph 12; "
    "spec section 6); named individually: every one banded individually significant, above "
    "PM, which spec section 4 lists by name in the TCWG communication, and every one "
    "escalated on a qualitative factor, which spec section 5 lists individually regardless "
    "of size (acceptance 9); each says why it is named and whether its own effect is at or "
    "above overall materiality, so every individually material item is named whichever of "
    "the two lines 'material individually' means (register B14); an item that could not be "
    "banded is named as undetermined and the extract marked incomplete; the other "
    "accumulated items are summarised by type and listed; an item below the clearly-trivial "
    "threshold and not accumulated is outside the communication and named apart (spec "
    "section 4); corrected and withdrawn items are not uncorrected and are not included; "
    "gross sums sizes with no netting between misstatements, net sums them signed (spec "
    "section 4.1); the effect on the opinion is the opinion gate's reading and is not "
    "decided here (spec section 7; architecture D18, D62)"
)

REQUEST_TEXT: Final[str] = (
    "We request that the uncorrected misstatements set out in this schedule be corrected."
)
REQUEST_BASIS: Final[str] = (
    "SA 450 paragraph 12: the auditor communicates uncorrected misstatements to those "
    "charged with governance and requests that they be corrected (spec section 2, row 12; "
    "section 6, item 2). The sentence is the standard's requirement put plainly; the firm's "
    "own wording, and whom the communication is addressed to, are the firm's"
)
NOTHING_TO_REQUEST: Final[str] = (
    "No uncorrected misstatement is accumulated, so there is nothing to request correction of."
)


@dataclass(frozen=True, slots=True)
class Named:
    """An item named individually, and why."""

    item: Item
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Pair:
    """One measure summed both ways (spec section 4.1)."""

    gross: Decimal
    net: Decimal


@dataclass(frozen=True, slots=True)
class Sums:
    count: int
    profit: Pair
    net_assets: Pair


@dataclass(frozen=True, slots=True)
class Extract:
    named: tuple[Named, ...]
    undetermined: tuple[Item, ...]
    other: tuple[Item, ...]
    # Clearly trivial and left out of the aggregate: not part of the communication.
    left_out: tuple[Item, ...]

    @property
    def communicated(self) -> int:
        """How many uncorrected misstatements the extract communicates."""
        return len(self.named) + len(self.undetermined) + len(self.other)


def sums(items: Iterable[Item]) -> Sums:
    """Count, and the effects summed gross (sizes, no netting) and net (signed). Only items
    whose effects are known contribute; the callers pass no other."""
    listed = list(items)
    profits = [item.profit for item in listed if item.profit is not None]
    assets = [item.net_assets for item in listed if item.net_assets is not None]
    return Sums(
        len(listed),
        Pair(sum((abs(value) for value in profits), ZERO), sum(profits, ZERO)),
        Pair(sum((abs(value) for value in assets), ZERO), sum(assets, ZERO)),
    )


def by_type(items: Iterable[Item]) -> dict[str, Sums]:
    """The items summarised by type, the three kept apart (spec section 3.2)."""
    listed = list(items)
    return {kind: sums(item for item in listed if item.type == kind) for kind in TYPES}


def extract(items: list[Item], aggregate: Aggregate, om: Decimal | None) -> Extract:
    """Place every uncorrected misstatement: named individually, undetermined, other, or
    clearly trivial and not accumulated."""
    at_om = {item.ref for item in items_at_or_above(items, om)}
    left_out = set(aggregate.not_accumulated)
    named: list[Named] = []
    undetermined: list[Item] = []
    other: list[Item] = []
    trivial: list[Item] = []
    for item in items:
        if not item.uncorrected:
            continue
        reasons: list[str] = []
        if item.band is Band.INDIVIDUALLY_SIGNIFICANT:
            reasons.append(ABOVE_PM)
        if item.ref in at_om:
            reasons.append(AT_OR_ABOVE_OM)
        if item.escalated:
            reasons.append(ESCALATED)
        if reasons:
            named.append(Named(item, tuple(reasons)))
        elif item.band is None:
            undetermined.append(item)
        elif item.ref in left_out:
            trivial.append(item)
        else:
            other.append(item)
    return Extract(tuple(named), tuple(undetermined), tuple(other), tuple(trivial))
