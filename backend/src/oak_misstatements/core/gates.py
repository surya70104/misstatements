"""The aggregate and the gates (spec sections 4.1 and 7, section 3.2 on projected items,
acceptance 4, 6 and 7; architecture D38). Pure: no database, no HTTP.

**What is aggregated.** Every misstatement whose current state is not ``corrected`` and not
``withdrawn`` is uncorrected (the F3 reading: raised, communicated, refused). Each one
contributes its effect on profit before tax and, separately, its effect on net assets
(section 4.1: "profit and net assets, separately"). Each measure is summed two ways
(section 4.1: "gross and net, both shown"): **gross**, the sum of absolute effects with no
netting between misstatements, and **net**, the signed sum. A classification-only item
contributes nil to both and is listed; its gross size is shown beside it.

**Clearly trivial items are not accumulated** (spec section 2, the row for SA 450 paragraph
5: "everything above it accumulates"; section 4: "Below it, not accumulated"; architecture
D53). An uncorrected item whose band is clearly trivial is left out of every sum and named
in ``not_accumulated``; it stays in the schedule and in the list of items. The band is the
item's own (D33: the higher of its two effects' bands, an assumption), so an item is in the
aggregate with both effects or with neither. A classification-only item bands clearly
trivial only because both effects are nil; it stays listed at nil as before (B2). With no
thresholds there is no band and nothing is left out, and no gate is evaluated either.

**Projected items** (section 3.2: "never aggregated as if it were factual without saying
so"; pending decision B8). Every aggregate is given twice: with every accumulated item, and
without the projected ones. Every gate is tested on both and says whether it depends on the
projected items. The interim treatment is that projected amounts **count**, the conservative
reading, and that the dependence is always disclosed; whether they should count is B8's,
and this module never answers it silently.

**The gates** (section 7). Each gate compares every measure (profit and net assets, gross
and the absolute net) against its line; it fires when any measure is at or above the line
(lines 139 and 141: "at or above"), and names the measures that reached it. The hard gate's
line is overall materiality; the soft gate's is performance materiality.

**Unresolved items.** An uncorrected item whose effects cannot be determined (D31, D32)
cannot be aggregated. It is named, the aggregate is marked incomplete, and a gate that does
not already fire on the known items is ``indeterminate``, which blocks exactly as firing
does: nothing is signed off on a figure that is known to be short.

**Individually significant items** (section 7, acceptance 6): any uncorrected item whose
band is individually significant blocks sign-off while it is raised or communicated; a
refusal with a reason, a correction or a withdrawal releases it. An item that cannot be
banded while raised or communicated blocks for the same reason an incomplete aggregate does.

**Blocking is in the write path** (line 149): ``sign_off`` is the one decision every write
that amounts to signing off must consult, and it fails closed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from oak_misstatements.core.banding import Band, Lines
from oak_misstatements.core.states import expected_spine_status

ZERO = Decimal("0.00")

UNCORRECTED_STATES = frozenset({"raised", "communicated", "refused"})  # F3 reading
BLOCKING_STATES = frozenset({"raised", "communicated"})  # spec section 7, acceptance 6
GateName = Literal["hard", "soft"]
GateStatus = Literal["fires", "clear", "indeterminate", "no_thresholds"]

AGGREGATE_BASIS = (
    "every misstatement not corrected and not withdrawn (raised, communicated, refused; the "
    "F3 reading) that is not clearly trivial contributes its effect on profit before tax and, "
    "separately, on net assets; an item whose band is clearly trivial is not accumulated and "
    "is named (spec section 4: 'below it, not accumulated'; the band is the item's, the "
    "higher of its two effects' bands; architecture D33, D53), unless the clearly trivial "
    "items together reach the clearly-trivial threshold, gross, on either measure, when all "
    "of them are accumulated (SA 450 paragraph A2: clearly trivial matters are clearly "
    "inconsequential 'whether taken individually or in aggregate'; architecture D57); an "
    "escalated item, one with a qualitative factor recorded, is accumulated whatever its "
    "band and listed individually (spec section 5; acceptance 8; architecture D59); "
    "gross sums absolute effects with no netting between misstatements, net sums them signed "
    "(spec section 4.1); each is given with and without the projected items (spec section "
    "3.2; pending decision B8); a classification-only item contributes nil and is listed; an "
    "item whose effects are unresolved is named and the aggregate marked incomplete "
    "(architecture D38)"
)
GATE_BASIS = (
    "fires when any measure (profit or net assets, gross or the absolute net) is at or above "
    "the line (spec section 7, 'at or above'); tested with and without the projected items, "
    "and says whether it depends on them (pending decision B8); indeterminate when the known "
    "items do not reach the line but an uncorrected item could not be aggregated "
    "(architecture D38)"
)


@dataclass(frozen=True, slots=True)
class Item:
    """One misstatement's current version as the aggregate sees it."""

    misstatement_id: uuid.UUID
    ref: str
    type: str  # factual | judgemental | projected
    state: str
    profit: Decimal | None
    net_assets: Decimal | None
    classification_only: bool
    band: Band | None
    refusal_reason: str | None = None
    spine_adjustment_status: str | None = None  # None when the Spine could not be read
    escalated: bool = False  # a factor of the qualitative checklist is recorded (D59)

    @property
    def uncorrected(self) -> bool:
        return self.state in UNCORRECTED_STATES

    @property
    def resolved(self) -> bool:
        return self.profit is not None and self.net_assets is not None

    @property
    def projected(self) -> bool:
        return self.type == "projected"


