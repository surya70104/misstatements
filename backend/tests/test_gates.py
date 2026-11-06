"""The aggregate and the gates on items directly (spec sections 4.1 and 7; D38): gross and
net, profit and net assets, with and without the projected items, the inclusive boundaries,
indeterminate when an item is unresolved, and the fail-closed sign-off decision."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from oak_misstatements.core.banding import Band, Lines
from oak_misstatements.core.gates import (
    Item,
    aggregate,
    blocking_items,
    gate,
    sign_off,
    unbanded_items,
)

LINES = Lines(ctt=Decimal("12500.00"), pm=Decimal("250000.00"), om=Decimal("400000.00"))


def item(
    ref: str,
    profit: str | None,
    net_assets: str | None = None,
    *,
    type: str = "factual",
    state: str = "raised",
    band: Band | None = Band.ACCUMULATED,
    classification_only: bool = False,
    refusal_reason: str | None = None,
) -> Item:
    return Item(
        misstatement_id=uuid.uuid4(),
        ref=ref,
        type=type,
        state=state,
        profit=None if profit is None else Decimal(profit),
        net_assets=Decimal(net_assets if net_assets is not None else (profit or "0")),
        classification_only=classification_only,
        band=band,
        refusal_reason=refusal_reason,
    )


# ---- the aggregate ----------------------------------------------------------------------------


def test_gross_sums_sizes_and_net_sums_signs_for_each_measure_separately() -> None:
    total = aggregate(
        [
            item("M-1", "-10000", "-10000"),
            item("M-2", "4000", "-4000"),  # profit up, net assets down
            item("M-3", "0", "8000"),  # a direct equity entry: profit untouched
        ]
    )
    assert (total.profit.gross, total.profit.net) == (Decimal("14000"), Decimal("-6000"))
    assert (total.net_assets.gross, total.net_assets.net) == (Decimal("22000"), Decimal("-6000"))
    assert total.counted == ("M-1", "M-2", "M-3")
    assert total.complete is True


def test_projected_items_count_and_are_given_apart() -> None:
    total = aggregate(
        [
            item("M-1", "-100000"),
            item("M-2", "-300000", type="projected"),
            item("M-3", "20000", type="judgemental"),
        ]
    )
    assert total.projected == ("M-2",)
    assert total.profit.gross == Decimal("420000")
    assert total.profit.gross_without_projected == Decimal("120000")
    assert total.profit.net_without_projected == Decimal("-80000")
    assert total.profit.projected_gross == Decimal("300000")
    assert total.profit.factual_gross == Decimal("100000")
    assert total.profit.judgemental_gross == Decimal("20000")


def test_corrected_and_withdrawn_items_are_excluded_and_refused_ones_count() -> None:
    total = aggregate(
        [
            item("M-1", "-5000", state="corrected"),
            item("M-2", "-6000", state="withdrawn"),
            item("M-3", "-7000", state="refused", refusal_reason="disagree"),
            item("M-4", "-8000", state="communicated"),
        ]
    )
    assert total.excluded == (("M-1", "corrected"), ("M-2", "withdrawn"))
    assert total.counted == ("M-3", "M-4")
    assert total.profit.gross == Decimal("15000")


def test_a_classification_only_item_is_listed_and_contributes_nil() -> None:
    total = aggregate([item("M-1", "0", "0", classification_only=True, band=Band.CLEARLY_TRIVIAL)])
    assert total.classification_only == ("M-1",)
    assert total.counted == ("M-1",)
    assert total.not_accumulated == ()  # listed at nil, as before (B2, D53)
    assert total.profit.gross == total.net_assets.gross == Decimal("0")


# ---- clearly trivial items are not accumulated (spec sections 2 and 4; D53) ---------------

TRIVIAL = Band.CLEARLY_TRIVIAL


def test_a_clearly_trivial_item_is_named_and_left_out_of_every_sum() -> None:
    total = aggregate(
        [
            item("M-1", "-60000"),
            item("M-2", "8000", band=TRIVIAL),
            item("M-3", "-5000", type="projected", band=TRIVIAL),
            item("M-4", "-7000", state="refused", refusal_reason="disagree", band=TRIVIAL),
            item("M-5", "-6000", state="communicated", band=TRIVIAL),
            item("M-6", "-4000", type="judgemental", band=TRIVIAL),
        ]
    )
    assert total.counted == ("M-1",)
    assert total.not_accumulated == ("M-2", "M-3", "M-4", "M-5", "M-6")
    # What they come to together, gross, for information only (D56).
    assert (total.left_out_profit, total.left_out_net_assets) == (
        Decimal("30000"),
        Decimal("30000"),
    )
    assert total.projected == ()
    for measure in (total.profit, total.net_assets):
        assert (measure.gross, measure.net) == (Decimal("60000"), Decimal("-60000"))
        assert measure.gross_without_projected == Decimal("60000")
        assert measure.net_without_projected == Decimal("-60000")
        assert measure.projected_gross == measure.judgemental_gross == Decimal("0")
        assert measure.factual_gross == Decimal("60000")
    assert total.complete is True


def test_trivial_items_stay_out_only_while_together_they_are_below_ctt() -> None:
    """SA 450 paragraph A2 (D57): clearly inconsequential "whether taken individually or
    in aggregate". Gross, so opposite signs do not cancel; at or above CTT brings all in."""
    pair = [item("M-1", "-6000", band=TRIVIAL), item("M-2", "6499.99", band=TRIVIAL)]
    below = aggregate(pair, LINES.ctt)  # 12,499.99 together
    assert below.not_accumulated == ("M-1", "M-2")
    assert below.accumulated_together == ()
    assert below.profit.gross == Decimal("0")
    assert (below.left_out_profit, below.left_out_net_assets) == (
        Decimal("12499.99"),
        Decimal("12499.99"),
    )
    at = aggregate([*pair, item("M-3", "-0.01", band=TRIVIAL)], LINES.ctt)  # exactly 12,500
    assert at.not_accumulated == ()
    assert at.accumulated_together == at.counted == ("M-1", "M-2", "M-3")
    assert (at.profit.gross, at.profit.net) == (Decimal("12500.00"), Decimal("499.98"))


