"""The generated working paper (SA 230; SA 450 paragraph 15; spec section 6 item 5;
architecture D66): the engagement's whole record as one structured paper, and its export,
which freezes that content against the current evaluation run and registers it here.

- ``GET  .../working-paper``: the paper as it stands now, with its hash, whether it can be
  exported and whether the latest registered paper still matches it;
- ``POST .../working-paper/export``: freeze and register it. Refused until an evaluation run
  records the figures as they stand, and when nothing has changed since the last export;
- ``GET  .../working-paper/exports`` and ``GET /working-papers/{id}``: what was registered,
  the latter with its content and the hash recomputed and compared.

The Working Paper Binder has a generated-paper intake, but its contract names no source for
this module, so the export is not sent there: the answer carries the delivery in the
Binder's shape, ready for the day the contract names it (register W1)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oak_misstatements import __version__
from oak_misstatements.api.deps import SessionDep, SettingsDep, SpineDep, UserDep
from oak_misstatements.api.engagements import engagement_json
from oak_misstatements.api.evaluation import evaluation_json
from oak_misstatements.api.misstatements import misstatement_json
from oak_misstatements.api.representation import attachment_json
from oak_misstatements.api.tcwg import extract_json
from oak_misstatements.config import Settings
from oak_misstatements.core import working_paper as core
from oak_misstatements.errors import Conflict, NotFound
from oak_misstatements.models import Engagement, Misstatement, MisstatementVersion
from oak_misstatements.models.evaluation import EvaluationRun
from oak_misstatements.models.working_paper import WorkingPaper
from oak_misstatements.services.authorisation import authorisation_json
from oak_misstatements.services.conclusions import list_conclusions
from oak_misstatements.services.engagements import get_engagement, link_status
from oak_misstatements.services.evaluation import Evaluation, evaluate, run_json
from oak_misstatements.services.evaluation_runs import (
    MATERIALITY_REASSESSED,
    list_runs,
    locked_engagement,
    require_evaluable,
)
from oak_misstatements.services.misstatements import current_versions, spine_views
from oak_misstatements.services.prior_period import listing_json
from oak_misstatements.services.prior_period import versions as prior_period_versions
from oak_misstatements.services.qualitative import entries_by_misstatement
from oak_misstatements.services.spine_client import SpineClient
from oak_misstatements.services.thresholds import (
    current_threshold,
    event_json,
    events,
    history,
    threshold_json,
)

router = APIRouter(tags=["working-paper"])


def _all_versions(session: Session, engagement: Engagement) -> dict[uuid.UUID, list[Any]]:
    """Every version of every misstatement of the engagement, oldest first."""
    rows = session.execute(
        select(MisstatementVersion)
        .join(Misstatement, Misstatement.id == MisstatementVersion.misstatement_id)
        .where(Misstatement.engagement_id == engagement.id)
        .order_by(MisstatementVersion.misstatement_id, MisstatementVersion.version_no)
    ).scalars()
    found: dict[uuid.UUID, list[Any]] = {}
    for row in rows:
        found.setdefault(row.misstatement_id, []).append(row)
    return found


def paper_content(
    session: Session,
    spine: SpineClient | None,
    settings: Settings,
    engagement: Engagement,
    evaluation: Evaluation,
) -> dict[str, Any]:
    """The paper: every read the screens make, in one structure, with no authorisation
    notice anywhere in it, so it hashes the same wherever it is generated."""
    pairs = current_versions(session, engagement)
    views = spine_views(session, spine, engagement, [version for _m, version in pairs])
    threshold = current_threshold(session, engagement)
    entries = entries_by_misstatement(session, [m.id for m, _v in pairs])
    trail = _all_versions(session, engagement)
    misstatements = [
        misstatement_json(
            misstatement,
            version,
            views[version.id],
            threshold,
            settings,
            versions=trail.get(misstatement.id, [version]),
            entries=entries[misstatement.id],
        )
        for misstatement, version in pairs
    ]
    runs = [run_json(run) for run in list_runs(session, engagement)]
    conclusions = [run_json(run) for run in list_conclusions(session, engagement)]
    trail_events = [event_json(event) for event in events(session, engagement)]
    latest_conclusion = evaluation.latest_conclusion
    concluded = (
        None
        if latest_conclusion is None or latest_conclusion.run is None
        else {**run_json(latest_conclusion.run), "status": latest_conclusion.status}
    )
    current = None if threshold is None else threshold_json(threshold)
    content = {
        "paper": {
            "title": core.TITLE,
            "standards": list(core.SA_REFS),
            "module": core.MODULE,
            "module_version": __version__,
        },
        "engagement": engagement_json(
            session, spine, engagement, settings, status=link_status(spine, engagement)
        ),
        "thresholds": {
            "current": current,
            "history": [threshold_json(version) for version in history(session, engagement)],
        },
        # SA 450 paragraph 10: materiality is reassessed before each evaluation run.
        "materiality_reassessment": {
            "runs": [run["run_no"] for run in runs if run["materiality_reassessed"]],
            "events": [event for event in trail_events if event["kind"] == MATERIALITY_REASSESSED],
        },
        "misstatements": misstatements,
        "prior_period": listing_json(engagement, prior_period_versions(session, engagement)),
        "evaluation": evaluation_json(evaluation, settings),
        "runs": runs,
        "conclusions": conclusions,
        "events": trail_events,
        "tcwg_extract": extract_json(session, evaluation, settings),
        "representation_attachment": attachment_json(evaluation, settings),
        "documentation": core.documentation(
            threshold=current, misstatements=misstatements, conclusion=concluded
        ),
        "basis": core.WORKING_PAPER_BASIS,
    }
    stripped: dict[str, Any] = core.without_authorisation(content)
    return stripped


def _latest_paper(session: Session, engagement: Engagement) -> WorkingPaper | None:
    return session.scalar(
        select(WorkingPaper)
        .where(WorkingPaper.engagement_id == engagement.id)
        .order_by(WorkingPaper.paper_no.desc())
        .limit(1)
    )


def _exportable(evaluation: Evaluation) -> list[str]:
    """Why the paper cannot be exported as it stands, or nothing."""
    reasons: list[str] = []
    try:
        require_evaluable(evaluation)
    except Conflict as refused:
        reasons.append(str(refused))
    run = evaluation.latest_run
    if run is None or run.run is None:
        reasons.append(
            "no evaluation run records the figures as they stand: record a run first, so "
            "the paper rests on a recorded evaluation (SA 450 paragraph 15; architecture D66)"
        )
    elif run.status != "current":
        reasons.append(
            f"the latest evaluation run (run {run.run.run_no}) no longer records the figures "
            f"as they stand: {run.detail}; record a new run first"
        )
    return reasons


def _summary_json(paper: WorkingPaper, run: EvaluationRun | None) -> dict[str, Any]:
    return {
        "id": str(paper.id),
        "engagement_id": str(paper.engagement_id),
        "paper_no": paper.paper_no,
        "evaluation_run_id": str(paper.evaluation_run_id),
        "run_no": None if run is None else run.run_no,
        "content_hash": paper.content_hash,
        "generated_by": paper.generated_by,
        "at": paper.at.isoformat(),
    }


def _delivery_json(paper: WorkingPaper, run: EvaluationRun | None) -> dict[str, Any]:
    """The paper in the Binder's generated-paper shape (its ``paper`` and ``generated``
    blocks), not sent: the Binder's contract has no source for this module (W1)."""
    content = paper.content
    concluded = content["documentation"]["conclusion_and_basis"]
    aggregate = content["evaluation"]["aggregate"]
    return {
        "deliverable": False,
        "not_deliverable_because": core.BINDER_NOT_DELIVERABLE,
        "binder_endpoint": "POST /api/binders/{binder_id}/generated-papers",
        "paper": {
            "ref": f"W-SA450-{paper.paper_no}",
            "section": "W",
            "title": core.TITLE,
            "sa_refs": list(core.SA_REFS),
            "objective": (
                "Evaluate the effect of identified misstatements on the audit and of "
                "uncorrected misstatements on the financial statements (SA 450)"
            ),
            "procedure": (
                f"Generated by the Misstatements Rollup from the engagement's record at "
                f"evaluation run {'' if run is None else run.run_no}; content hash "
                f"{paper.content_hash}"
            ),
            "result": (
                f"{len(content['misstatements'])} misstatements recorded; uncorrected aggregate "
                f"profit before tax gross {aggregate['profit_before_tax']['gross']}, net "
                f"{aggregate['profit_before_tax']['net']}; net assets gross "
                f"{aggregate['net_assets']['gross']}, net {aggregate['net_assets']['net']}"
            ),
            "conclusion": concluded["conclusion"],
        },
        "generated": {
            "source": None,
            "module": core.MODULE,
            "module_version": __version__,
            "run_id": str(paper.evaluation_run_id),
            "generated_at": paper.at.isoformat(),
            "inputs": {
                "engagement_id": str(paper.engagement_id),
                "evaluation_run_no": None if run is None else run.run_no,
                "threshold_version_no": (
                    None
                    if content["thresholds"]["current"] is None
                    else content["thresholds"]["current"]["version_no"]
                ),
                "content_hash": paper.content_hash,
            },
            "citations": [
                {"ref": m["ref"], "source_ref": m["current"]["source_ref"]}
                for m in content["misstatements"]
            ]
            + [{"ref": f"evaluation run {'' if run is None else run.run_no}"}],
        },
    }


