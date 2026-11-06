"""Prior-period uncorrected misstatements carried forward (SA 450 paragraph 11(b); spec
section 4.1; acceptance 5; architecture D61). Pure.

"Prior-period uncorrected misstatements carried forward, with the current-period effect and
the cumulative effect shown separately, so the partner can see it both ways rather than
being handed one method" (spec section 4.1).

A carried item states four figures, each a person's, none computed here:

- its **current-period effect** on profit before tax and on net assets: what it does to
  this period's figures (for instance the reversal, in this period, of an error left
  uncorrected in the last);
- its **cumulative effect** on profit before tax and on net assets: what correcting all of
  it now would do (what still stands in the closing figures).

How either is arrived at for a given item is an accounting judgement this module does not
make (register B6): the figures are entered with their basis. What is computed here is only
their sum, gross and net as spec section 4.1 sums everything, kept apart from the current
year's own misstatements and then shown beside and together with them, on each basis.

Nothing here is read by a gate. Which basis a gate should test, if any, is the firm's
policy and is not decided (register, Pass 2 feature 2).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from oak_misstatements.core.gates import Aggregate

ZERO = Decimal("0.00")

Basis = Literal["current_period", "cumulative"]
BASES: Final[tuple[Basis, ...]] = ("current_period", "cumulative")
MEASURES: Final[tuple[str, ...]] = (
    "profit.gross",
    "profit.net",
    "net_assets.gross",
    "net_assets.net",
)

PRIOR_PERIOD_BASIS: Final[str] = (
    "uncorrected misstatements of prior periods are carried forward and shown apart from the "
    "current year's own (SA 450 paragraph 11(b); spec section 4.1; acceptance 5); each "
    "carried item states its current-period effect and its cumulative effect on profit "
    "before tax and on net assets, entered by a person with the basis: this module computes "
    "neither (register B6); the totals sum those figures gross, with no netting between "
    "items, and net, signed (spec section 4.1); 'with prior-period items' adds each total to "
    "the aggregate of the current year's uncorrected misstatements, so the evaluation is "
    "shown both ways and no one method is chosen; a carried item is not banded and none is "
    "left out as clearly trivial; the gates of spec section 7 test the current year's "
    "aggregate and do not read these figures, because which basis a gate should test is the "
    "firm's policy and is not decided (architecture D61)"
)


@dataclass(frozen=True, slots=True)
class Carried:
    """One prior-period item as it is carried now: its reference, the version read, and
    the four effects that version states."""

    ref: str
    version_no: int
    current_profit: Decimal
    current_net_assets: Decimal
    cumulative_profit: Decimal
    cumulative_net_assets: Decimal


@dataclass(frozen=True, slots=True)
class Pair:
    """One measure summed both ways (spec section 4.1)."""

    gross: Decimal
    net: Decimal

    def plus(self, other: Pair) -> Pair:
        return Pair(self.gross + other.gross, self.net + other.net)


@dataclass(frozen=True, slots=True)
class Effect:
    """Profit before tax and net assets, each gross and net, on one basis."""

    profit: Pair
    net_assets: Pair

    def plus(self, other: Effect) -> Effect:
        return Effect(self.profit.plus(other.profit), self.net_assets.plus(other.net_assets))


def _pair(values: Iterable[Decimal]) -> Pair:
    listed = list(values)
    return Pair(sum((abs(value) for value in listed), ZERO), sum(listed, ZERO))


def total(items: Iterable[Carried], basis: Basis) -> Effect:
    """What the carried items come to on one basis: gross sums sizes with no netting
    between items, net sums them signed."""
    listed = list(items)
    if basis == "current_period":
        return Effect(
            _pair(item.current_profit for item in listed),
            _pair(item.current_net_assets for item in listed),
        )
    return Effect(
        _pair(item.cumulative_profit for item in listed),
        _pair(item.cumulative_net_assets for item in listed),
    )


def current_year(aggregate: Aggregate) -> Effect:
    """The aggregate of the current year's own uncorrected misstatements, as the gates
    read it, in the shape the prior-period totals have."""
    return Effect(
        Pair(aggregate.profit.gross, aggregate.profit.net),
        Pair(aggregate.net_assets.gross, aggregate.net_assets.net),
    )


def reached(effect: Effect, line: Decimal) -> tuple[str, ...]:
    """The measures at or above ``line``: gross as it is, net by its size (the comparison
    the gates make, spec section 7 'at or above'). Information only."""
    sizes = (
        effect.profit.gross,
        abs(effect.profit.net),
        effect.net_assets.gross,
        abs(effect.net_assets.net),
    )
    return tuple(name for name, size in zip(MEASURES, sizes, strict=True) if size >= line)