@dataclass(frozen=True, slots=True)
class Measure:
    """One of the two measures, summed both ways, with and without the projected items."""

    gross: Decimal
    net: Decimal
    gross_without_projected: Decimal
    net_without_projected: Decimal
    projected_gross: Decimal
    factual_gross: Decimal = ZERO
    judgemental_gross: Decimal = ZERO

    def highest(self, *, with_projected: bool) -> Decimal:
        if with_projected:
            return max(self.gross, abs(self.net))
        return max(self.gross_without_projected, abs(self.net_without_projected))


@dataclass(frozen=True, slots=True)
class Aggregate:
    profit: Measure
    net_assets: Measure
    counted: tuple[str, ...]  # refs that contributed
    projected: tuple[str, ...]  # the projected items among them
    classification_only: tuple[str, ...]  # listed, nil contribution
    unresolved: tuple[str, ...]  # uncorrected items that could not be aggregated
    excluded: tuple[tuple[str, str], ...]  # (ref, state) of corrected and withdrawn items
    not_accumulated: tuple[str, ...] = ()  # uncorrected and clearly trivial: named, never summed
    # What the items that are clearly trivial one by one come to together, gross (D56, D57).
    left_out_profit: Decimal = ZERO
    left_out_net_assets: Decimal = ZERO
    # Clearly trivial one by one, accumulated because together they reach CTT (D57).
    accumulated_together: tuple[str, ...] = ()
    # Uncorrected items with a qualitative factor recorded: listed individually (D59).
    escalated: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.unresolved


def _measure(items: list[Item], pick: str) -> Measure:
    gross = net = gross_wo = net_wo = ZERO
    by_type = {"factual": ZERO, "judgemental": ZERO, "projected": ZERO}
    for item in items:
        value = getattr(item, pick)
        assert value is not None  # noqa: S101 - callers pass resolved items only
        gross += abs(value)
        net += value
        by_type[item.type] = by_type.get(item.type, ZERO) + abs(value)
        if not item.projected:
            gross_wo += abs(value)
            net_wo += value
    return Measure(
        gross,
        net,
        gross_wo,
        net_wo,
        by_type["projected"],
        by_type["factual"],
        by_type["judgemental"],
    )


def accumulates(item: Item) -> bool:
    """Spec section 4: below the clearly-trivial threshold, not accumulated (D53). The band
    is the item's own, so an item with no band (no thresholds) is not left out, and neither
    is a classification-only item, which is listed at nil whatever its band (B2). An
    escalated item is never left out either: a matter is clearly trivial only when it is
    clearly inconsequential by "size, nature or circumstances" (SA 450 paragraph A2), and a
    recorded qualitative factor says its nature is not (spec section 5; F5; D59)."""
    return item.band is not Band.CLEARLY_TRIVIAL or item.classification_only or item.escalated


