"""The qualitative checklist (spec section 5; acceptance 8; architecture D59). Pure.

"A misstatement below the threshold can still be material by nature." The specification
turns the circumstances SA 450 lists into a checklist against each item, "any one of which
escalates it with a recorded reason", and "an escalated item is listed individually
regardless of size". Which factors apply is a person's judgement: nothing here detects one
(spec section 12).
"""

from __future__ import annotations

from typing import Final

# The seven factors, in the specification's order and in its words.
FACTORS: Final[dict[str, str]] = {
    "law_or_covenant": "affects compliance with a law, regulation or loan covenant",
    "earnings_trend": "masks a change in earnings or a trend",
    "ratio": (
        "changes a ratio used to evaluate the entity, including the eleven Schedule III ratios"
    ),
    "fraud": "relates to a fraud or a suspected fraud",
    "related_party": "relates to a related party transaction",
    "segment_or_remuneration": "affects segment information, or management remuneration",
    "loss_to_profit": "turns a loss into a profit, or the reverse",
}
FACTOR_KEYS: Final[tuple[str, ...]] = tuple(FACTORS)

ESCALATION_BASIS: Final[str] = (
    "an item is escalated while at least one factor of the qualitative checklist is recorded "
    "against it, each with its reason (spec section 5); an escalated item is listed "
    "individually regardless of its size (acceptance 8) and is accumulated whatever its band, "
    "because a matter is clearly trivial only when it is clearly inconsequential 'whether "
    "judged by any criteria of size, nature or circumstances' (SA 450 paragraph A2; register "
    "F5; architecture D59); which factors apply is a person's judgement and is never detected "
    "(spec section 12)"
)


def ordered(factors: set[str] | frozenset[str]) -> tuple[str, ...]:
    """The given factors in the checklist's order."""
    return tuple(key for key in FACTOR_KEYS if key in factors)
