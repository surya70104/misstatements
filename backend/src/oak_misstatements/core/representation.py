"""The written representation attachment (SA 450 paragraph 14; spec section 2 row 14,
section 6 item 3; architecture D63). Pure.

"Written representation that management and TCWG believe the effects are immaterial, with
the summary attached" (spec section 2). "The written representation attachment: the summary
in the form that attaches to the representation letter" (spec section 6).

The attachment is the summary of uncorrected misstatements, and with it the statement
management is asked to make. Two things follow from whose statement it is:

- the statement is **management's belief**, requested by the auditor. It is never the
  auditor's conclusion, and it changes nothing in the evaluation: the gates and the
  partner's conclusion stand as they are, whatever is represented;
- so where the evaluation does not sit with such a belief, the attachment says so to the
  auditor, as a caution beside the document and never inside it.

The summary lists every uncorrected misstatement that is accumulated (raised, communicated
or refused; the aggregate's own reading), set out by type, the three kept apart as spec
section 3.2 keeps them. A misstatement below the clearly-trivial threshold and not
accumulated is outside it (spec section 4), as it is outside the TCWG extract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from oak_misstatements.core.gates import Aggregate, Item

REPRESENTATION_TEXT: Final[str] = (
    "Management and those charged with governance believe that the effects of the "
    "uncorrected misstatements summarised in this schedule are immaterial, individually and "
    "in aggregate, to the financial statements as a whole."
)
REPRESENTATION_BASIS: Final[str] = (
    "SA 450 paragraph 14: the auditor requests a written representation from management "
    "and, where appropriate, those charged with governance whether they believe the effects "
    "of uncorrected misstatements are immaterial, individually and in aggregate, to the "
    "financial statements as a whole, and a summary of those items is included in or "
    "attached to the representation (spec section 2, row 14; section 6, item 3). The "
    "sentence is the standard's requirement put plainly. It is management's belief, not the "
    "auditor's conclusion, and it changes nothing in the evaluation. The firm's own wording "
    "of the representation letter is the firm's"
)
NOTHING_TO_REPRESENT: Final[str] = (
    "No uncorrected misstatement is accumulated, so there is no summary to attach to the "
    "written representation."
)

ATTACHMENT_BASIS: Final[str] = (
    "the summary of uncorrected misstatements in the form that attaches to the written "
    "representation (SA 450 paragraph 14; spec section 6, item 3): every uncorrected "
    "misstatement that is accumulated (raised, communicated or refused; the F3 reading), "
    "listed by type, the three kept apart (spec section 3.2), each with its effect on "
    "profit before tax and, separately, on net assets; each type and the whole are summed "
    "gross, with no netting between misstatements, and net, signed (spec section 4.1); the "
    "whole is the evaluation's own aggregate, so the attachment and the evaluation cannot "
    "differ; a misstatement below the clearly-trivial threshold and not accumulated is "
    "outside the summary (spec section 4); corrected and withdrawn items are not "
    "uncorrected; prior-period items carried forward are shown with their current-period "
    "and cumulative effects, apart from the totals (SA 450 paragraph 11(b); architecture "
    "D61); the cautions are for the auditor and are not part of the attachment "
    "(architecture D63)"
)

# The cautions, by code. Each is a fact of the evaluation as it stands, put beside the
# attachment for the auditor. None changes the attachment or blocks it.
NOT_COMMUNICATED: Final[str] = "not_communicated"
NAMED_INDIVIDUALLY: Final[str] = "named_individually"
OPINION_BLOCKED: Final[str] = "opinion_blocked"
OPINION_UNDETERMINED: Final[str] = "opinion_undetermined"
CONCLUDED_MATERIAL: Final[str] = "concluded_material"
NO_CURRENT_RUN: Final[str] = "no_current_run"
PRIOR_PERIOD_REACHES: Final[str] = "prior_period_reaches"


@dataclass(frozen=True, slots=True)
class Summary:
    """Where each uncorrected misstatement falls for the attachment."""

    listed: tuple[Item, ...]  # accumulated, with known effects: in the summary
    undetermined: tuple[Item, ...]  # effects not known: named, and the summary is short
    left_out: tuple[Item, ...]  # clearly trivial and not accumulated: outside it


def summary(items: list[Item], aggregate: Aggregate) -> Summary:
    """Place every uncorrected misstatement. What is listed is exactly what the aggregate
    counts, so the summary's totals are the aggregate's."""
    counted = set(aggregate.counted)
    left_out = set(aggregate.not_accumulated)
    listed: list[Item] = []
    undetermined: list[Item] = []
    trivial: list[Item] = []
    for item in items:
        if not item.uncorrected:
            continue
        if item.ref in counted:
            listed.append(item)
        elif item.ref in left_out:
            trivial.append(item)
        else:
            undetermined.append(item)
    return Summary(tuple(listed), tuple(undetermined), tuple(trivial))