@router.get("/engagements/{engagement_id}/working-paper")
def read(
    engagement_id: uuid.UUID, session: SessionDep, spine: SpineDep, settings: SettingsDep
) -> dict[str, Any]:
    """The working paper as it stands now (SA 230; SA 450 paragraph 15), with its hash,
    whether it can be exported, and whether the latest export still matches it."""
    engagement = get_engagement(session, engagement_id)
    evaluation = evaluate(session, spine, engagement, settings)
    content = paper_content(session, spine, settings, engagement, evaluation)
    digest = core.content_hash(content)
    latest = _latest_paper(session, engagement)
    reasons = _exportable(evaluation)
    return {
        **content,
        "content_hash": digest,
        "exportable": {"allowed": not reasons, "reasons": reasons},
        "export": {
            "status": (
                "none"
                if latest is None
                else "current"
                if latest.content_hash == digest
                else "stale"
            ),
            "latest": (
                None
                if latest is None
                else _summary_json(latest, session.get(EvaluationRun, latest.evaluation_run_id))
            ),
        },
        "authorisation": authorisation_json(settings),
    }


@router.post("/engagements/{engagement_id}/working-paper/export", status_code=201)
def export(
    engagement_id: uuid.UUID,
    session: SessionDep,
    spine: SpineDep,
    settings: SettingsDep,
    user: UserDep,
) -> dict[str, Any]:
    """Freeze the paper as it stands and register it, tied to the current evaluation run.
    Refused until a run records the figures as they stand, and when nothing has changed
    since the last export. The engagement row is locked, so the content, the run it names
    and the row written belong to one moment."""
    engagement = locked_engagement(session, engagement_id)
    evaluation = evaluate(session, spine, engagement, settings)
    reasons = _exportable(evaluation)
    if reasons:
        raise Conflict("the working paper was not exported: " + "; ".join(reasons))
    assert evaluation.latest_run is not None and evaluation.latest_run.run is not None  # noqa: S101
    run = evaluation.latest_run.run
    content = paper_content(session, spine, settings, engagement, evaluation)
    digest = core.content_hash(content)
    latest = _latest_paper(session, engagement)
    if latest is not None and latest.content_hash == digest:
        raise Conflict(
            f"the working paper was not exported: nothing has changed since paper "
            f"{latest.paper_no} (content hash {digest})"
        )
    highest = session.scalar(
        select(func.max(WorkingPaper.paper_no)).where(WorkingPaper.engagement_id == engagement.id)
    )
    paper = WorkingPaper(
        id=uuid.uuid4(),
        engagement_id=engagement.id,
        paper_no=int(highest or 0) + 1,
        evaluation_run_id=run.id,
        content=content,
        content_hash=digest,
        generated_by=user,
    )
    session.add(paper)
    session.flush()
    return {
        "paper": _summary_json(paper, run),
        "binder_delivery": _delivery_json(paper, run),
        "authorisation": authorisation_json(settings),
    }