def test_either_measure_reaching_ctt_brings_the_trivial_items_in() -> None:
    items = [
        item("M-1", "0", "8000", band=TRIVIAL),  # a direct equity entry: profit untouched
        item("M-2", "-1000", "-5000", band=TRIVIAL),
    ]
    total = aggregate(items, LINES.ctt)  # profit 1,000 together; net assets 13,000
    assert total.accumulated_together == ("M-1", "M-2")
    assert total.profit.gross == Decimal("1000")
    assert total.net_assets.gross == Decimal("13000")


def test_many_trivial_items_reach_the_gates_once_they_are_accumulated() -> None:
    many = [item(f"M-{n}", "-12499.99", band=TRIVIAL) for n in range(1, 41)]  # 4,99,999.60
    total = aggregate(many, LINES.ctt)
    assert total.not_accumulated == ()
    assert total.profit.gross == Decimal("499999.60")
    assert gate("soft", total, LINES.pm).status == "fires"
    assert gate("hard", total, LINES.om).status == "fires"
    # A projected one among them is accumulated as projected, and is still given apart.
    mixed = aggregate(
        [item("M-1", "-7000", band=TRIVIAL), item("M-2", "-7000", type="projected", band=TRIVIAL)],
        LINES.ctt,
    )
    assert mixed.projected == ("M-2",)
    assert mixed.profit.gross_without_projected == Decimal("7000")


def test_without_a_threshold_nothing_is_tested_together() -> None:
    many = [item(f"M-{n}", "-12499.99", band=TRIVIAL) for n in range(1, 41)]
    total = aggregate(many)  # no CTT is known: the items keep the band they were given
    assert total.accumulated_together == ()
    assert len(total.not_accumulated) == 40


def test_a_corrected_or_withdrawn_trivial_item_is_excluded_by_its_state() -> None:
    total = aggregate(
        [
            item("M-1", "-5000", state="corrected", band=TRIVIAL),
            item("M-2", "-6000", state="withdrawn", band=TRIVIAL),
        ]
    )
    assert total.excluded == (("M-1", "corrected"), ("M-2", "withdrawn"))
    assert total.not_accumulated == ()
    assert total.counted == ()


