"""The state machine of a misstatement (spec section 3.3; acceptance 3 and 11; D41). Pure.

    raised -> communicated -> corrected      -> posted to the Spine
                           -> refused        -> uncorrected schedule
                           -> withdrawn      -> kept, excluded, with a reason

Corrected and uncorrected are states, not categories: the same record moves, by a new
append-only version each time, and nothing is deleted. ``corrected``, ``refused`` and
``withdrawn`` are final: the Spine decides an adjustment once
(``D:\\CAF\\backend\\src\\oak_spine\\spine\\adjustments.py``, ``decide``), so a decision here
cannot be taken back there.

What each final state asks of the Financial Spine, using only what its contract offers
(``POST /api/spine-versions/{id}/adjustments/{id}/decision`` with ``accepted`` or ``refused``
and a note):

- ``corrected``: ``accepted``. The adjustment posts to the chain and the adjusted trial
  balance moves (acceptance 11).
- ``refused``: ``refused``, with management's reason as the note. The Spine keeps a refused
  correction in its own uncorrected schedule; nothing posts.
- ``withdrawn``: ``refused``, with a note that says it was withdrawn by the auditor and why.
  The Spine has no withdrawn status (pending decision B1), and a proposal left open could
  later be accepted there and post an item this module says was withdrawn. Refusing it makes
  that impossible. The Spine's own aggregate still counts it, which is B1's open question.
"""

from __future__ import annotations

from typing import Literal

from oak_misstatements.errors import Conflict

State = Literal["raised", "communicated", "corrected", "refused", "withdrawn"]
Target = Literal["communicated", "corrected", "refused", "withdrawn"]
SpineDecision = Literal["accepted", "refused"]

TRANSITIONS: dict[str, frozenset[str]] = {
    "raised": frozenset({"communicated"}),
    "communicated": frozenset({"corrected", "refused", "withdrawn"}),
    "corrected": frozenset(),
    "refused": frozenset(),
    "withdrawn": frozenset(),
}
FINAL = frozenset({"corrected", "refused", "withdrawn"})
REASON_REQUIRED = frozenset({"refused", "withdrawn"})
SPINE_DECISION: dict[str, SpineDecision] = {
    "corrected": "accepted",
    "refused": "refused",
    "withdrawn": "refused",
}
# The Spine's limit on a decision note (``api/spine.py``, ``Narration``).
SPINE_NOTE_LIMIT = 2000


def check_transition(current: str, to: str) -> None:
    """Refuse any move the diagram does not draw, saying what is allowed from here."""
    allowed = TRANSITIONS.get(current, frozenset())
    if to in allowed:
        return
    if current in FINAL:
        raise Conflict(
            f"this misstatement is {current}, a final state: nothing follows it (spec section "
            "3.3). Raise a new misstatement if the facts have changed"
        )
    raise Conflict(
        f"a {current} misstatement cannot become {to}; from {current} the only move is to "
        + " or ".join(sorted(allowed))
        + " (spec section 3.3)"
    )


def expected_spine_status(state: str) -> str:
    """The status the Spine's adjustment has when the two modules agree."""
    return SPINE_DECISION.get(state, "proposed")


def decision_note(to: str, ref: str, actor: str, reason: str | None) -> str:
    """What the Spine records with the decision. It names our reference and who acted here,
    because the Spine records its own service identity as ``decided_by``."""
    if to == "corrected":
        note = f"{ref} corrected: accepted by {actor} in the Misstatements Rollup"
    elif to == "refused":
        note = f"{ref} refused by management: {reason} (recorded by {actor})"
    elif to == "withdrawn":
        note = (
            f"{ref} WITHDRAWN by the auditor, not a management refusal: {reason} "
            f"(recorded by {actor})"
        )
    else:
        raise ValueError(f"{to} asks nothing of the Spine")
    if len(note) > SPINE_NOTE_LIMIT:
        raise ValueError("the decision note exceeds the Spine's limit")
    return note
