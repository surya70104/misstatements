"""The one place the Spine's adjustment kind is chosen (D23, D37)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from oak_misstatements.core.effects import Line, Section, compute
from oak_misstatements.core.spine_kind import spine_kind_for
from oak_misstatements.errors import Invalid


def line(name: str, section: Section, *, dr: str = "0", cr: str = "0") -> Line:
    nature = None if section == "unresolved" else ("PL" if section.startswith("pl") else "BS")
    head = None if name == "Suspense" else name.lower()
    return Line(name.lower(), name, (), head, nature, section, Decimal(dr), Decimal(cr))  # type: ignore[arg-type]


def test_an_item_with_a_profit_effect_is_a_correction() -> None:
    effects = compute([line("Rent", "pl_before_tax", dr="10"), line("Cash", "assets", cr="10")])
    assert spine_kind_for(effects) == "correction"


def test_a_direct_equity_item_is_a_correction_because_net_assets_move() -> None:
    effects = compute(
        [line("Reserve", "equity", dr="10"), line("Provision", "liabilities", cr="10")]
    )
    assert spine_kind_for(effects) == "correction"


def test_a_classification_only_item_is_a_reclassification() -> None:
    """D37: both effects reliably nil is exactly what the Spine calls a reclass."""
    effects = compute([line("Alpha", "assets", dr="10"), line("Cash", "assets", cr="10")])
    assert spine_kind_for(effects) == "reclass"
    within_pl = compute(
        [line("Rent", "pl_before_tax", dr="10"), line("Fees", "pl_before_tax", cr="10")]
    )
    assert spine_kind_for(within_pl) == "reclass"


def test_an_unclassifiable_ledger_is_refused_before_any_kind_is_chosen() -> None:
    effects = compute([line("Suspense", "unresolved", dr="10"), line("Cash", "assets", cr="10")])
    with pytest.raises(Invalid, match="cannot be classified: Suspense"):
        spine_kind_for(effects)
    pending = compute(
        [line("Share application money", "unresolved", dr="10"), line("Cash", "assets", cr="10")]
    )
    with pytest.raises(Invalid, match="share application money pending allotment"):
        spine_kind_for(pending)