def test_an_item_without_a_band_is_never_treated_as_clearly_trivial() -> None:
    unresolved = aggregate([item("M-1", None, "0", band=None)])
    assert unresolved.unresolved == ("M-1",)
    assert unresolved.not_accumulated == ()
    assert unresolved.complete is False
    # No thresholds, so no band: nothing can be called clearly trivial, and it is summed.
    unbanded = aggregate([item("M-1", "-5000", band=None)])
    assert unbanded.counted == ("M-1",)
    assert unbanded.profit.gross == Decimal("5000")


def test_an_item_is_in_the_aggregate_with_both_effects_or_with_neither() -> None:
    """The band is the item's (D33: the higher of its two effects' bands). 5,000 on profit
    and 50,000 on net assets is accumulated, and both effects are summed."""
    total = aggregate([item("M-1", "-5000", "-50000", band=Band.ACCUMULATED)])
    assert total.profit.gross == Decimal("5000")
    assert total.net_assets.gross == Decimal("50000")
    left_out = aggregate([item("M-1", "-5000", "-6000", band=TRIVIAL)])
    assert left_out.profit.gross == left_out.net_assets.gross == Decimal("0")


def test_an_unresolved_uncorrected_item_makes_the_aggregate_incomplete() -> None:
    total = aggregate([item("M-1", "-1000"), item("M-2", None, "0", band=None)])
    assert total.unresolved == ("M-2",)
    assert total.complete is False
    assert total.counted == ("M-1",)
    # A withdrawn item that is unresolved is not an uncorrected gap.
    assert aggregate([item("M-3", None, "0", state="withdrawn", band=None)]).complete is True


# ---- the gates: inclusive boundaries, every measure, projected dependence --------------


@pytest.mark.parametrize(
    ("amount", "hard", "soft"),
    [
        ("249999.99", "clear", "clear"),
        ("250000.00", "clear", "fires"),  # exactly PM: at or above (line 141)
        ("399999.99", "clear", "fires"),
        ("400000.00", "fires", "fires"),  # exactly OM: at or above (line 139)
        ("400000.01", "fires", "fires"),
    ],
)
def test_the_boundaries_are_inclusive(amount: str, hard: str, soft: str) -> None:
    total = aggregate([item("M-1", f"-{amount}")])
    assert gate("hard", total, LINES.om).status == hard
    assert gate("soft", total, LINES.pm).status == soft


def test_the_gate_names_the_measures_that_reached_the_line() -> None:
    # Two items that cancel on net but not on gross.
    total = aggregate([item("M-1", "-300000", "-300000"), item("M-2", "300000", "300000")])
    result = gate("hard", total, LINES.om)
    assert result.status == "fires"
    assert result.fires_on == ("profit.gross", "net_assets.gross")
    assert result.highest == Decimal("600000")
    # One item that reaches the line on net assets only.
    equity = aggregate([item("M-3", "0", "-400000")])
    assert gate("hard", equity, LINES.om).fires_on == ("net_assets.gross", "net_assets.net")


def test_a_negative_net_is_compared_on_its_size() -> None:
    total = aggregate([item("M-1", "-400000", "0")])
    assert gate("hard", total, LINES.om).fires_on == ("profit.gross", "profit.net")


def test_the_same_boundaries_hold_for_projected_only_items_and_the_dependence_is_said() -> None:
    for amount, status in (("399999.99", "clear"), ("400000.00", "fires")):
        total = aggregate([item("M-1", f"-{amount}", type="projected")])
        result = gate("hard", total, LINES.om)
        assert result.status == status
        assert result.fires_without_projected is False
        assert result.depends_on_projected is (status == "fires")


