"""The written representation attachment (SA 450 paragraph 14; spec section 2 row 14,
section 6 item 3; architecture D63): the summary of uncorrected misstatements in the form
that attaches to the representation letter, with the statement management is asked to make.

Read-only and computed on every read from the evaluation as it stands, exactly as the
schedule, the gates and the TCWG extract compute it, so none of them can disagree with it.
Nothing is stored: the attachment is a view, not a record that a representation was given.

The statement is management's belief. It is not the auditor's conclusion and it changes
nothing in the evaluation. Where the evaluation does not sit with it, the answer says so in
``cautions``, which are for the auditor and are not part of the attachment."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from oak_misstatements.api.deps import SessionDep, SettingsDep, SpineDep
from oak_misstatements.api.tcwg import row_json, sums_json
from oak_misstatements.config import Settings
from oak_misstatements.core import representation as core
from oak_misstatements.core import tcwg
from oak_misstatements.core.gates import AGGREGATE_BASIS, opinion_gate
from oak_misstatements.schemas import amount
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.engagements import get_engagement
from oak_misstatements.services.evaluation import (
    Evaluation,
    evaluate,
    figures,
    not_accumulated_total,
)
from oak_misstatements.services.prior_period import evaluation_json as prior_period_json

router = APIRouter(tags=["rep-letter-attachment"])


def _incomplete_because(evaluation: Evaluation, summary: core.Summary) -> list[str]:
    reasons: list[str] = []
    if evaluation.threshold is None:
        reasons.append(
            "no thresholds have been set, so which misstatements are clearly trivial is not "
            "known and the uncorrected misstatements cannot be evaluated"
        )
    if summary.undetermined:
        reasons.append(
            "the effects of "
            + ", ".join(item.ref for item in summary.undetermined)
            + " cannot be determined, so the summary and its totals are short"
        )
    if evaluation.inconsistent:
        reasons.append(
            ", ".join(item.ref for item in evaluation.inconsistent)
            + " disagree with the Financial Spine about their state"
        )
    return reasons


def _cautions(
    evaluation: Evaluation, summary: core.Summary, settings: Settings
) -> list[dict[str, str]]:
    """Facts of the evaluation that the auditor should have in view before the attachment
    goes out. Each is information: none blocks the attachment or changes it."""
    found: list[dict[str, str]] = []

    def caution(code: str, text: str) -> None:
        found.append({"code": code, "text": text})

    raised = [item.ref for item in summary.listed + summary.undetermined if item.state == "raised"]
    if raised:
        caution(
            core.NOT_COMMUNICATED,
            ", ".join(raised)
            + (" is" if len(raised) == 1 else " are")
            + " raised and not yet recorded as communicated to management (SA 450 paragraph 8)",
        )
    om = None if evaluation.threshold is None else evaluation.threshold.om
    named = tcwg.extract(evaluation.items, evaluation.aggregate, om).named
    if named:
        caution(
            core.NAMED_INDIVIDUALLY,
            ", ".join(entry.item.ref for entry in named)
            + (" is" if len(named) == 1 else " are")
            + " above performance materiality or escalated on a qualitative factor, and "
            "named individually in the TCWG extract",
        )
    exposure = opinion_gate(
        evaluation.hard,
        evaluation.soft,
        pm_gate=settings.pm_gate,
        unbanded=evaluation.unbanded,
        inconsistent=evaluation.inconsistent,
    )
    if exposure.status == "blocked":
        caution(
            core.OPINION_BLOCKED,
            "an unmodified opinion is blocked: "
            + "; ".join(exposure.blocked_by)
            + ". A representation that the effects are immaterial is management's belief "
            "and does not change this",
        )
    elif exposure.status == "undetermined":
        caution(
            core.OPINION_UNDETERMINED,
            "whether an unmodified opinion is blocked cannot be determined: "
            + "; ".join(exposure.undetermined_because),
        )
    conclusion = evaluation.latest_conclusion
    if (
        conclusion is not None
        and conclusion.run is not None
        and conclusion.run.determination == "material"
    ):
        caution(
            core.CONCLUDED_MATERIAL,
            f"the partner's latest conclusion (run {conclusion.run.run_no}, {conclusion.status}) "
            "is that the uncorrected misstatements are material",
        )
    run = evaluation.latest_run
    # Only where there is a summary to attach: with nothing accumulated there are no
    # figures for a run to record.
    has_summary = bool(summary.listed) or bool(summary.undetermined)
    if has_summary and (run is None or run.status != "current"):
        caution(
            core.NO_CURRENT_RUN,
            (
                "no evaluation run records these figures"
                if run is None or run.run is None
                else f"the latest evaluation run (run {run.run.run_no}) no longer records "
                f"these figures: {run.detail}"
            ),
        )
    return found


def _prior_period_caution(prior: dict[str, Any], evaluation: Evaluation) -> list[dict[str, str]]:
    """A line that the current year's aggregate does not reach, and that the figures with
    the prior-period items do. Where the current year reaches it alone, the gate says so."""
    reaches = prior["reaches"]
    if reaches is None or not prior["items"]:
        return []
    for line, name, gate in (
        ("om", "overall materiality", evaluation.hard),
        ("pm", "performance materiality", evaluation.soft),
    ):
        if gate.status == "fires":
            continue
        bases = [basis.replace("_", "-") for basis in reaches if reaches[basis][line]]
        if bases:
            return [
                {
                    "code": core.PRIOR_PERIOD_REACHES,
                    "text": (
                        "with the prior-period items, a figure is at or above "
                        f"{name} on the {' and the '.join(bases)} basis, which the current "
                        "year's aggregate alone does not reach; no gate tests this"
                    ),
                }
            ]
    return []


def attachment_json(evaluation: Evaluation, settings: Settings) -> dict[str, Any]:
    engagement = evaluation.engagement
    threshold = evaluation.threshold
    total = evaluation.aggregate
    summary = core.summary(evaluation.items, total)
    versions = {m.id: version for m, version in evaluation.pairs}
    incomplete = _incomplete_because(evaluation, summary)
    grouped = tcwg.by_type(summary.listed)
    prior = prior_period_json(evaluation.prior_period, total, threshold)
    applies = bool(summary.listed) or bool(summary.undetermined)
    run = evaluation.latest_run
    conclusion = evaluation.latest_conclusion
    concluded = None if conclusion is None else conclusion.run
    return {
        "engagement": {"id": str(engagement.id), "label": engagement.label},
        "threshold": (
            None
            if threshold is None
            else {
                "id": str(threshold.id),
                "version_no": threshold.version_no,
                "om": amount(threshold.om),
                "pm": amount(threshold.pm),
                "ctt": amount(threshold.ctt),
            }
        ),
        # ready | incomplete: incomplete when a misstatement's effects are not known or the
        # evaluation cannot be made, in which case the attachment is not fit to be sent.
        "status": "incomplete" if incomplete else "ready",
        "incomplete_because": incomplete,
        # The statement management is asked to make (SA 450 paragraph 14). Its belief, not
        # the auditor's conclusion.
        "representation": {
            "applies": applies,
            "text": core.REPRESENTATION_TEXT if applies else core.NOTHING_TO_REPRESENT,
            "basis": core.REPRESENTATION_BASIS,
        },
        # The summary: every accumulated uncorrected misstatement, by type, each type summed.
        "schedule": {
            "by_type": [
                {
                    "type": kind,
                    **sums_json(grouped[kind]),
                    "items": [
                        row_json(item, versions[item.misstatement_id])
                        for item in summary.listed
                        if item.type == kind
                    ],
                }
                for kind in tcwg.TYPES
            ],
            # Uncorrected, with effects that could not be determined: named, never dropped.
            "undetermined": [
                row_json(item, versions[item.misstatement_id]) for item in summary.undetermined
            ],
            "count": len(summary.listed) + len(summary.undetermined),
        },
        # What the summary comes to: the evaluation's own aggregate, as the gates test it,
        # with and without the projected items and by type.
        "totals": {
            **figures(total),
            "count": len(total.counted),
            "complete": total.complete,
            "basis": AGGREGATE_BASIS,
        },
        # SA 450 paragraph 11(b): the prior-period items carried forward, apart from the
        # totals, each with its current-period and cumulative effect (architecture D61).
        "prior_period": prior,
        # Outside the summary: clearly trivial and not accumulated, and no longer uncorrected.
        "not_included": {
            "clearly_trivial": {
                "items": [
                    row_json(item, versions[item.misstatement_id]) for item in summary.left_out
                ],
                "total": not_accumulated_total(total, threshold),
            },
            "not_uncorrected": [{"ref": ref, "state": state} for ref, state in total.excluded],
        },
        # For the auditor, and not part of the attachment.
        "cautions": [
            *_cautions(evaluation, summary, settings),
            *_prior_period_caution(prior, evaluation),
        ],
        # The evaluation the summary was read from: whether a run records the same figures,
        # and the partner's conclusion when there is one.
        "evaluation": {
            "run": {
                "status": "none" if run is None else run.status,
                "detail": "no evaluation run has been recorded" if run is None else run.detail,
                "run_no": None if run is None or run.run is None else run.run.run_no,
            },
            "conclusion": {
                "status": "none" if conclusion is None else conclusion.status,
                "determination": None if concluded is None else concluded.determination,
                "run_no": None if concluded is None else concluded.run_no,
            },
        },
        "basis": core.ATTACHMENT_BASIS,
        "read_only": True,
        "authorisation": authorisation_json(settings),
    }


@router.get("/engagements/{engagement_id}/rep-letter-attachment")
def read(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    """The attachment to the written representation (SA 450 paragraph 14): the summary of
    uncorrected misstatements by type, with the effects on profit before tax and on net
    assets gross and net, the prior-period items, and the statement management is asked
    to make. Read-only."""
    engagement = get_engagement(session, engagement_id)
    return attachment_json(evaluate(session, spine, engagement, settings), settings)
