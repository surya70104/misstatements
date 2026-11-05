"""The band of a misstatement against the three lines (spec section 4; D33): the literal
boundaries, both effects banded separately with the higher band winning, nothing banded on
unresolved effects, and the inclusive aggregate gates."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oak_misstatements.core.banding import (
    BAND_BASIS,
    Band,
    BandResult,
    Lines,
    band_for,
    band_item,
    hard_gate_fires,
    higher,
    range_crosses_pm,
    soft_gate_fires,
)
from oak_misstatements.core.effects import Line, Section, compute

LINES = Lines(ctt=Decimal("12500.00"), pm=Decimal("250000.00"), om=Decimal("400000.00"))
THRESHOLD_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


# ---- B11: the literal boundaries ------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "band"),
    [
        ("0.00", Band.CLEARLY_TRIVIAL),
        ("12499.99", Band.CLEARLY_TRIVIAL),  # below CTT: clearly trivial (line 81)
        ("12500.00", Band.ACCUMULATED),  # exactly CTT: accumulates
        ("100000.00", Band.ACCUMULATED),
        ("249999.99", Band.ACCUMULATED),
        ("250000.00", Band.ACCUMULATED),  # exactly PM: not "above PM" (line 83)
        ("250000.01", Band.INDIVIDUALLY_SIGNIFICANT),  # strictly above PM
        ("400000.00", Band.INDIVIDUALLY_SIGNIFICANT),
        ("999999999.00", Band.INDIVIDUALLY_SIGNIFICANT),
    ],
)
def test_the_three_lines_and_their_boundaries(amount: str, band: Band) -> None:
    assert band_for(Decimal(amount), LINES) is band


def test_the_aggregate_gates_are_inclusive() -> None:
    assert soft_gate_fires(Decimal("249999.99"), LINES) is False
    assert soft_gate_fires(Decimal("250000.00"), LINES) is True  # at PM: line 141
    assert hard_gate_fires(Decimal("399999.99"), LINES) is False
    assert hard_gate_fires(Decimal("400000.00"), LINES) is True  # at OM: line 139


def test_a_negative_amount_is_refused_and_lines_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="never negative"):
        band_for(Decimal("-1"), LINES)
    with pytest.raises(ValueError, match="below PM"):
        Lines(ctt=Decimal("250000"), pm=Decimal("250000"), om=Decimal("1"))
    with pytest.raises(ValueError, match="above zero"):
        Lines(ctt=Decimal("0"), pm=Decimal("1"), om=Decimal("1"))
    with pytest.raises(ValueError, match="OM must be above zero"):
        Lines(ctt=Decimal("1"), pm=Decimal("2"), om=Decimal("0"))


def test_higher_band_wins() -> None:
    assert higher(Band.CLEARLY_TRIVIAL, Band.ACCUMULATED) is Band.ACCUMULATED
    assert higher(Band.INDIVIDUALLY_SIGNIFICANT, Band.ACCUMULATED) is Band.INDIVIDUALLY_SIGNIFICANT
    assert higher(Band.ACCUMULATED, Band.ACCUMULATED) is Band.ACCUMULATED


# ---- B3: both effects, separately -------------------------------------------------------------


def line(name: str, section: Section, *, dr: str = "0", cr: str = "0") -> Line:
    nature = None if section == "unresolved" else ("PL" if section.startswith("pl") else "BS")
    head = None if section == "unresolved" else name
    return Line(name, name, (), head, nature, section, Decimal(dr), Decimal(cr))  # type: ignore[arg-type]


def banded(lines: list[Line]) -> BandResult | None:
    return band_item(compute(lines), LINES, threshold_id=THRESHOLD_ID, threshold_version_no=3)


def test_a_profit_and_loss_correction_bands_both_effects_alike() -> None:
    result = banded(
        [line("rent", "pl_before_tax", dr="20000"), line("provisions", "liabilities", cr="20000")]
    )
    assert result is not None
    assert (result.profit_band, result.net_assets_band, result.band) == (
        Band.ACCUMULATED,
        Band.ACCUMULATED,
        Band.ACCUMULATED,
    )
    assert (result.profit_amount, result.net_assets_amount) == (Decimal("20000"), Decimal("20000"))
    assert (result.threshold_id, result.threshold_version_no, result.basis) == (
        THRESHOLD_ID,
        3,
        BAND_BASIS,
    )


def test_a_direct_equity_entry_is_trivial_on_profit_and_banded_on_net_assets() -> None:
    result = banded(
        [line("reserve", "equity", dr="300000"), line("provisions", "liabilities", cr="300000")]
    )
    assert result is not None
    assert result.profit_band is Band.CLEARLY_TRIVIAL
    assert result.net_assets_band is Band.INDIVIDUALLY_SIGNIFICANT
    assert result.band is Band.INDIVIDUALLY_SIGNIFICANT  # the higher of the two


def test_differing_effects_each_get_their_own_band() -> None:
    # A correction with its tax lines: profit moves more than net assets.
    result = banded(
        [
            line("rent", "pl_before_tax", dr="260000"),
            line("provisions", "liabilities", cr="260000"),
            line("provision for tax", "liabilities", dr="240000"),
            line("current tax", "pl_after_tax", cr="240000"),
        ]
    )
    assert result is not None
    assert result.profit_amount == Decimal("260000")
    assert result.net_assets_amount == Decimal("20000")
    assert result.profit_band is Band.INDIVIDUALLY_SIGNIFICANT
    assert result.net_assets_band is Band.ACCUMULATED
    assert result.band is Band.INDIVIDUALLY_SIGNIFICANT


def test_a_negative_effect_is_banded_on_its_size() -> None:
    result = banded(
        [
            line("sales", "pl_before_tax", dr="250000.01"),
            line("receivables", "assets", cr="250000.01"),
        ]
    )
    assert result is not None
    assert result.band is Band.INDIVIDUALLY_SIGNIFICANT


def test_classification_only_items_are_clearly_trivial_on_amount() -> None:
    result = banded([line("receivables", "assets", dr="700"), line("cash", "assets", cr="700")])
    assert result is not None
    assert (result.profit_band, result.net_assets_band, result.band) == (
        Band.CLEARLY_TRIVIAL,
        Band.CLEARLY_TRIVIAL,
        Band.CLEARLY_TRIVIAL,
    )


def test_nothing_is_banded_on_unresolved_effects() -> None:
    assert (
        banded([line("suspense", "unresolved", dr="50"), line("sales", "pl_before_tax", cr="50")])
        is None
    )


def test_range_crossing_pm_is_information_beside_the_band() -> None:
    assert range_crosses_pm(Decimal("5000"), Decimal("15000"), LINES) is False
    assert range_crosses_pm(Decimal("5000"), Decimal("250000.01"), LINES) is True
    assert range_crosses_pm(Decimal("-300000"), Decimal("1"), LINES) is True
    assert (
        range_crosses_pm(Decimal("1"), Decimal("250000.00"), LINES) is False
    )  # at PM is not above
    assert range_crosses_pm(None, None, LINES) is None


money = st.decimals(
    min_value=Decimal("0.00"), max_value=Decimal("9999999.99"), places=2, allow_nan=False
)


@given(money)
def test_every_amount_lands_in_exactly_the_band_its_size_dictates(amount: Decimal) -> None:
    band = band_for(amount, LINES)
    if amount < LINES.ctt:
        assert band is Band.CLEARLY_TRIVIAL
    elif amount <= LINES.pm:
        assert band is Band.ACCUMULATED
    else:
        assert band is Band.INDIVIDUALLY_SIGNIFICANT


@given(money, money)
def test_the_item_band_is_never_below_either_effects_band(
    profit: Decimal, net_assets: Decimal
) -> None:
    # A synthetic entry whose profit and net assets effects are the two drawn sizes: a P&L
    # line for the profit effect and an equity line for the difference.
    lines = [
        line("rent", "pl_before_tax", dr=str(profit)),
        line("reserve", "equity", cr=str(profit)),
        line("receivables", "assets", dr=str(net_assets)),
        line("reserve2", "equity", cr=str(net_assets)),
    ]
    result = banded(lines)
    assert result is not None
    assert result.profit_amount == profit
    assert result.net_assets_amount == net_assets
    assert result.band is higher(result.profit_band, result.net_assets_band)