def aggregate(items: list[Item], ctt: Decimal | None = None) -> Aggregate:
    """The aggregate of the uncorrected misstatements. ``ctt`` is the clearly-trivial
    threshold when there is one.

    SA 450 paragraph A2 (D57): matters are clearly trivial only where they are "clearly
    inconsequential, whether taken individually or in aggregate", and "when there is any
    uncertainty about whether one or more items are clearly trivial, the matter is
    considered not to be clearly trivial". So the items that band clearly trivial one by
    one are totalled, gross, on each measure. While that total is below CTT on both
    measures they are left out and named. Once it reaches CTT on either, it can no longer
    be said that together they are below the amount designated as clearly trivial, and
    all of them are accumulated."""
    uncorrected = [item for item in items if item.uncorrected]
    resolved = [item for item in uncorrected if item.resolved]
    trivial = [item for item in resolved if not accumulates(item)]
    trivial_profit = sum((abs(item.profit or ZERO) for item in trivial), ZERO)
    trivial_net_assets = sum((abs(item.net_assets or ZERO) for item in trivial), ZERO)
    together = ctt is not None and max(trivial_profit, trivial_net_assets) >= ctt
    accumulated = [item for item in resolved if together or accumulates(item)]
    left_out = [] if together else trivial
    return Aggregate(
        profit=_measure(accumulated, "profit"),
        net_assets=_measure(accumulated, "net_assets"),
        counted=tuple(item.ref for item in accumulated),
        projected=tuple(item.ref for item in accumulated if item.projected),
        classification_only=tuple(item.ref for item in accumulated if item.classification_only),
        unresolved=tuple(item.ref for item in uncorrected if not item.resolved),
        excluded=tuple((item.ref, item.state) for item in items if not item.uncorrected),
        not_accumulated=tuple(item.ref for item in left_out),
        left_out_profit=trivial_profit,
        left_out_net_assets=trivial_net_assets,
        accumulated_together=tuple(item.ref for item in trivial) if together else (),
        escalated=tuple(item.ref for item in uncorrected if item.escalated),
    )


@dataclass(frozen=True, slots=True)
class GateResult:
    name: GateName
    line: Decimal | None
    status: GateStatus
    fires_on: tuple[str, ...]  # "profit.gross", "profit.net", "net_assets.gross", ...
    fires_without_projected: bool | None
    depends_on_projected: bool
    highest: Decimal | None
    basis: str

    @property
    def blocks(self) -> bool:
        """Fail closed: firing and not knowing both block."""
        return self.status != "clear"


def _reached(total: Aggregate, line: Decimal, *, with_projected: bool) -> tuple[str, ...]:
    reached: list[str] = []
    for label, measure in (("profit", total.profit), ("net_assets", total.net_assets)):
        gross = measure.gross if with_projected else measure.gross_without_projected
        net = measure.net if with_projected else measure.net_without_projected
        if gross >= line:
            reached.append(f"{label}.gross")
        if abs(net) >= line:
            reached.append(f"{label}.net")
    return tuple(reached)


def gate(name: GateName, total: Aggregate, line: Decimal | None) -> GateResult:
    if line is None:
        return GateResult(name, None, "no_thresholds", (), None, False, None, GATE_BASIS)
    fires_on = _reached(total, line, with_projected=True)
    without = bool(_reached(total, line, with_projected=False))
    highest = max(
        total.profit.highest(with_projected=True), total.net_assets.highest(with_projected=True)
    )
    if fires_on:
        status: GateStatus = "fires"
    elif not total.complete:
        status = "indeterminate"
    else:
        status = "clear"
    return GateResult(
        name=name,
        line=line,
        status=status,
        fires_on=fires_on,
        fires_without_projected=without,
        depends_on_projected=bool(fires_on) and not without,
        highest=highest,
        basis=GATE_BASIS,
    )