@router.get("/engagements/{engagement_id}/working-paper/exports")
def exports(
    engagement_id: uuid.UUID, session: SessionDep, settings: SettingsDep
) -> list[dict[str, Any]]:
    """Every registered paper of the engagement, newest first, without its content."""
    engagement = get_engagement(session, engagement_id)
    papers = session.scalars(
        select(WorkingPaper)
        .where(WorkingPaper.engagement_id == engagement.id)
        .order_by(WorkingPaper.paper_no.desc())
    )
    answers = []
    for paper in papers:
        answer = _summary_json(paper, session.get(EvaluationRun, paper.evaluation_run_id))
        answer["authorisation"] = authorisation_json(settings)
        answers.append(answer)
    return answers


@router.get("/working-papers/{paper_id}")
def read_paper(paper_id: uuid.UUID, session: SessionDep, settings: SettingsDep) -> dict[str, Any]:
    """One registered paper, exactly as it was frozen, with its hash recomputed from the
    stored content and compared with the one recorded."""
    paper = session.get(WorkingPaper, paper_id)
    if paper is None:
        raise NotFound(f"no working paper {paper_id}")
    run = session.get(EvaluationRun, paper.evaluation_run_id)
    recomputed = core.content_hash(paper.content)
    return {
        **_summary_json(paper, run),
        "content": paper.content,
        "verification": {
            "recorded_hash": paper.content_hash,
            "recomputed_hash": recomputed,
            "matches": recomputed == paper.content_hash,
        },
        "binder_delivery": _delivery_json(paper, run),
        "authorisation": authorisation_json(settings),
    }
