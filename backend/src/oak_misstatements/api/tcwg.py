"""The TCWG extract (SA 450 paragraph 12; spec section 2 row 12, section 6 item 2;
acceptance 9; architecture D62): the uncorrected misstatements of an engagement for
communication to those charged with governance, the material ones named individually, with
the effect on the opinion and the request to correct.

Read-only and computed on every read from the evaluation as it stands, exactly as the
schedule and the gates compute it, so the three can never disagree. Nothing is stored: the
extract is a view, not a record of a communication having been made."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy.orm import Session

from oak_misstatements.api.deps import SessionDep, SettingsDep, SpineDep
from oak_misstatements.api.misstatements import line_json
from oak_misstatements.config import Settings
from oak_misstatements.core import tcwg
from oak_misstatements.core.gates import AGGREGATE_BASIS, OPINION_GATE_SCOPE, Item, opinion_gate
from oak_misstatements.models import MisstatementVersion
from oak_misstatements.schemas import amount
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.engagements import get_engagement
from oak_misstatements.services.evaluation import (
    Evaluation,
    evaluate,
    figures,
    gate_json,
    not_accumulated_total,
)
from oak_misstatements.services.misstatements import SpineView
from oak_misstatements.services.prior_period import evaluation_json as prior_period_json
from oak_misstatements.services.qualitative import entries_by_misstatement, summary_json

router = APIRouter(tags=["tcwg-extract"])

# What the opinion gate's status means for an unmodified opinion, in the gate's own terms.
OPINION_EFFECT = {
    "blocked": (
        "blocked",
        "An unmodified opinion cannot be issued on the uncorrected misstatements as they stand.",
    ),
    "open": (
        "not_blocked",
        "The size of the uncorrected misstatements does not block an unmodified opinion.",
    ),
    "undetermined": (
        "undetermined",
        "Whether an unmodified opinion is blocked cannot be determined yet.",
    ),
}


def _optional(value: Any) -> str | None:
    return None if value is None else amount(value)


def _sums_json(sums: tcwg.Sums) -> dict[str, Any]:
    return {
        "count": sums.count,
        "profit_before_tax": {"gross": amount(sums.profit.gross), "net": amount(sums.profit.net)},
        "net_assets": {
            "gross": amount(sums.net_assets.gross),
            "net": amount(sums.net_assets.net),
        },
    }


def _row(item: Item, version: MisstatementVersion) -> dict[str, Any]:
    """One uncorrected misstatement as the schedule of the extract shows it."""
    return {
        "id": str(item.misstatement_id),
        "ref": item.ref,
        "type": item.type,
        "state": item.state,
        "description": version.description,
        "source_ref": version.source_ref,
        "profit_before_tax": _optional(item.profit),
        "net_assets": _optional(item.net_assets),
        "band": None if item.band is None else item.band.value,
        "classification_only": item.classification_only,
        # A refusal carries management's reason (SA 450 paragraph 9; acceptance 3).
        "refusal_reason": version.refusal_reason,
    }


def _named(
    entry: tcwg.Named,
    version: MisstatementVersion,
    view: SpineView,
    factors: list[dict[str, Any]],
) -> dict[str, Any]:
    """An item named individually: what the schedule shows, why it is named, and what an
    item of its type must say (spec section 3.2)."""
    return {
        **_row(entry.item, version),
        "reasons": [{"code": code, "text": tcwg.REASON_TEXT[code]} for code in entry.reasons],
        # The qualitative factors recorded against it, each with its reason (spec section 5).
        "factors": factors,
        "range": (
            None
            if version.range_low is None or version.range_high is None
            else {"low": amount(version.range_low), "high": amount(version.range_high)}
        ),
        "sample_ref": version.sample_ref,
        "projection_basis": version.projection_basis,
        # Its Dr/Cr lines, as the Financial Spine holds them; empty when it could not be read.
        "lines": [line_json(line) for line in view.lines],
    }


def _incomplete_because(evaluation: Evaluation, extract: tcwg.Extract) -> list[str]:
    reasons: list[str] = []
    if evaluation.threshold is None:
        reasons.append(
            "no thresholds have been set, so no misstatement can be banded and none can be "
            "identified as above performance materiality"
        )
    if evaluation.aggregate.unresolved:
        reasons.append(
            "the effects of "
            + ", ".join(evaluation.aggregate.unresolved)
            + " cannot be determined, so the totals are short"
        )
    if extract.undetermined and evaluation.threshold is not None:
        reasons.append(
            ", ".join(item.ref for item in extract.undetermined)
            + " could not be banded, so whether each is above performance materiality is "
            "not known"
        )
    if evaluation.inconsistent:
        reasons.append(
            ", ".join(item.ref for item in evaluation.inconsistent)
            + " disagree with the Financial Spine about their state"
        )
    return reasons


def _opinion_effect(evaluation: Evaluation, settings: Settings) -> dict[str, Any]:
    exposure = opinion_gate(
        evaluation.hard,
        evaluation.soft,
        pm_gate=settings.pm_gate,
        unbanded=evaluation.unbanded,
        inconsistent=evaluation.inconsistent,
    )
    effect, statement = OPINION_EFFECT[exposure.status]
    conclusion = evaluation.latest_conclusion
    concluded = None if conclusion is None else conclusion.run
    return {
        # blocked | not_blocked | undetermined: the opinion gate's reading (spec section 7).
        "unmodified_opinion": effect,
        "statement": statement,
        "blocked_by": list(exposure.blocked_by),
        "undetermined_because": list(exposure.undetermined_because),
        "hard_gate": gate_json(evaluation.hard),
        "soft_gate": {**gate_json(evaluation.soft), "pm_gate": settings.pm_gate},
        # The partner's conclusion, when one is recorded, and whether it still stands.
        "conclusion": {
            "status": "none" if conclusion is None else conclusion.status,
            "determination": None if concluded is None else concluded.determination,
            "run_no": None if concluded is None else concluded.run_no,
        },
        "scope": OPINION_GATE_SCOPE,
        # The gate tests the current year's aggregate; the prior-period items are shown
        # in this extract and are not read by it (architecture D61).
        "reads_prior_period": False,
    }


def extract_json(session: Session, evaluation: Evaluation, settings: Settings) -> dict[str, Any]:
    engagement = evaluation.engagement
    threshold = evaluation.threshold
    total = evaluation.aggregate
    extract = tcwg.extract(evaluation.items, total, None if threshold is None else threshold.om)

    versions = {m.id: version for m, version in evaluation.pairs}
    entries = entries_by_misstatement(
        session, [entry.item.misstatement_id for entry in extract.named]
    )
    named = [
        _named(
            entry,
            versions[entry.item.misstatement_id],
            evaluation.views[versions[entry.item.misstatement_id].id],
            summary_json(entries[entry.item.misstatement_id])["factors"],
        )
        for entry in extract.named
    ]
    named_items = [entry.item for entry in extract.named]
    incomplete = _incomplete_because(evaluation, extract)
    run = evaluation.latest_run
    grouped = tcwg.by_type(extract.other)
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
        # ready | incomplete: incomplete when something uncorrected could not be placed or
        # summed, in which case the extract says what and is not fit to be communicated.
        "status": "incomplete" if incomplete else "ready",
        "incomplete_because": incomplete,
        "counts": {
            "communicated": extract.communicated,
            "named_individually": len(extract.named),
            "undetermined": len(extract.undetermined),
            "other_uncorrected": len(extract.other),
            "clearly_trivial_not_accumulated": len(extract.left_out),
        },
        # Acceptance 9: every individually material item, by name.
        "named_individually": named,
        # Could not be banded: named, because it cannot be shown not to be material.
        "undetermined": [
            {
                **_row(item, versions[item.misstatement_id]),
                "reason": (
                    "no thresholds have been set"
                    if threshold is None
                    else "its effects cannot be determined, so it cannot be banded"
                ),
            }
            for item in extract.undetermined
        ],
        # The remaining accumulated items, summarised by type and listed.
        "other_uncorrected": {
            "groups": [{"type": kind, **_sums_json(grouped[kind])} for kind in tcwg.TYPES],
            "items": [_row(item, versions[item.misstatement_id]) for item in extract.other],
        },
        "totals": {
            "named_individually": _sums_json(tcwg.sums(named_items)),
            "other_uncorrected": _sums_json(tcwg.sums(extract.other)),
            # The aggregate of the evaluation: what the two above come to together, with
            # and without the projected items and by type. The gates test these figures.
            "all_uncorrected": {
                **figures(total),
                "count": len(total.counted),
                "complete": total.complete,
            },
            "basis": AGGREGATE_BASIS,
        },
        # Outside the communication: below the clearly-trivial threshold and not
        # accumulated (spec section 4), and what is no longer uncorrected.
        "not_communicated": {
            "clearly_trivial": {
                "items": [_row(item, versions[item.misstatement_id]) for item in extract.left_out],
                "total": not_accumulated_total(total, threshold),
            },
            "not_uncorrected": [{"ref": ref, "state": state} for ref, state in total.excluded],
        },
        # SA 450 paragraph 11(b): the prior-period items carried forward, with their
        # current-period and cumulative effects apart (architecture D61).
        "prior_period": prior_period_json(evaluation.prior_period, total, threshold),
        "opinion_effect": _opinion_effect(evaluation, settings),
        "request": {
            "applies": bool(total.counted) or bool(extract.undetermined),
            "text": (
                tcwg.REQUEST_TEXT
                if total.counted or extract.undetermined
                else tcwg.NOTHING_TO_REQUEST
            ),
            "basis": tcwg.REQUEST_BASIS,
        },
        # Whether an evaluation run records these figures (architecture D43).
        "evaluation_run": {
            "status": "none" if run is None else run.status,
            "detail": "no evaluation run has been recorded" if run is None else run.detail,
            "run_no": None if run is None or run.run is None else run.run.run_no,
        },
        "basis": tcwg.TCWG_BASIS,
        "read_only": True,
        "authorisation": authorisation_json(settings),
    }


@router.get("/engagements/{engagement_id}/tcwg-extract")
def read(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    """The TCWG extract (SA 450 paragraph 12): every uncorrected misstatement, the material
    ones named individually (acceptance 9), the others summarised and listed, the totals,
    the effect on the opinion and the request to correct. Read-only."""
    engagement = get_engagement(session, engagement_id)
    return extract_json(session, evaluate(session, spine, engagement, settings), settings)