def blocking_items(items: list[Item]) -> tuple[Item, ...]:
    """Section 7: an item above PM blocks until corrected, refused with a reason or
    withdrawn. A refused item without a reason still blocks (acceptance 3)."""
    found: list[Item] = []
    for item in items:
        if item.band is not Band.INDIVIDUALLY_SIGNIFICANT:
            continue
        if item.state in BLOCKING_STATES or (
            item.state == "refused" and not (item.refusal_reason or "").strip()
        ):
            found.append(item)
    return tuple(found)


INDIVIDUAL_BASIS = (
    "every uncorrected item whose band is individually significant (above PM; spec section "
    "4), whatever its state, a refused one included; and, among all uncorrected items, those "
    "whose own effect on profit before tax or on net assets is at or above overall "
    "materiality (SA 450 paragraph 11: material individually or in aggregate, both tests "
    "shown; architecture D43)"
)


def individually_significant_items(items: list[Item]) -> tuple[Item, ...]:
    """The individual test (SA 450 paragraph 11; spec section 4): every uncorrected item
    banded above PM. Unlike ``blocking_items`` this keeps a refused item: refusing with a
    reason releases the block on sign-off, it does not make the item less significant."""
    return tuple(
        item for item in items if item.uncorrected and item.band is Band.INDIVIDUALLY_SIGNIFICANT
    )


def items_at_or_above(items: list[Item], line: Decimal | None) -> tuple[Item, ...]:
    """Uncorrected items whose own effect, on either measure, is at or above ``line``."""
    if line is None:
        return ()
    return tuple(
        item
        for item in items
        if item.uncorrected
        and item.profit is not None
        and item.net_assets is not None
        and max(abs(item.profit), abs(item.net_assets)) >= line
    )


def unbanded_items(items: list[Item]) -> tuple[Item, ...]:
    """Uncorrected items that could not be banded while still raised or communicated: no one
    knows whether they are above PM, so they block like an incomplete aggregate."""
    return tuple(item for item in items if item.band is None and item.state in BLOCKING_STATES)


# Why a reason blocks (D45). A MATERIALITY reason says the misstatements have reached a
# line: it blocks a conclusion that they are not material, and nothing else. A READINESS
# reason says the evaluation is unknown or unfinished: it blocks every conclusion.
MATERIALITY = "materiality"
READINESS = "readiness"
Determination = Literal["not_material", "material"]


@dataclass(frozen=True, slots=True)
class SignOff:
    blocked: bool
    reasons: tuple[str, ...]
    kinds: tuple[str, ...] = ()  # parallel to ``reasons``: MATERIALITY or READINESS


def inconsistent_items(items: list[Item]) -> tuple[Item, ...]:
    """Items whose state here and whose adjustment in the Spine disagree (D41): corrected
    here but not accepted there, or uncorrected here but accepted (and so posted) there.
    Neither module is believed over the other; the disagreement blocks until a person
    reconciles it."""
    return tuple(
        item
        for item in items
        if item.spine_adjustment_status is not None
        and item.spine_adjustment_status != expected_spine_status(item.state)
    )