def test_a_mixed_aggregate_says_whether_the_factual_items_alone_reach_the_line() -> None:
    total = aggregate([item("M-1", "-200000"), item("M-2", "-200000", type="projected")])
    hard = gate("hard", total, LINES.om)
    assert (hard.status, hard.fires_without_projected, hard.depends_on_projected) == (
        "fires",
        False,
        True,
    )
    soft = gate("soft", total, LINES.pm)
    assert (soft.status, soft.fires_without_projected, soft.depends_on_projected) == (
        "fires",
        False,
        True,
    )
    both = aggregate([item("M-1", "-400000"), item("M-2", "-1", type="projected")])
    assert gate("hard", both, LINES.om).depends_on_projected is False


def test_an_incomplete_aggregate_is_indeterminate_unless_the_known_items_already_fire() -> None:
    short = aggregate([item("M-1", "-1000"), item("M-2", None, "0", band=None)])
    assert gate("hard", short, LINES.om).status == "indeterminate"
    assert gate("hard", short, LINES.om).blocks is True
    loud = aggregate([item("M-1", "-400000"), item("M-2", None, "0", band=None)])
    assert gate("hard", loud, LINES.om).status == "fires"


def test_no_thresholds_means_no_gate_and_still_blocks() -> None:
    result = gate("hard", aggregate([item("M-1", "-1")]), None)
    assert result.status == "no_thresholds"
    assert result.blocks is True


# ---- individually significant items and the sign-off decision -------------------------


def test_an_item_above_pm_blocks_until_corrected_refused_with_a_reason_or_withdrawn() -> None:
    significant = Band.INDIVIDUALLY_SIGNIFICANT
    items = [
        item("M-1", "-300000", band=significant, state="raised"),
        item("M-2", "-300000", band=significant, state="communicated"),
        item("M-3", "-300000", band=significant, state="refused", refusal_reason="no"),
        item("M-4", "-300000", band=significant, state="refused", refusal_reason="  "),
        item("M-5", "-300000", band=significant, state="corrected"),
        item("M-6", "-300000", band=significant, state="withdrawn"),
        item("M-7", "-1", band=Band.ACCUMULATED, state="raised"),
    ]
    assert [entry.ref for entry in blocking_items(items)] == ["M-1", "M-2", "M-4"]
    assert [entry.ref for entry in unbanded_items([item("M-8", None, "0", band=None)])] == ["M-8"]


def test_sign_off_fails_closed_and_names_every_reason() -> None:
    total = aggregate([item("M-1", "-250000", type="projected")])
    hard = gate("hard", total, LINES.om)
    soft = gate("soft", total, LINES.pm)
    assert hard.status == "clear" and soft.status == "fires"
    unacknowledged = sign_off(
        hard, soft, pm_gate="soft", soft_acknowledged=False, blocking=(), unbanded=()
    )
    assert unacknowledged.blocked is True
    assert unacknowledged.reasons == (
        "soft gate: aggregate at or above performance materiality on profit.gross, "
        "profit.net, net_assets.gross, net_assets.net and the partner has not acknowledged "
        "these figures",
    )
    acknowledged = sign_off(
        hard, soft, pm_gate="soft", soft_acknowledged=True, blocking=(), unbanded=()
    )
    assert acknowledged.blocked is False
    firm_hard = sign_off(
        hard, soft, pm_gate="hard", soft_acknowledged=True, blocking=(), unbanded=()
    )
    assert firm_hard.blocked is True and "OAK_PM_GATE" in firm_hard.reasons[0]
    blocked_item = item("M-9", "-300000", type="projected", band=Band.INDIVIDUALLY_SIGNIFICANT)
    with_item = sign_off(
        hard,
        soft,
        pm_gate="soft",
        soft_acknowledged=True,
        blocking=(blocked_item,),
        unbanded=(item("M-10", None, "0", band=None),),
    )
    assert with_item.reasons == (
        "M-9 is individually significant and raised (projected)",
        "M-10 is raised and cannot be banded",
    )


def test_a_hard_gate_that_depends_on_projected_items_says_so_in_the_reason() -> None:
    total = aggregate([item("M-1", "-400000", type="projected")])
    decision = sign_off(
        gate("hard", total, LINES.om),
        gate("soft", total, LINES.pm),
        pm_gate="soft",
        soft_acknowledged=True,
        blocking=(),
        unbanded=(),
    )
    assert decision.blocked is True
    assert "only with the projected items; pending decision B8" in decision.reasons[0]
    none = sign_off(
        gate("hard", aggregate([]), None),
        gate("soft", aggregate([]), None),
        pm_gate="soft",
        soft_acknowledged=False,
        blocking=(),
        unbanded=(),
    )
    assert none.reasons == ("no thresholds have been set, so no gate can be evaluated",)


