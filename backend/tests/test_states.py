"""The state machine as a table (spec section 3.3; D41): which moves exist, what each asks
of the Spine, and the note the Spine is given."""

from __future__ import annotations

import pytest

from oak_misstatements.core.states import (
    FINAL,
    REASON_REQUIRED,
    SPINE_DECISION,
    SPINE_NOTE_LIMIT,
    TRANSITIONS,
    check_transition,
    decision_note,
    expected_spine_status,
)
from oak_misstatements.errors import Conflict
from oak_misstatements.models.misstatement import STATES

ALLOWED = {
    ("raised", "communicated"),
    ("communicated", "corrected"),
    ("communicated", "refused"),
    ("communicated", "withdrawn"),
}


def test_the_table_covers_the_five_states_and_only_the_diagrams_moves() -> None:
    assert set(TRANSITIONS) == set(STATES)
    assert {(a, b) for a, targets in TRANSITIONS.items() for b in targets} == ALLOWED
    assert frozenset({"corrected", "refused", "withdrawn"}) == FINAL
    assert frozenset({"refused", "withdrawn"}) == REASON_REQUIRED


@pytest.mark.parametrize("current", STATES)
@pytest.mark.parametrize("to", STATES)
def test_every_pair_is_allowed_or_refused_exactly_as_the_diagram_says(
    current: str, to: str
) -> None:
    if (current, to) in ALLOWED:
        check_transition(current, to)
        return
    with pytest.raises(Conflict) as refused:
        check_transition(current, to)
    assert "spec section 3.3" in str(refused.value)
    if current in FINAL:
        assert "final state" in str(refused.value)
    else:
        assert "the only move is to" in str(refused.value)


def test_what_each_final_state_asks_of_the_spine() -> None:
    assert SPINE_DECISION == {"corrected": "accepted", "refused": "refused", "withdrawn": "refused"}
    assert expected_spine_status("raised") == "proposed"
    assert expected_spine_status("communicated") == "proposed"
    assert expected_spine_status("corrected") == "accepted"
    assert expected_spine_status("refused") == "refused"
    assert expected_spine_status("withdrawn") == "refused"


def test_the_note_names_our_reference_the_actor_and_the_reason() -> None:
    corrected = decision_note("corrected", "M-3", "manager@firm", None)
    assert "M-3" in corrected and "manager@firm" in corrected
    refused = decision_note("refused", "M-3", "manager@firm", "immaterial in their view")
    assert "refused by management: immaterial in their view" in refused
    withdrawn = decision_note("withdrawn", "M-3", "manager@firm", "raised in error")
    assert "WITHDRAWN by the auditor, not a management refusal: raised in error" in withdrawn
    with pytest.raises(ValueError, match="asks nothing"):
        decision_note("communicated", "M-3", "x", None)


def test_the_longest_reason_and_identity_still_fit_the_spines_limit() -> None:
    longest = decision_note("withdrawn", "M-999999", "u" * 254, "r" * 1500)
    assert len(longest) <= SPINE_NOTE_LIMIT
    with pytest.raises(ValueError, match="exceeds the Spine's limit"):
        decision_note("withdrawn", "M-1", "u", "r" * 2000)