def sign_off(
    hard: GateResult,
    soft: GateResult,
    *,
    pm_gate: Literal["soft", "hard"],
    soft_acknowledged: bool,
    blocking: tuple[Item, ...],
    unbanded: tuple[Item, ...],
    inconsistent: tuple[Item, ...] = (),
) -> SignOff:
    """The one decision a write that amounts to signing off must consult (spec line 149).
    Fails closed: no thresholds, an indeterminate gate and an unbanded item all block."""
    found: list[tuple[str, str]] = []
    if hard.status == "no_thresholds":
        found.append((READINESS, "no thresholds have been set, so no gate can be evaluated"))
    if hard.status == "fires":
        found.append(
            (
                MATERIALITY,
                "hard gate: aggregate uncorrected misstatements at or above overall "
                "materiality on "
                + ", ".join(hard.fires_on)
                + (
                    " (only with the projected items; pending decision B8)"
                    if hard.depends_on_projected
                    else ""
                ),
            )
        )
    elif hard.status == "indeterminate":
        found.append(
            (READINESS, "hard gate indeterminate: an uncorrected item could not be aggregated")
        )
    if soft.status == "fires":
        if pm_gate == "hard":
            found.append(
                (
                    MATERIALITY,
                    "PM gate (set to hard by the firm, OAK_PM_GATE): aggregate at or above "
                    "performance materiality on " + ", ".join(soft.fires_on),
                )
            )
        elif not soft_acknowledged:
            found.append(
                (
                    MATERIALITY,
                    "soft gate: aggregate at or above performance materiality on "
                    + ", ".join(soft.fires_on)
                    + " and the partner has not acknowledged these figures",
                )
            )
    elif soft.status == "indeterminate":
        found.append(
            (READINESS, "soft gate indeterminate: an uncorrected item could not be aggregated")
        )
    for item in blocking:
        found.append(
            (
                READINESS,
                f"{item.ref} is individually significant and {item.state}"
                + (" (projected)" if item.projected else ""),
            )
        )
    for item in unbanded:
        found.append((READINESS, f"{item.ref} is {item.state} and cannot be banded"))
    for item in inconsistent:
        found.append(
            (
                READINESS,
                f"{item.ref} is {item.state} here but its adjustment is "
                f"{item.spine_adjustment_status} in the Financial Spine",
            )
        )
    return SignOff(
        blocked=bool(found),
        reasons=tuple(reason for _kind, reason in found),
        kinds=tuple(kind for kind, _reason in found),
    )


def conclusion_blockers(decision: SignOff, determination: Determination) -> tuple[str, ...]:
    """What stops a conclusion (D45). *Not material* is what an unmodified opinion rests on,
    so every reason blocks it. *Material* records that the misstatements are material: a
    gate that fires is its subject, not its obstacle, so only the reasons that leave the
    evaluation unknown or unfinished block it (spec section 7: the hard gate blocks an
    unmodified opinion; acceptance 6: an item above PM blocks until it is dealt with)."""
    if determination == "not_material":
        return decision.reasons
    return tuple(
        reason
        for kind, reason in zip(decision.kinds, decision.reasons, strict=True)
        if kind == READINESS
    )


StrategyStatus = Literal["not_configured", "no_thresholds", "clear", "fires", "indeterminate"]


@dataclass(frozen=True, slots=True)
class StrategyTrigger:
    """Spec section 7 and SA 450 paragraph 6: the aggregate approaching materiality."""

    status: StrategyStatus
    fraction: Decimal | None
    line: Decimal | None
    fires_on: tuple[str, ...]
    highest: Decimal | None


