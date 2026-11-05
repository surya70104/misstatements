"""Spec section 3.1 as arithmetic (architecture D31): the effect on profit before tax, the
effect on net assets, the captions, the classification-only flag, and the refusal to offer
a partial total. The full matrix from the B7 investigation is here, on sections directly;
``test_api_misstatements.py`` runs the same entries through the Spine double."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oak_misstatements.core.effects import (
    NET_ASSETS_BASIS,
    PROFIT_BASIS,
    ZERO,
    CaptionEffect,
    Line,
    Section,
    balanced,
    compute,
)

# head id -> (nature, section), a slice of the Schedule III format.
HEADS: dict[str, tuple[str, Section]] = {
    "receivables": ("BS", "assets"),
    "cash": ("BS", "assets"),
    "accumulated_depreciation": ("BS", "assets"),  # contra asset, credit side
    "deferred_tax_asset": ("BS", "assets"),
    "provisions": ("BS", "liabilities"),
    "trade_payables": ("BS", "liabilities"),
    "provision_for_tax": ("BS", "liabilities"),
    "deferred_tax_liability": ("BS", "liabilities"),
    "share_application_refundable": ("BS", "liabilities"),
    "general_reserve": ("BS", "equity"),
    "capital_reserve": ("BS", "equity"),
    "share_application_money": ("BS", "unresolved"),  # item I(2): not classified by the tree
    "sales": ("PL", "pl_before_tax"),
    "rent": ("PL", "pl_before_tax"),
    "salaries": ("PL", "pl_before_tax"),
    "depreciation": ("PL", "pl_before_tax"),
    "current_tax": ("PL", "pl_after_tax"),
    "deferred_tax": ("PL", "pl_after_tax"),
    "discontinued": ("PL", "pl_after_tax"),
}


def line(name: str, *, dr: str = "0", cr: str = "0") -> Line:
    if name == "suspense":
        return Line("suspense", "Suspense", (), None, None, "unresolved", Decimal(dr), Decimal(cr))
    nature, section = HEADS[name]
    return Line(name, name, (), name, nature, section, Decimal(dr), Decimal(cr))  # type: ignore[arg-type]


def dr(name: str, amount: str) -> Line:
    return line(name, dr=amount)


def cr(name: str, amount: str) -> Line:
    return line(name, cr=amount)


MATRIX: list[tuple[str, list[Line], str | None, str | None, bool]] = [
    (
        "normal expense accrual",
        [dr("rent", "10000"), cr("provisions", "10000")],
        "-10000",
        "-10000",
        False,
    ),
    (
        "revenue cut-off",
        [dr("sales", "50000"), cr("receivables", "50000")],
        "-50000",
        "-50000",
        False,
    ),
    (
        "compound, mixed",
        [dr("rent", "6000"), dr("receivables", "4000"), cr("provisions", "10000")],
        "-6000",
        "-6000",
        False,
    ),
    (
        "compound, two P&L lines",
        [dr("rent", "6000"), dr("salaries", "4000"), cr("cash", "10000")],
        "-10000",
        "-10000",
        False,
    ),
    (
        "tax expense only",
        [dr("current_tax", "3000"), cr("provision_for_tax", "3000")],
        "0",
        "-3000",
        False,
    ),
    (
        "correction with its tax lines",
        [
            dr("rent", "10000"),
            cr("provisions", "10000"),
            dr("provision_for_tax", "2500"),
            cr("current_tax", "2500"),
        ],
        "-10000",
        "-7500",
        False,
    ),
    (
        "direct equity, prior-year error",
        [dr("general_reserve", "8000"), cr("provisions", "8000")],
        "0",
        "-8000",
        False,
    ),
    (
        "direct equity, asset side",
        [dr("receivables", "8000"), cr("general_reserve", "8000")],
        "0",
        "8000",
        False,
    ),
    (
        "classification, balance sheet",
        [dr("receivables", "700"), cr("cash", "700")],
        "0",
        "0",
        True,
    ),
    (
        "classification, asset against liability",
        [dr("trade_payables", "700"), cr("receivables", "700")],
        "0",
        "0",
        True,
    ),
    ("classification, profit and loss", [dr("rent", "700"), cr("salaries", "700")], "0", "0", True),
    (
        "classification within equity",
        [dr("general_reserve", "700"), cr("capital_reserve", "700")],
        "0",
        "0",
        True,
    ),
    (
        "deferred tax",
        [dr("deferred_tax", "1200"), cr("deferred_tax_liability", "1200")],
        "0",
        "-1200",
        False,
    ),
    (
        "contra asset",
        [dr("depreciation", "2000"), cr("accumulated_depreciation", "2000")],
        "-2000",
        "-2000",
        False,
    ),
    (
        "discontinuing operations",
        [dr("discontinued", "900"), cr("cash", "900")],
        "0",
        "-900",
        False,
    ),
    ("unknown account", [dr("suspense", "50"), cr("sales", "50")], None, None, False),
    (
        "share application money, no reliable classification",
        [dr("share_application_money", "5000"), cr("cash", "5000")],
        None,
        None,
        False,
    ),
    (
        "share application money refundable, classified as a liability",
        [dr("share_application_refundable", "5000"), cr("cash", "5000")],
        "0",
        "0",
        True,
    ),
]


@pytest.mark.parametrize(("label", "lines", "pbt", "net_assets", "classification"), MATRIX)
def test_the_matrix(
    label: str, lines: list[Line], pbt: str | None, net_assets: str | None, classification: bool
) -> None:
    assert balanced(lines), label
    effects = compute(lines)
    assert effects.profit_before_tax == (None if pbt is None else Decimal(pbt)), label
    assert effects.net_assets == (None if net_assets is None else Decimal(net_assets)), label
    assert effects.classification_only is classification, label
    assert effects.partial is (pbt is None), label
    if pbt is not None:
        # The identity: net assets equals the credits less debits on every profit-and-loss
        # line (before and after tax) plus the credits less debits on equity lines.
        mirror = sum(
            (
                entry.cr - entry.dr
                for entry in lines
                if entry.section in ("pl_before_tax", "pl_after_tax", "equity")
            ),
            ZERO,
        )
        assert effects.net_assets == mirror, label


# ---- the two defects of the B7 investigation, as regressions --------------------------------


def test_regression_a_tax_expense_line_does_not_move_profit_before_tax() -> None:
    effects = compute([dr("current_tax", "3000"), cr("provision_for_tax", "3000")])
    assert effects.profit_before_tax == ZERO
    assert effects.net_assets == Decimal("-3000")
    assert not effects.classification_only


def test_regression_a_direct_equity_entry_is_not_classification_only() -> None:
    effects = compute([dr("general_reserve", "8000"), cr("provisions", "8000")])
    assert effects.profit_before_tax == ZERO
    assert effects.net_assets == Decimal("-8000")
    assert not effects.classification_only


def test_an_unresolved_line_gives_no_partial_total_and_names_the_ledger() -> None:
    effects = compute([dr("suspense", "50"), cr("sales", "50")])
    assert effects.partial is True
    assert effects.profit_partial is True
    assert effects.unresolved == ("Suspense",)
    assert effects.profit_before_tax is None and effects.net_assets is None
    assert "Suspense" in effects.net_assets_basis and "not computed" in effects.net_assets_basis
    assert not effects.classification_only
    # The known line still appears as a caption.
    assert effects.captions == (CaptionEffect("sales", "PL", Decimal("-50")),)


def test_the_bases_say_what_was_computed() -> None:
    effects = compute([dr("rent", "1"), cr("cash", "1")])
    assert effects.profit_basis == PROFIT_BASIS
    assert effects.net_assets_basis == NET_ASSETS_BASIS
    assert "item IX" in PROFIT_BASIS and "D31" in NET_ASSETS_BASIS


def test_captions_fold_lines_on_one_head() -> None:
    effects = compute([dr("rent", "700"), dr("sales", "300"), cr("rent", "1000")])
    assert effects.captions == (
        CaptionEffect("rent", "PL", Decimal("-300")),
        CaptionEffect("sales", "PL", Decimal("300")),
    )
    assert effects.classification_only


def test_no_lines_is_not_classification_only() -> None:
    assert not compute([]).classification_only


money = st.decimals(
    min_value=Decimal("0.01"), max_value=Decimal("9999999.99"), places=2, allow_nan=False
)
resolved_heads = st.sampled_from(
    [name for name, (_nature, section) in HEADS.items() if section != "unresolved"]
)


@st.composite
def balanced_lines(draw: st.DrawFn) -> list[Line]:
    """Random balanced entries over classified heads: debits, then one credit per debit."""
    debits = draw(st.lists(st.tuples(resolved_heads, money), min_size=1, max_size=6))
    lines = [line(name, dr=str(value)) for name, value in debits]
    lines += [line(draw(resolved_heads), cr=str(value)) for _name, value in debits]
    return lines


@given(balanced_lines())
def test_net_assets_equals_the_mirror_of_profit_and_equity_for_any_balanced_entry(
    lines: list[Line],
) -> None:
    effects = compute(lines)
    assert not effects.partial
    expected_pbt = sum(
        (entry.cr - entry.dr for entry in lines if entry.section == "pl_before_tax"), ZERO
    )
    assert effects.profit_before_tax == expected_pbt
    mirror = sum(
        (
            entry.cr - entry.dr
            for entry in lines
            if entry.section in ("pl_before_tax", "pl_after_tax", "equity")
        ),
        ZERO,
    )
    assert effects.net_assets == mirror
    assert effects.classification_only == (expected_pbt == ZERO and effects.net_assets == ZERO)
    assert sum((caption.signed for caption in effects.captions), ZERO) == ZERO