# ---- D41: the state here and the adjustment in the Spine must agree ------------------------


def test_a_state_the_spine_does_not_share_blocks_sign_off() -> None:
    from dataclasses import replace

    from oak_misstatements.core.gates import inconsistent_items

    agreeing = [
        replace(item("M-1", "-1"), spine_adjustment_status="proposed"),
        replace(item("M-2", "-1", state="communicated"), spine_adjustment_status="proposed"),
        replace(item("M-3", "-1", state="corrected"), spine_adjustment_status="accepted"),
        replace(
            item("M-4", "-1", state="refused", refusal_reason="no"),
            spine_adjustment_status="refused",
        ),
        replace(item("M-5", "-1", state="withdrawn"), spine_adjustment_status="refused"),
        item("M-6", "-1"),  # the Spine could not be read: unknown, not a disagreement
    ]
    assert inconsistent_items(agreeing) == ()
    posted = replace(item("M-7", "-1"), spine_adjustment_status="accepted")
    unposted = replace(item("M-8", "-1", state="corrected"), spine_adjustment_status="proposed")
    found = inconsistent_items([*agreeing, posted, unposted])
    assert [entry.ref for entry in found] == ["M-7", "M-8"]
    total = aggregate([])
    decision = sign_off(
        gate("hard", total, LINES.om),
        gate("soft", total, LINES.pm),
        pm_gate="soft",
        soft_acknowledged=False,
        blocking=(),
        unbanded=(),
        inconsistent=found,
    )
    assert decision.reasons == (
        "M-7 is raised here but its adjustment is accepted in the Financial Spine",
        "M-8 is corrected here but its adjustment is proposed in the Financial Spine",
    )


# ---- D43: the individual test of SA 450 paragraph 11 ---------------------------------------


def test_the_individual_test_keeps_refused_items_and_drops_corrected_and_withdrawn() -> None:
    from oak_misstatements.core.gates import individually_significant_items, items_at_or_above

    significant = Band.INDIVIDUALLY_SIGNIFICANT
    items = [
        item("M-1", "-300000", band=significant, state="raised"),
        item("M-2", "-300000", band=significant, state="communicated"),
        item("M-3", "-300000", band=significant, state="refused", refusal_reason="no"),
        item("M-4", "-300000", band=significant, state="corrected"),
        item("M-5", "-300000", band=significant, state="withdrawn"),
        item("M-6", "-100000", band=Band.ACCUMULATED),
        item("M-7", None, "0", band=None),
    ]
    assert [entry.ref for entry in individually_significant_items(items)] == ["M-1", "M-2", "M-3"]
    assert [entry.ref for entry in blocking_items(items)] == ["M-1", "M-2"]
    at_om = [
        item("M-1", "-399999.99"),
        item("M-2", "-400000.00"),
        item("M-3", "400000.00", "0"),  # the sign does not matter
        item("M-4", "0", "-400000.01"),  # net assets alone
        item("M-5", "-900000", state="corrected"),
        item("M-6", "-900000", state="withdrawn"),
        item("M-7", "-900000", state="refused", refusal_reason="no"),
        item("M-8", None, "0", band=None),
    ]
    assert [entry.ref for entry in items_at_or_above(at_om, LINES.om)] == [
        "M-2",
        "M-3",
        "M-4",
        "M-7",
    ]
    assert items_at_or_above(at_om, None) == ()


# ---- D45: what blocks which conclusion, and the strategy trigger ---------------------------