def strategy_trigger(
    total: Aggregate, om: Decimal | None, fraction: Decimal | None
) -> StrategyTrigger:
    """Fires when any measure is at or above ``fraction`` of overall materiality. With no
    fraction declared it is not evaluated: the band is pending decision B5 and none is
    assumed. It is a prompt, never a block."""
    if fraction is None:
        return StrategyTrigger("not_configured", None, None, (), None)
    if om is None:
        return StrategyTrigger("no_thresholds", fraction, None, (), None)
    line = (om * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fires_on = _reached(total, line, with_projected=True)
    highest = max(
        total.profit.highest(with_projected=True), total.net_assets.highest(with_projected=True)
    )
    if fires_on:
        status: StrategyStatus = "fires"
    elif not total.complete:
        status = "indeterminate"
    else:
        status = "clear"
    return StrategyTrigger(status, fraction, line, fires_on, highest)


def lines_or_none(lines: Lines | None) -> tuple[Decimal | None, Decimal | None]:
    return (None, None) if lines is None else (lines.om, lines.pm)


# ---- gate exposure (architecture D18, D46) --------------------------------------------------

Exposure = Literal["open", "blocked", "undetermined"]

OPINION_GATE_SCOPE = (
    "whether an unmodified opinion is blocked by the size of the uncorrected misstatements: "
    "the hard gate at overall materiality (spec section 7), and the gate at performance "
    "materiality when the firm has set it to hard. It says nothing about items above PM not "
    "yet dealt with or about the partner's acknowledgement: the sign-off gate does"
)
SIGN_OFF_GATE_SCOPE = (
    "whether sign-off is blocked for any reason this module knows: the hard gate, the soft "
    "gate without a current partner acknowledgement, an item above PM still raised or "
    "communicated (spec section 7; acceptance 6 and 7)"
)


@dataclass(frozen=True, slots=True)
class GateExposure:
    """What another module is told (D18): open, blocked or undetermined, with why. Blocked
    wins over undetermined: a gate that already fires on what is known is blocked, whatever
    else is unknown. Neither blocked nor open is ever reported on a guess."""

    status: Exposure
    blocked_by: tuple[str, ...]
    undetermined_because: tuple[str, ...]


def _unknowns(
    hard: GateResult,
    soft: GateResult,
    unbanded: tuple[Item, ...],
    inconsistent: tuple[Item, ...],
    *,
    soft_matters: bool,
) -> list[str]:
    found: list[str] = []
    if hard.status == "no_thresholds":
        found.append("no thresholds have been set")
    if hard.status == "indeterminate":
        found.append("an uncorrected item could not be aggregated against overall materiality")
    if soft_matters and soft.status == "indeterminate":
        found.append("an uncorrected item could not be aggregated against performance materiality")
    found.extend(f"{item.ref} is {item.state} and cannot be banded" for item in unbanded)
    found.extend(
        f"{item.ref} is {item.state} here but {item.spine_adjustment_status} in the Financial Spine"
        for item in inconsistent
    )
    return found


def opinion_gate(
    hard: GateResult,
    soft: GateResult,
    *,
    pm_gate: Literal["soft", "hard"],
    unbanded: tuple[Item, ...] = (),
    inconsistent: tuple[Item, ...] = (),
) -> GateExposure:
    blocked: list[str] = []
    if hard.status == "fires":
        blocked.append(
            "aggregate uncorrected misstatements at or above overall materiality on "
            + ", ".join(hard.fires_on)
            + (
                " (only with the projected items; pending decision B8)"
                if hard.depends_on_projected
                else ""
            )
        )
    if pm_gate == "hard" and soft.status == "fires":
        blocked.append(
            "aggregate at or above performance materiality on "
            + ", ".join(soft.fires_on)
            + ", which the firm has set as a hard gate (OAK_PM_GATE)"
        )
    unknown = _unknowns(hard, soft, unbanded, inconsistent, soft_matters=pm_gate == "hard")
    status: Exposure = "blocked" if blocked else ("undetermined" if unknown else "open")
    return GateExposure(status, tuple(blocked), tuple(unknown))


def sign_off_gate(
    decision: SignOff,
    hard: GateResult,
    soft: GateResult,
    *,
    unbanded: tuple[Item, ...] = (),
    inconsistent: tuple[Item, ...] = (),
) -> GateExposure:
    """The sign-off decision as open, blocked or undetermined. Every reason of ``decision``
    is either one of the unknowns named here or a known block; the two are told apart by
    their text, which both functions build from the same inputs."""
    unknown = _unknowns(hard, soft, unbanded, inconsistent, soft_matters=True)
    unknown_reasons = set()
    if hard.status == "no_thresholds":
        unknown_reasons.add("no thresholds have been set, so no gate can be evaluated")
    if hard.status == "indeterminate":
        unknown_reasons.add("hard gate indeterminate: an uncorrected item could not be aggregated")
    if soft.status == "indeterminate":
        unknown_reasons.add("soft gate indeterminate: an uncorrected item could not be aggregated")
    unknown_reasons.update(f"{item.ref} is {item.state} and cannot be banded" for item in unbanded)
    unknown_reasons.update(
        f"{item.ref} is {item.state} here but its adjustment is "
        f"{item.spine_adjustment_status} in the Financial Spine"
        for item in inconsistent
    )
    blocked = tuple(reason for reason in decision.reasons if reason not in unknown_reasons)
    status: Exposure = "blocked" if blocked else ("undetermined" if unknown else "open")
    return GateExposure(status, blocked, tuple(unknown))