def test_every_reason_is_a_materiality_or_a_readiness_reason() -> None:
    from oak_misstatements.core.gates import MATERIALITY, READINESS, conclusion_blockers

    total = aggregate([item("M-1", "-400000", type="projected")])
    blocked = item("M-2", "-300000", band=Band.INDIVIDUALLY_SIGNIFICANT)
    decision = sign_off(
        gate("hard", total, LINES.om),
        gate("soft", total, LINES.pm),
        pm_gate="soft",
        soft_acknowledged=False,
        blocking=(blocked,),
        unbanded=(item("M-3", None, "0", band=None),),
    )
    assert decision.kinds == (MATERIALITY, MATERIALITY, READINESS, READINESS)
    assert len(decision.kinds) == len(decision.reasons)
    # Not material: everything blocks. Material: only what leaves the evaluation unknown.
    assert conclusion_blockers(decision, "not_material") == decision.reasons
    assert conclusion_blockers(decision, "material") == (
        "M-2 is individually significant and raised",
        "M-3 is raised and cannot be banded",
    )


def test_a_gate_that_fires_blocks_not_material_and_never_material() -> None:
    from oak_misstatements.core.gates import conclusion_blockers

    refused = item(
        "M-1", "-400000", band=Band.INDIVIDUALLY_SIGNIFICANT, state="refused", refusal_reason="no"
    )
    total = aggregate([refused])
    for pm_gate, acknowledged in (("soft", False), ("soft", True), ("hard", True)):
        decision = sign_off(
            gate("hard", total, LINES.om),
            gate("soft", total, LINES.pm),
            pm_gate=pm_gate,  # type: ignore[arg-type]
            soft_acknowledged=acknowledged,
            blocking=blocking_items([refused]),
            unbanded=(),
        )
        assert conclusion_blockers(decision, "not_material")
        assert conclusion_blockers(decision, "material") == ()


def test_an_unknown_evaluation_blocks_both_conclusions() -> None:
    from oak_misstatements.core.gates import conclusion_blockers

    none = sign_off(
        gate("hard", aggregate([]), None),
        gate("soft", aggregate([]), None),
        pm_gate="soft",
        soft_acknowledged=False,
        blocking=(),
        unbanded=(),
    )
    short = aggregate([item("M-1", "-1"), item("M-2", None, "0", band=None)])
    indeterminate = sign_off(
        gate("hard", short, LINES.om),
        gate("soft", short, LINES.pm),
        pm_gate="soft",
        soft_acknowledged=False,
        blocking=(),
        unbanded=(),
    )
    for decision in (none, indeterminate):
        assert conclusion_blockers(decision, "material") == decision.reasons
        assert conclusion_blockers(decision, "not_material") == decision.reasons
        assert decision.blocked is True
    clear = sign_off(
        gate("hard", aggregate([item("M-1", "-1")]), LINES.om),
        gate("soft", aggregate([item("M-1", "-1")]), LINES.pm),
        pm_gate="soft",
        soft_acknowledged=False,
        blocking=(),
        unbanded=(),
    )
    assert conclusion_blockers(clear, "not_material") == ()
    assert conclusion_blockers(clear, "material") == ()


def test_the_strategy_trigger_needs_a_declared_band_and_fires_at_or_above_it() -> None:
    from oak_misstatements.core.gates import strategy_trigger

    total = aggregate([item("M-1", "-300000")])
    unset = strategy_trigger(total, LINES.om, None)
    assert (unset.status, unset.line, unset.fires_on) == ("not_configured", None, ())
    assert strategy_trigger(total, None, Decimal("0.75")).status == "no_thresholds"
    fires = strategy_trigger(total, LINES.om, Decimal("0.75"))
    assert (fires.status, fires.line) == ("fires", Decimal("300000.00"))
    assert fires.fires_on == ("profit.gross", "profit.net", "net_assets.gross", "net_assets.net")
    below = strategy_trigger(aggregate([item("M-1", "-299999.99")]), LINES.om, Decimal("0.75"))
    assert below.status == "clear"
    # The line is rounded to the paisa, half up, like every other line.
    odd = strategy_trigger(aggregate([]), Decimal("1000.30"), Decimal("0.75"))
    assert odd.line == Decimal("750.23")  # 750.225, half up
    short = aggregate([item("M-1", "-1"), item("M-2", None, "0", band=None)])
    assert strategy_trigger(short, LINES.om, Decimal("0.75")).status == "indeterminate"
