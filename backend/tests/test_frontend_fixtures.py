"""The frontend's test fixtures are this API's real answers (Stage 6; architecture D47).

The screens are tested against JSON files in ``frontend/tests/fixtures``. If those were
written by hand they could drift from the API, or describe a backend that does not exist.
So each fixture is produced here, by driving the real application through a scenario, and
this test fails when a committed fixture no longer matches what the API answers.

To regenerate after a deliberate API change, run this one module with the environment
variable ``OAK_WRITE_FIXTURES`` set to ``1``::

    python -m pytest tests/test_frontend_fixtures.py

Identifiers and timestamps differ on every run, so both sides are compared with those
masked. Everything else, every key and every other value, must be equal. The scenario runs
in the test transaction and is rolled back: it leaves nothing in any database.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from decimal import Decimal
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from tests.conftest import BACKEND_DIR, act_as, use_spine
from tests.fake_spine import ENGAGEMENT_ID, OPEN_VERSION_ID
from tests.test_api_evaluation import SAMPLING

FIXTURES = BACKEND_DIR.parent / "frontend" / "tests" / "fixtures"
WRITE = os.environ.get("OAK_WRITE_FIXTURES") == "1"

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")
SEQ = re.compile(r'"seq": \d+')
# A content hash (D66) differs whenever an identifier or a timestamp inside the content does.
HASH = re.compile(r"\b[0-9a-f]{64}\b")

# Labels say what each engagement is for. They are test data and name no real client.
PINNED = "Test engagement A: linked, version pinned"
LINKED = "Test engagement B: linked, no version"
UNLINKED = "Test engagement C: not linked"


def masked(value: Any) -> Any:
    """``value`` with every identifier and timestamp replaced by a placeholder. An event's
    ``seq`` is an identifier too: the database issues it, and it differs on every run."""
    text = json.dumps(value, sort_keys=True)
    text = HASH.sub("<hash>", TIME.sub("<time>", UUID.sub("<id>", text)))
    return json.loads(SEQ.sub('"seq": "<seq>"', text))


def check(name: str, answer: Any) -> None:
    """Write the fixture when asked to; in every case require it to match the API."""
    path = FIXTURES / f"{name}.json"
    if WRITE:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(answer, indent=2, ensure_ascii=False) + "\n")
    assert path.exists(), (
        f"{path.name} is missing: regenerate the fixtures (see this module's docstring)"
    )
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert masked(committed) == masked(answer), (
        f"{path.name} no longer matches the API: regenerate the fixtures if the change to "
        "the API was deliberate, and update the screens that read it"
    )


def create(api: TestClient, label: str, **link: str) -> str:
    created = api.post("/api/engagements", json={"label": label, **link})
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def test_the_engagement_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    use_spine(api)
    pinned = create(
        api,
        PINNED,
        spine_engagement_id=str(ENGAGEMENT_ID),
        spine_version_id=str(OPEN_VERSION_ID),
    )
    create(api, LINKED, spine_engagement_id=str(ENGAGEMENT_ID))
    create(api, UNLINKED)
    thresholds = api.post(
        f"/api/engagements/{pinned}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
    )
    assert thresholds.status_code == 201, thresholds.text
    for amount in ("10000.00", "300000.00"):
        raised = api.post(
            f"/api/engagements/{pinned}/misstatements",
            json={
                "type": "factual",
                "description": "Rent for March not accrued",
                "raised_from": "wp",
                "source_ref": "E-4.2",
                "lines": [{"line_no": 5, "dr": amount}, {"line_no": 3, "cr": amount}],
            },
        )
        assert raised.status_code == 201, raised.text

    listed = api.get("/api/engagements")
    assert listed.status_code == 200, listed.text
    # Within one transaction every row has the same creation time, so the API's order
    # among them is by identifier; the fixture is kept in label order to be stable.
    engagements = sorted(listed.json(), key=lambda entry: entry["label"])
    assert [entry["label"] for entry in engagements] == [PINNED, LINKED, UNLINKED]
    check("engagements", engagements)

    detail = api.get(f"/api/engagements/{pinned}")
    assert detail.status_code == 200, detail.text
    check("engagement", detail.json())

    missing = api.get("/api/engagements/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404
    check("engagement-not-found", missing.json())


# The schedule scenario (Stage 6 part 2). One engagement carrying every type, every state
# and every band the schedule has to show, and one with nothing raised.
SCHEDULE = "Test engagement S: schedule of misstatements"
NOTHING_RAISED = "Test engagement E: nothing raised"


def raise_one(api: TestClient, engagement: str, **body: Any) -> str:
    raised = api.post(f"/api/engagements/{engagement}/misstatements", json=body)
    assert raised.status_code == 201, raised.text
    return str(raised.json()["id"])


def move(api: TestClient, misstatement: str, to: str, reason: str | None = None) -> None:
    body = {"to": to} if reason is None else {"to": to, "reason": reason}
    moved = api.post(f"/api/misstatements/{misstatement}/transitions", json=body)
    assert moved.status_code == 201, moved.text


def test_the_schedule_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    spine = use_spine(api)
    pinned = {"spine_engagement_id": str(ENGAGEMENT_ID), "spine_version_id": str(OPEN_VERSION_ID)}
    engagement = create(api, SCHEDULE, **pinned)
    empty = create(api, NOTHING_RAISED, **pinned)
    thresholds = api.post(
        f"/api/engagements/{engagement}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
    )
    assert thresholds.status_code == 201, thresholds.text

    # Communicated, between the clearly-trivial line and performance materiality.
    rent = raise_one(
        api,
        engagement,
        type="factual",
        description="Rent for March not accrued",
        raised_from="wp",
        source_ref="E-4.2",
        lines=[{"line_no": 5, "dr": "60000.00"}, {"line_no": 3, "cr": "60000.00"}],
    )
    move(api, rent, "communicated")
    # Raised, below the clearly-trivial line, and increasing profit: so gross and net differ.
    raise_one(
        api,
        engagement,
        type="factual",
        description="Sales invoice of 31 March not recorded",
        raised_from="wp",
        source_ref="R-2.1",
        lines=[{"line_no": 1, "dr": "8000.00"}, {"line_no": 4, "cr": "8000.00"}],
    )
    # Judgemental with its range, refused with a reason.
    depreciation = raise_one(
        api,
        engagement,
        type="judgemental",
        description="Depreciation on plant understated: useful life taken as 15 years",
        raised_from="wp",
        source_ref="F-3.4",
        lines=[{"line_no": 15, "dr": "90000.00"}, {"line_no": 14, "cr": "90000.00"}],
        range_low="70000.00",
        range_high="110000.00",
    )
    move(api, depreciation, "communicated")
    move(api, depreciation, "refused", "Management considers the useful life appropriate")
    # Projected from a sample, naming the sample and the basis.
    raise_one(
        api,
        engagement,
        type="projected",
        description="Sales cut-off errors projected over the March population",
        raised_from="wp",
        source_ref="R-5.3",
        lines=[{"line_no": 4, "dr": "45000.00"}, {"line_no": 1, "cr": "45000.00"}],
        sample_ref="S-12",
        projection_basis="Ratio of error to sample value, applied to the population",
        **SAMPLING,
        projected_amount="45000.00",
    )
    # Above performance materiality, then corrected: posted in the Spine, out of the totals.
    salaries = raise_one(
        api,
        engagement,
        type="factual",
        description="Salaries for March not provided",
        raised_from="wp",
        source_ref="E-2.6",
        lines=[{"line_no": 6, "dr": "260000.00"}, {"line_no": 3, "cr": "260000.00"}],
    )
    move(api, salaries, "communicated")
    move(api, salaries, "corrected")
    # Classification only: between two liability captions, no effect on profit or net assets.
    raise_one(
        api,
        engagement,
        type="factual",
        description="Creditor balance shown under provisions",
        raised_from="manual",
        source_ref="L-1.3",
        lines=[{"line_no": 3, "dr": "20000.00"}, {"line_no": 8, "cr": "20000.00"}],
    )
    # Withdrawn with a reason: kept, excluded.
    charges = raise_one(
        api,
        engagement,
        type="factual",
        description="Bank charges for March not recorded",
        raised_from="wp",
        source_ref="B-1.2",
        lines=[{"line_no": 5, "dr": "15000.00"}, {"line_no": 2, "cr": "15000.00"}],
    )
    move(api, charges, "communicated")
    move(api, charges, "withdrawn", "Recorded by the client in April; not an error of this year")

    for name, path in (
        ("schedule-engagement", f"/api/engagements/{engagement}"),
        ("schedule-misstatements", f"/api/engagements/{engagement}/misstatements"),
        ("schedule-evaluation", f"/api/engagements/{engagement}/evaluation"),
        ("misstatement", f"/api/misstatements/{depreciation}"),
        ("empty-engagement", f"/api/engagements/{empty}"),
        ("empty-misstatements", f"/api/engagements/{empty}/misstatements"),
        ("empty-evaluation", f"/api/engagements/{empty}/evaluation"),
    ):
        answer = api.get(path)
        assert answer.status_code == 200, answer.text
        check(name, answer.json())

    states = [
        entry["current"]["state"]
        for entry in api.get(f"/api/engagements/{engagement}/misstatements").json()
    ]
    assert sorted(set(states)) == ["communicated", "corrected", "raised", "refused", "withdrawn"]

    missing = api.get("/api/misstatements/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404
    check("misstatement-not-found", missing.json())

    # The Financial Spine cannot be reached: every amount lives there, so the same schedule
    # has no lines, no effects and no bands, and the totals are marked incomplete (D38).
    spine.unreachable = True
    for name, path in (
        ("spine-down-misstatements", f"/api/engagements/{engagement}/misstatements"),
        ("spine-down-evaluation", f"/api/engagements/{engagement}/evaluation"),
    ):
        answer = api.get(path)
        assert answer.status_code == 200, answer.text
        check(name, answer.json())
    down = api.get(f"/api/engagements/{engagement}/evaluation").json()
    assert down["aggregate"]["complete"] is False


# The detail scenario (Stage 6 part 3). One misstatement read in every state, each move's
# answer, and each refusal a person can meet on the detail screen.
DETAIL = "Test engagement D: misstatement detail"
SENIOR = "senior@firm"
MANAGER = "manager@firm"


def attempt(api: TestClient, misstatement: str, status: int, **body: str) -> Any:
    """A move, expected to answer ``status``; its body."""
    answer = api.post(f"/api/misstatements/{misstatement}/transitions", json=body)
    assert answer.status_code == status, answer.text
    return answer.json()


def schedule_of(api: TestClient, engagement: str, part: str) -> Any:
    answer = api.get(f"/api/engagements/{engagement}/{part}")
    assert answer.status_code == 200, answer.text
    return answer.json()


def detail(api: TestClient, misstatement: str) -> Any:
    answer = api.get(f"/api/misstatements/{misstatement}")
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_the_detail_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    spine = use_spine(api)
    act_as(api, SENIOR)
    engagement = create(
        api,
        DETAIL,
        spine_engagement_id=str(ENGAGEMENT_ID),
        spine_version_id=str(OPEN_VERSION_ID),
    )
    thresholds = api.post(
        f"/api/engagements/{engagement}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
    )
    assert thresholds.status_code == 201, thresholds.text

    # One item through raised, communicated and corrected, with the refusals met on the way.
    rent = raise_one(
        api,
        engagement,
        type="factual",
        description="Rent for March not accrued",
        raised_from="wp",
        source_ref="E-4.2",
        lines=[{"line_no": 5, "dr": "60000.00"}, {"line_no": 3, "cr": "60000.00"}],
    )
    check("detail-raised", detail(api, rent))
    # The engagement's schedule before and after the first move, so the screens can be
    # tested from the schedule to the detail and back.
    check("workflow-engagement", api.get(f"/api/engagements/{engagement}").json())
    check("workflow-misstatements-raised", schedule_of(api, engagement, "misstatements"))
    check("workflow-evaluation-raised", schedule_of(api, engagement, "evaluation"))
    # The same engagement as the engagement list and the evaluation screen read it, so one
    # path through every screen can be tested on answers that belong together.
    listed = api.get("/api/engagements")
    assert listed.status_code == 200, listed.text
    assert [entry["id"] for entry in listed.json()] == [engagement]
    check("workflow-engagements", listed.json())
    check("workflow-evaluation-screen", snapshot(api, engagement))
    check("workflow-thresholds-screen", thresholds_screen(api, engagement))
    check("workflow-spine-screen", spine_screen(api, engagement))
    check("workflow-tcwg-extract", tcwg_extract(api, engagement))
    check("workflow-rep-letter-attachment", rep_attachment(api, engagement))
    check("workflow-working-paper", got(api, f"/api/engagements/{engagement}/working-paper"))
    check(
        "workflow-working-paper-exports",
        got(api, f"/api/engagements/{engagement}/working-paper/exports"),
    )
    check("transition-raised-cannot-be-corrected", attempt(api, rent, 409, to="corrected"))
    act_as(api, MANAGER)
    check("transition-communicated", attempt(api, rent, 201, to="communicated"))
    check("detail-communicated", detail(api, rent))
    check("workflow-misstatements-communicated", schedule_of(api, engagement, "misstatements"))
    check("workflow-evaluation-communicated", schedule_of(api, engagement, "evaluation"))
    check("transition-refusal-without-reason", attempt(api, rent, 422, to="refused"))
    check("transition-blank-reason", attempt(api, rent, 422, to="withdrawn", reason="   "))
    spine.unreachable = True
    check("detail-spine-down", detail(api, rent))
    check("transition-spine-down", attempt(api, rent, 503, to="corrected"))
    spine.unreachable = False
    check("transition-corrected", attempt(api, rent, 201, to="corrected"))
    check("detail-corrected", detail(api, rent))
    check("transition-from-a-final-state", attempt(api, rent, 409, to="withdrawn", reason="x"))

    # Judgemental, with its range, refused by management.
    act_as(api, SENIOR)
    depreciation = raise_one(
        api,
        engagement,
        type="judgemental",
        description="Depreciation on plant understated: useful life taken as 15 years",
        raised_from="wp",
        source_ref="F-3.4",
        lines=[{"line_no": 15, "dr": "90000.00"}, {"line_no": 14, "cr": "90000.00"}],
        range_low="70000.00",
        range_high="110000.00",
    )
    act_as(api, MANAGER)
    attempt(api, depreciation, 201, to="communicated")
    check("detail-communicated-judgemental", detail(api, depreciation))
    check(
        "transition-refused",
        attempt(
            api,
            depreciation,
            201,
            to="refused",
            reason="Management considers the useful life appropriate",
        ),
    )
    check("detail-refused", detail(api, depreciation))

    # Projected, naming its sample and basis, withdrawn by the auditor.
    act_as(api, SENIOR)
    cut_off = raise_one(
        api,
        engagement,
        type="projected",
        description="Sales cut-off errors projected over the March population",
        raised_from="wp",
        source_ref="R-5.3",
        lines=[{"line_no": 4, "dr": "45000.00"}, {"line_no": 1, "cr": "45000.00"}],
        sample_ref="S-12",
        projection_basis="Ratio of error to sample value, applied to the population",
        **SAMPLING,
        projected_amount="45000.00",
    )
    attempt(api, cut_off, 201, to="communicated")
    check("detail-communicated-projected", detail(api, cut_off))
    check(
        "transition-withdrawn",
        attempt(
            api,
            cut_off,
            201,
            to="withdrawn",
            reason="Sample re-performed: the errors were recorded in the correct period",
        ),
    )
    check("detail-withdrawn", detail(api, cut_off))

    # Classification only, between two liability captions.
    reclass = raise_one(
        api,
        engagement,
        type="factual",
        description="Creditor balance shown under provisions",
        raised_from="manual",
        source_ref="L-1.3",
        lines=[{"line_no": 3, "dr": "20000.00"}, {"line_no": 8, "cr": "20000.00"}],
    )
    check("detail-classification-only", detail(api, reclass))

    # The client later maps the provisions ledger to a reserve: the effects stay on the
    # classification recorded at raising, and the difference is reported beside them (D32).
    spine.remap("Provision for expenses", "bs.liabilities.shareholders_funds.reserves.general")
    check("detail-classification-drift", detail(api, reclass))


# The evaluation scenarios (Stage 6 part 4). Each fixture is everything the evaluation screen
# reads for one engagement at one moment: six answers, each exactly as its endpoint gave it.
EVALUATION = "Test engagement V: evaluation"
REASSESSED = {"materiality_reassessed": True}
THRESHOLDS = {"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"}
PINNED_LINK = {
    "spine_engagement_id": str(ENGAGEMENT_ID),
    "spine_version_id": str(OPEN_VERSION_ID),
}
RENT_LINES = (5, 3)  # Dr rent / Cr provisions: profit and net assets both down


def snapshot(client: TestClient, engagement: str) -> dict[str, Any]:
    """The six reads of the evaluation screen."""
    paths = {
        "engagement": f"/api/engagements/{engagement}",
        "evaluation": f"/api/engagements/{engagement}/evaluation",
        "runs": f"/api/engagements/{engagement}/evaluation/runs",
        "conclusions": f"/api/engagements/{engagement}/evaluation/conclusions",
        "opinion_gate": f"/api/engagements/{engagement}/gates/opinion",
        "sign_off_gate": f"/api/engagements/{engagement}/gates/sign-off",
    }
    answers: dict[str, Any] = {}
    for name, path in paths.items():
        answer = client.get(path)
        assert answer.status_code == 200, (path, answer.text)
        answers[name] = answer.json()
    return answers


def with_thresholds(client: TestClient, label: str, **headers: Any) -> str:
    created = client.post("/api/engagements", json={"label": label, **PINNED_LINK}, **headers)
    assert created.status_code == 201, created.text
    engagement = str(created.json()["id"])
    answer = client.post(f"/api/engagements/{engagement}/thresholds", json=THRESHOLDS, **headers)
    assert answer.status_code == 201, answer.text
    return engagement


def item(
    client: TestClient,
    engagement: str,
    amount: str,
    description: str,
    *,
    type: str = "factual",
    pair: tuple[int, int] = RENT_LINES,
    **more: Any,
) -> str:
    headers = more.pop("headers", None)
    if type == "projected":  # SA 530 (D65): how it was projected; the lines carry the amount
        more = {**SAMPLING, "projected_amount": amount, **more}
    body = {
        "type": type,
        "description": description,
        "raised_from": "wp",
        "source_ref": "E-4.2",
        "lines": [{"line_no": pair[0], "dr": amount}, {"line_no": pair[1], "cr": amount}],
        **more,
    }
    raised = client.post(f"/api/engagements/{engagement}/misstatements", json=body, headers=headers)
    assert raised.status_code == 201, raised.text
    return str(raised.json()["id"])


def post(client: TestClient, path: str, status: int, body: dict[str, Any], **kwargs: Any) -> Any:
    answer = client.post(path, json=body, **kwargs)
    assert answer.status_code == status, (path, answer.status_code, answer.text)
    return answer.json()


def test_the_evaluation_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    spine = use_spine(api)
    act_as(api, SENIOR)

    # Nothing raised and no thresholds.
    empty = create(api, "Test engagement N: nothing to evaluate", **PINNED_LINK)
    check("eval-empty", snapshot(api, empty))
    check(
        "eval-run-no-thresholds",
        post(api, f"/api/engagements/{empty}/evaluation/runs", 409, REASSESSED),
    )

    # Every type, with corrected and withdrawn items left out of the totals: no gate fires.
    engagement = with_thresholds(api, EVALUATION)
    rent = item(api, engagement, "60000.00", "Rent for March not accrued")
    move(api, rent, "communicated")
    item(api, engagement, "8000.00", "Sales invoice of 31 March not recorded", pair=(1, 4))
    depreciation = item(
        api,
        engagement,
        "90000.00",
        "Depreciation on plant understated: useful life taken as 15 years",
        type="judgemental",
        pair=(15, 14),
        range_low="70000.00",
        range_high="110000.00",
    )
    move(api, depreciation, "communicated")
    move(api, depreciation, "refused", "Management considers the useful life appropriate")
    item(
        api,
        engagement,
        "45000.00",
        "Sales cut-off errors projected over the March population",
        type="projected",
        pair=(4, 1),
        sample_ref="S-12",
        projection_basis="Ratio of error to sample value, applied to the population",
    )
    salaries = item(api, engagement, "260000.00", "Salaries for March not provided", pair=(6, 3))
    move(api, salaries, "communicated")
    move(api, salaries, "corrected")
    item(api, engagement, "20000.00", "Creditor balance shown under provisions", pair=(3, 8))
    runs = f"/api/engagements/{engagement}/evaluation/runs"
    check("eval-clear-no-run", snapshot(api, engagement))

    # A run needs the reassessment of materiality to be stated (SA 450 paragraph 10).
    check("eval-run-not-reassessed", post(api, runs, 422, {"materiality_reassessed": False}))

    # The Financial Spine cannot be reached: nothing can be aggregated, and no run is taken.
    spine.unreachable = True
    check("eval-spine-down", snapshot(api, engagement))
    check("eval-run-not-evaluable", post(api, runs, 409, REASSESSED))
    spine.unreachable = False

    # The first run, which then describes the evaluation as it stands.
    act_as(api, MANAGER)
    check("eval-run-recorded", post(api, runs, 201, REASSESSED))
    check("eval-run-current", snapshot(api, engagement))

    # A further misstatement: the run no longer describes the evaluation.
    act_as(api, SENIOR)
    item(api, engagement, "15000.00", "Bank charges for March not recorded", pair=(5, 2))
    check("eval-run-stale", snapshot(api, engagement))

    # A second run: two in the history, the later one current.
    act_as(api, MANAGER)
    post(api, runs, 201, REASSESSED)
    check("eval-two-runs", snapshot(api, engagement))

    # The firm declares what "approaching materiality" means: the strategy prompt fires.
    settings = cast(FastAPI, api.app).state.settings
    settings.strategy_trigger_fraction = Decimal("0.5")
    responses = f"/api/engagements/{engagement}/evaluation/strategy-responses"
    check("eval-strategy-required", snapshot(api, engagement))
    check(
        "eval-strategy-response",
        post(
            api,
            responses,
            201,
            {"strategy_revised": False, "note": "Revisited with the partner; no change needed"},
        ),
    )
    check("eval-strategy-recorded", snapshot(api, engagement))
    check(
        "eval-strategy-already-answered",
        post(api, responses, 409, {"strategy_revised": True}),
    )
    settings.strategy_trigger_fraction = None

    # The aggregate reaches performance materiality: the soft gate fires and asks for the
    # partner, who cannot be named in development mode.
    act_as(api, SENIOR)
    soft = with_thresholds(api, "Test engagement P: at performance materiality")
    item(api, soft, "150000.00", "Rent for the last quarter not accrued")
    item(api, soft, "100000.00", "Salaries for March not provided", pair=(6, 3))
    check("eval-soft-gate", snapshot(api, soft))

    # The aggregate reaches overall materiality only with a projected item counted.
    hard = with_thresholds(api, "Test engagement O: at overall materiality")
    item(api, hard, "200000.00", "Rent for the last quarter not accrued")
    item(
        api,
        hard,
        "200000.00",
        "Sales cut-off errors projected over the year",
        type="projected",
        pair=(4, 1),
        sample_ref="S-14",
        projection_basis="Ratio of error to sample value, applied to the population",
    )
    check("eval-hard-gate", snapshot(api, hard))

    # One item above performance materiality, not yet dealt with: it blocks sign-off.
    above = with_thresholds(api, "Test engagement I: an item above performance materiality")
    item(api, above, "300000.00", "Salaries for the last quarter not provided", pair=(6, 3))
    check("eval-item-above-pm", snapshot(api, above))


def test_the_conclusion_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    """A conclusion can only be recorded by a partner named by the trusted proxy, so this
    scenario runs the app the way production does: header identity behind a listed proxy."""
    use_spine(api)
    settings = cast(FastAPI, api.app).state.settings
    settings.auth = "header"
    settings.dev_user = None
    settings.trusted_proxies = "10.0.0.0/24"
    settings.auth_roles_header = "X-Authenticated-Roles"
    settings.partner_role = "engagement-partner"
    proxy = TestClient(api.app, client=("10.0.0.5", 40000))
    senior = {"X-Authenticated-User": SENIOR, "X-Authenticated-Roles": "staff"}
    partner = {
        "X-Authenticated-User": "partner@firm",
        "X-Authenticated-Roles": "staff, engagement-partner",
    }

    engagement = with_thresholds(proxy, "Test engagement C: conclusion", headers=senior)
    item(proxy, engagement, "60000.00", "Rent for March not accrued", headers=senior)
    runs = f"/api/engagements/{engagement}/evaluation/runs"
    conclusions = f"/api/engagements/{engagement}/evaluation/conclusions"
    first = post(proxy, runs, 201, REASSESSED, headers=senior)
    # A current run, no conclusion yet, and the partner's actions available.
    check("eval-partner-available", snapshot(proxy, engagement))

    words = {
        "conclusion": "Uncorrected misstatements are not material, individually or in aggregate.",
        "basis": "The aggregate is below performance materiality on every measure; see C-4.",
        **REASSESSED,
    }
    # Someone who is not the partner is refused, whatever else is right.
    check(
        "eval-conclusion-not-a-partner",
        post(
            proxy,
            f"{conclusions}/not-material",
            403,
            {**words, "reviewed_run_id": first["id"]},
            headers=senior,
        ),
    )
    check(
        "eval-conclusion-recorded",
        post(
            proxy,
            f"{conclusions}/not-material",
            201,
            {**words, "reviewed_run_id": first["id"]},
            headers=partner,
        ),
    )
    check("eval-concluded", snapshot(proxy, engagement))

    # A further misstatement: the conclusion no longer stands on the evaluation as it is.
    item(
        proxy,
        engagement,
        "18000.00",
        "Sales invoice of 31 March not recorded",
        pair=(1, 4),
        headers=senior,
    )
    check("eval-conclusion-stale", snapshot(proxy, engagement))

    # A new run and a new conclusion: two in the history, none ever changed.
    second = post(proxy, runs, 201, REASSESSED, headers=senior)
    post(
        proxy,
        f"{conclusions}/not-material",
        201,
        {**words, "reviewed_run_id": second["id"]},
        headers=partner,
    )
    check("eval-two-conclusions", snapshot(proxy, engagement))


# The screens added to close Stage 6 (S1, S2, S3, S11) and the display branches no earlier
# fixture reached (V11). A refusal is kept with the status it was sent with.


def refused(client: TestClient, path: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """A request the backend refuses: the status and the body, exactly as sent."""
    answer = client.post(path, json=body, **kwargs)
    assert answer.status_code >= 400, (path, answer.status_code, answer.text)
    return {"status": answer.status_code, "body": answer.json()}


def got(client: TestClient, path: str) -> Any:
    answer = client.get(path)
    assert answer.status_code == 200, (path, answer.text)
    return answer.json()


def thresholds_screen(client: TestClient, engagement: str) -> dict[str, Any]:
    """The four reads of the thresholds screen."""
    return {
        "engagement": got(client, f"/api/engagements/{engagement}"),
        "current": got(client, f"/api/engagements/{engagement}/thresholds"),
        "history": got(client, f"/api/engagements/{engagement}/thresholds/history"),
        "events": got(client, f"/api/engagements/{engagement}/events"),
    }


def spine_screen(client: TestClient, engagement: str) -> dict[str, Any]:
    """The two reads of the Financial Spine screen."""
    return {
        "engagement": got(client, f"/api/engagements/{engagement}"),
        "reconciliation": got(client, f"/api/engagements/{engagement}/spine-reconciliation"),
    }


def events_screen(client: TestClient, engagement: str) -> dict[str, Any]:
    return {
        "engagement": got(client, f"/api/engagements/{engagement}"),
        "events": got(client, f"/api/engagements/{engagement}/events"),
    }


RENT = {
    "type": "factual",
    "description": "Rent for March not accrued",
    "raised_from": "wp",
    "source_ref": "E-4.2",
    "lines": [{"line_no": 5, "dr": "60000.00"}, {"line_no": 3, "cr": "60000.00"}],
}


def test_the_setup_screen_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    spine = use_spine(api)
    act_as(api, SENIOR)

    # ---- creating an engagement ----
    check("engagement-create-blank-label", refused(api, "/api/engagements", {"label": "   "}))
    check(
        "engagement-create-version-without-engagement",
        refused(
            api,
            "/api/engagements",
            {"label": "Test engagement", "spine_version_id": str(OPEN_VERSION_ID)},
        ),
    )
    check(
        "engagement-create-unknown-spine-engagement",
        refused(
            api,
            "/api/engagements",
            {
                "label": "Test engagement",
                "spine_engagement_id": "99999999-9999-4999-8999-999999999999",
            },
        ),
    )
    unlinked = post(api, "/api/engagements", 201, {"label": "Test engagement K: created unlinked"})
    check("engagement-created-unlinked", unlinked)
    pinned = post(
        api, "/api/engagements", 201, {"label": "Test engagement L: created pinned", **PINNED_LINK}
    )
    check("engagement-created-pinned", pinned)
    engagement = str(pinned["id"])

    # ---- the Financial Spine link and the reconciliation ----
    check("spine-screen-unlinked", spine_screen(api, str(unlinked["id"])))
    check(
        "spine-link-set",
        post(api, f"/api/engagements/{unlinked['id']}/spine-link", 200, PINNED_LINK),
    )
    check(
        "spine-link-unknown-version",
        refused(
            api,
            f"/api/engagements/{unlinked['id']}/spine-link",
            {
                "spine_engagement_id": str(ENGAGEMENT_ID),
                "spine_version_id": "99999999-9999-4999-8999-999999999999",
            },
        ),
    )
    check("spine-screen-clean-empty", spine_screen(api, engagement))

    # ---- thresholds: none, set, revised, and the refusals ----
    thresholds = f"/api/engagements/{engagement}/thresholds"
    check("thresholds-screen-none", thresholds_screen(api, engagement))
    check(
        "threshold-pm-not-below-om",
        refused(api, thresholds, {**THRESHOLDS, "pm": "400000.00"}),
    )
    check("threshold-no-fraction", refused(api, thresholds, {"om": "400000.00", "pm": "250000.00"}))
    check(
        "threshold-fraction-too-large",
        refused(api, thresholds, {**THRESHOLDS, "ctt_fraction": "1.5"}),
    )
    check("threshold-set", post(api, thresholds, 201, THRESHOLDS))
    check("thresholds-screen-one", thresholds_screen(api, engagement))

    # ---- recording a misstatement, and the refusals ----
    misstatements = f"/api/engagements/{engagement}/misstatements"
    check(
        "raise-unbalanced",
        refused(
            api,
            misstatements,
            {**RENT, "lines": [{"line_no": 5, "dr": "60000.00"}, {"line_no": 3, "cr": "50000.00"}]},
        ),
    )
    check(
        "raise-one-line",
        refused(api, misstatements, {**RENT, "lines": [{"line_no": 5, "dr": "60000.00"}]}),
    )
    check(
        "raise-unknown-line",
        refused(
            api,
            misstatements,
            {
                **RENT,
                "lines": [{"line_no": 999, "dr": "60000.00"}, {"line_no": 3, "cr": "60000.00"}],
            },
        ),
    )
    check(
        "raise-judgemental-without-range",
        refused(api, misstatements, {**RENT, "type": "judgemental"}),
    )
    check(
        "raise-projected-without-sample", refused(api, misstatements, {**RENT, "type": "projected"})
    )
    check(
        "raise-on-unlinked-engagement",
        refused(
            api,
            f"/api/engagements/{create(api, 'Test engagement M: never linked')}/misstatements",
            RENT,
        ),
    )
    raised = post(api, misstatements, 201, RENT)
    check("misstatement-raised", raised)
    # A ledger the Spine's import lacks, introduced by name, group and Schedule III head.
    check(
        "misstatement-raised-new-ledger",
        post(
            api,
            misstatements,
            201,
            {
                "type": "judgemental",
                "description": "Provision for doubtful debts understated",
                "raised_from": "manual",
                "source_ref": "R-7.1",
                "range_low": "20000.00",
                "range_high": "40000.00",
                "lines": [
                    {
                        "ledger_name": "Bad debts",
                        "parent_chain": ["Indirect Expenses"],
                        "head_id": "pl.expenses.other",
                        "dr": "30000.00",
                    },
                    {"line_no": 1, "cr": "30000.00"},
                ],
            },
        ),
    )
    # Once a misstatement is proposed on the pinned version the link cannot be re-pointed.
    check(
        "spine-link-refused-after-raising",
        refused(
            api,
            f"/api/engagements/{engagement}/spine-link",
            {"spine_engagement_id": str(ENGAGEMENT_ID)},
        ),
    )

    # ---- revising the thresholds: materiality reassessed, every band recomputes ----
    act_as(api, MANAGER)
    check(
        "threshold-revised",
        post(
            api,
            thresholds,
            201,
            {
                "om": "500000.00",
                "pm": "300000.00",
                "ctt_fraction": "0.04",
                "basis": "C-1 revised: benchmark updated to final profit before tax",
            },
        ),
    )
    check("thresholds-screen-two", thresholds_screen(api, engagement))
    check("events-screen-thresholds", events_screen(api, engagement))

    # ---- the reconciliation: clean, then with every kind of finding ----
    check("spine-screen-clean", spine_screen(api, engagement))
    # An orphan: the Spine took the proposal, and the commit here then failed.
    factory = cast(FastAPI, api.app).state.session_factory
    state = {"armed": True}

    def fail_once(_session: Any) -> None:
        if state["armed"]:
            state["armed"] = False
            raise OperationalError("COMMIT", {}, Exception("connection lost at commit"))

    event.listen(factory, "before_commit", fail_once)
    failed = TestClient(api.app, raise_server_exceptions=False).post(
        misstatements, json={**RENT, "description": "Electricity for March not accrued"}
    )
    event.remove(factory, "before_commit", fail_once)
    assert failed.status_code == 503, failed.text
    check("raise-commit-failed", {"status": failed.status_code, "body": failed.json()})
    # The Spine decides one adjustment directly, and loses another.
    spine.client().decide(
        OPEN_VERSION_ID,
        uuid.UUID(raised["current"]["spine_adjustment_id"]),
        status="accepted",
        note=None,
    )
    third = post(
        api, misstatements, 201, {**RENT, "description": "Telephone for March not accrued"}
    )
    del spine.adjustments[uuid.UUID(third["current"]["spine_adjustment_id"])]
    problems = spine_screen(api, engagement)
    assert problems["reconciliation"]["clean"] is False
    assert problems["reconciliation"]["orphans"] and problems["reconciliation"]["missing"]
    assert problems["reconciliation"]["disagreements"]
    check("spine-screen-problems", problems)

    spine.unreachable = True
    check("spine-screen-unreachable", spine_screen(api, engagement))
    check("thresholds-screen-spine-down", thresholds_screen(api, engagement))


def test_the_untested_branch_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    """The eight display branches no earlier fixture reached (register V11)."""
    spine = use_spine(api)
    act_as(api, SENIOR)
    engagement = with_thresholds(api, "Test engagement B: display branches")
    runs = f"/api/engagements/{engagement}/evaluation/runs"

    # 1. A judgemental range that crosses performance materiality (250,000).
    crossing = item(
        api,
        engagement,
        "240000.00",
        "Inventory provision understated: net realisable value",
        type="judgemental",
        pair=(15, 14),
        range_low="200000.00",
        range_high="300000.00",
    )
    check("branch-range-crosses-pm", detail(api, crossing))
    move(api, crossing, "communicated")
    move(api, crossing, "refused", "Management considers the provision adequate")

    # 2. A state that differs from the Spine's: the Spine accepted the adjustment directly.
    differs = item(api, engagement, "30000.00", "Rent for March not accrued")
    move(api, differs, "communicated")
    record = detail(api, differs)
    spine.client().decide(
        OPEN_VERSION_ID,
        uuid.UUID(record["current"]["spine_adjustment_id"]),
        status="accepted",
        note=None,
    )
    check("branch-state-differs", detail(api, differs))
    check("branch-state-differs-schedule", schedule_of(api, engagement, "misstatements"))
    check("branch-state-differs-evaluation", snapshot(api, engagement))
    check("branch-state-differs-run-refused", refused(api, runs, REASSESSED))

    # 5. A move the Spine had already decided: recorded here, decided nothing twice.
    check("branch-already-decided", attempt(api, differs, 201, to="corrected"))

    # 3 and 4. A ledger the Spine now holds under another key: it cannot be matched, so the
    # effects cannot be determined, while the Spine itself is readable.
    unmatched = item(api, engagement, "20000.00", "Salaries for March not provided", pair=(6, 3))
    spine.rekey_ledger("Salaries", "salaries (old)")
    check("branch-unmatched", detail(api, unmatched))
    check("branch-unmatched-schedule", schedule_of(api, engagement, "misstatements"))
    check("branch-unmatched-evaluation", snapshot(api, engagement))
    spine.rekey = {}

    # 8. One item at or above overall materiality (400,000) on its own.
    alone = with_thresholds(api, "Test engagement T: one item at overall materiality")
    item(api, alone, "400000.00", "Revenue recognised before delivery", pair=(4, 1))
    at_om = snapshot(api, alone)
    assert at_om["evaluation"]["tests"]["individual"]["at_or_above_om"] == ["M-1"]
    check("branch-item-at-om", at_om)

    # 7. A strategy answer gone stale: the figures moved after it was given.
    settings = cast(FastAPI, api.app).state.settings
    settings.strategy_trigger_fraction = Decimal("0.5")
    prompt = with_thresholds(api, "Test engagement Q: strategy answer gone stale")
    item(api, prompt, "210000.00", "Rent for the last quarter not accrued")
    post(
        api,
        f"/api/engagements/{prompt}/evaluation/strategy-responses",
        201,
        {"strategy_revised": True, "note": "Sample sizes increased in revenue"},
    )
    item(api, prompt, "15000.00", "Bank charges for March not recorded", pair=(5, 2))
    stale = snapshot(api, prompt)
    assert stale["evaluation"]["gates"]["strategy_trigger"]["response"]["status"] == "stale"
    check("branch-strategy-stale", stale)
    check("events-screen-evaluation", events_screen(api, prompt))
    settings.strategy_trigger_fraction = None


def test_the_partner_form_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    """The two partner-only writes, captured with the app run the way production is: header
    identity behind a listed proxy, the partner named by the proxy's role claim."""
    use_spine(api)
    settings = cast(FastAPI, api.app).state.settings
    settings.auth = "header"
    settings.dev_user = None
    settings.trusted_proxies = "10.0.0.0/24"
    settings.auth_roles_header = "X-Authenticated-Roles"
    settings.partner_role = "engagement-partner"
    proxy = TestClient(api.app, client=("10.0.0.5", 40000))
    senior = {"X-Authenticated-User": SENIOR, "X-Authenticated-Roles": "staff"}
    partner = {
        "X-Authenticated-User": "partner@firm",
        "X-Authenticated-Roles": "staff, engagement-partner",
    }

    # The aggregate reaches performance materiality: the soft gate asks for the partner.
    engagement = with_thresholds(
        proxy, "Test engagement G: acknowledgement and conclusion", headers=senior
    )
    item(proxy, engagement, "150000.00", "Rent for the last quarter not accrued", headers=senior)
    item(
        proxy,
        engagement,
        "100000.00",
        "Salaries for March not provided",
        pair=(6, 3),
        headers=senior,
    )
    base = f"/api/engagements/{engagement}/evaluation"
    run = post(proxy, f"{base}/runs", 201, REASSESSED, headers=senior)
    check("partner-acknowledgement-required", snapshot(proxy, engagement))

    words = {
        "conclusion": "Uncorrected misstatements are not material, individually or in aggregate.",
        "basis": "The aggregate is at performance materiality and below overall materiality; C-4.",
        "reviewed_run_id": run["id"],
        **REASSESSED,
    }
    # The gate is in the write path: not material is refused until the partner acknowledges.
    check(
        "partner-conclusion-gate-blocked",
        refused(proxy, f"{base}/conclusions/not-material", words, headers=partner),
    )
    check(
        "partner-acknowledgement-not-a-partner",
        refused(
            proxy,
            f"{base}/soft-gate-acknowledgements",
            {"note": "Reviewed with the manager"},
            headers=senior,
        ),
    )
    check(
        "partner-acknowledgement-recorded",
        post(
            proxy,
            f"{base}/soft-gate-acknowledgements",
            201,
            {"note": "Reviewed with the manager; see C-4"},
            headers=partner,
        ),
    )
    check("partner-acknowledged", snapshot(proxy, engagement))
    check(
        "partner-acknowledgement-twice",
        refused(proxy, f"{base}/soft-gate-acknowledgements", {}, headers=partner),
    )
    check(
        "partner-conclusion-empty",
        refused(
            proxy,
            f"{base}/conclusions/not-material",
            {**words, "conclusion": "   ", "basis": ""},
            headers=partner,
        ),
    )
    check(
        "partner-conclusion-recorded",
        post(proxy, f"{base}/conclusions/not-material", 201, words, headers=partner),
    )
    check("partner-concluded", snapshot(proxy, engagement))
    check("events-screen-partner", events_screen(proxy, engagement))

    # 6. An acknowledgement gone stale: the figures moved after it was given.
    item(
        proxy,
        engagement,
        "18000.00",
        "Bank charges for March not recorded",
        pair=(5, 2),
        headers=senior,
    )
    stale = snapshot(proxy, engagement)
    assert stale["evaluation"]["gates"]["soft"]["acknowledgement"]["status"] == "stale"
    check("branch-acknowledgement-stale", stale)

    # The other conclusion: material, which a gate that fires does not block.
    second = post(proxy, f"{base}/runs", 201, REASSESSED, headers=senior)
    check(
        "partner-conclusion-stale-run",
        refused(
            proxy,
            f"{base}/conclusions/material",
            {**words, "conclusion": "Material in aggregate.", "basis": "At PM; see C-4."},
            headers=partner,
        ),
    )
    check(
        "partner-conclusion-material-recorded",
        post(
            proxy,
            f"{base}/conclusions/material",
            201,
            {
                **words,
                "conclusion": "Uncorrected misstatements are material in aggregate.",
                "basis": "The aggregate exceeds performance materiality on every measure; C-4.",
                "reviewed_run_id": second["id"],
            },
            headers=partner,
        ),
    )
    check("partner-concluded-material", snapshot(proxy, engagement))


# The qualitative checklist (Pass 2, feature 1; architecture D59). One engagement with an
# ordinary item and a clearly trivial one; the small one is escalated, its reason changed,
# and the factor cleared again, with each refusal a person can meet on the way.
QUALITATIVE = "Test engagement Q: qualitative factors"
RELATED_PARTY = "Sale to a firm owned by a director; see E-12"


def test_the_qualitative_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    use_spine(api)
    act_as(api, SENIOR)
    engagement = with_thresholds(api, QUALITATIVE)  # CTT 12,500
    item(api, engagement, "60000.00", "Rent for March not accrued")
    small = item(api, engagement, "3000.00", "Sale to a related party not invoiced")
    path = f"/api/misstatements/{small}/qualitative"

    # Before anything is recorded: clearly trivial, not escalated, left out of the totals.
    check("qualitative-detail-clear", detail(api, small))
    check("qualitative-blank-note", post(api, path, 422, {"factor": "fraud", "note": "   "}))

    # A factor is recorded: the item is escalated, whatever its amount.
    act_as(api, MANAGER)
    recorded = post(api, path, 201, {"factor": "related_party", "note": RELATED_PARTY})
    check("qualitative-recorded", recorded)
    check("qualitative-detail-escalated", detail(api, small))
    check("qualitative-engagement", api.get(f"/api/engagements/{engagement}").json())
    check("qualitative-misstatements", schedule_of(api, engagement, "misstatements"))
    check("qualitative-evaluation", schedule_of(api, engagement, "evaluation"))
    check("qualitative-evaluation-screen", snapshot(api, engagement))
    check(
        "qualitative-already-recorded",
        post(api, path, 409, {"factor": "related_party", "note": RELATED_PARTY}),
    )

    # The reason is changed: a new entry, the first one kept.
    check(
        "qualitative-reason-changed",
        post(
            api,
            path,
            201,
            {"factor": "related_party", "note": "Director's firm; pricing not at arm's length"},
        ),
    )
    check("qualitative-detail-reason-changed", detail(api, small))

    # The factor is cleared, with the reason: the item is no longer escalated.
    check(
        "qualitative-cleared",
        post(
            api,
            f"{path}/related_party/clear",
            201,
            {"note": "The buyer is not a related party: E-12 revised"},
        ),
    )
    check("qualitative-detail-cleared", detail(api, small))
    # Clearing it a second time, as from a page that still shows it recorded, is refused.
    check(
        "qualitative-not-recorded",
        post(api, f"{path}/related_party/clear", 409, {"note": "Cleared twice"}),
    )


# The prior-period carry-forward (Pass 2, feature 2; architecture D61). One engagement with
# two misstatements of its own and two items carried from the prior period: one that reversed
# in this period and one that still stands. A run is recorded, an item is revised and one is
# removed, with each refusal a person can meet on the way.
PRIOR_PERIOD = "Test engagement P: prior-period items"
PY_REVERSED = {
    "description": "Rent for March of the prior year not accrued",
    "prior_period": "FY 2024-25",
    "source_ref": "PY schedule M-4",
    "current_profit_before_tax": "50000.00",
    "current_net_assets": "0.00",
    "cumulative_profit_before_tax": "0.00",
    "cumulative_net_assets": "0.00",
    "basis": "Accrual of the prior year reversed in April; see PY E-4.2",
}
PY_STANDING = {
    "description": "Depreciation on plant understated in the prior year",
    "prior_period": "FY 2024-25",
    "source_ref": "PY schedule M-7",
    "current_profit_before_tax": "0.00",
    "current_net_assets": "-30000.00",
    "cumulative_profit_before_tax": "-30000.00",
    "cumulative_net_assets": "-30000.00",
    "basis": "Carrying amount still overstated at the year end; see PY F-3.4",
}


def test_the_prior_period_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    use_spine(api)
    act_as(api, SENIOR)
    engagement = with_thresholds(api, PRIOR_PERIOD)  # OM 4,00,000; PM 2,50,000
    item(api, engagement, "150000.00", "Rent for March not accrued")
    item(api, engagement, "40000.00", "Repairs charged to plant")
    path = f"/api/engagements/{engagement}/prior-period"

    # Nothing carried yet: the evaluation says so.
    check("prior-period-none-screen", snapshot(api, engagement))
    check("prior-period-blank-basis", post(api, path, 422, {**PY_REVERSED, "basis": "   "}))

    act_as(api, MANAGER)
    check("prior-period-recorded", post(api, path, 201, PY_REVERSED))
    post(api, path, 201, PY_STANDING)
    check("prior-period-listing", got(api, path))
    # Two items carried, their current-period and cumulative effects apart, and no gate
    # reading them: the current year's aggregate is below PM and the gates are clear.
    check("prior-period-screen", snapshot(api, engagement))

    # A run records what it saw of them.
    post(api, f"/api/engagements/{engagement}/evaluation/runs", 201, REASSESSED)
    check("prior-period-run-screen", snapshot(api, engagement))

    # The standing item is revised upward: with it the cumulative view now reaches PM, which
    # is said as information, and the run no longer describes the evaluation.
    check(
        "prior-period-revised",
        post(
            api,
            f"{path}/PY-2/revisions",
            201,
            {
                "current_profit_before_tax": "0.00",
                "current_net_assets": "-70000.00",
                "cumulative_profit_before_tax": "-70000.00",
                "cumulative_net_assets": "-70000.00",
                "basis": "Useful life re-read: the understatement was 70,000; see PY F-3.4 revised",
            },
        ),
    )
    check("prior-period-reaches-pm-screen", snapshot(api, engagement))

    # The reversed item is removed, with the reason; removing it twice is refused.
    removal = {"reason": "Corrected by management in this year's books; see E-9"}
    check("prior-period-removed", post(api, f"{path}/PY-1/removal", 201, removal))
    check("prior-period-not-carried", post(api, f"{path}/PY-1/removal", 409, removal))
    check("prior-period-removed-screen", snapshot(api, engagement))


# The TCWG extract (Pass 2, feature 3; architecture D62). One engagement read at three
# moments: with nothing above PM and the opinion not blocked; with every place an item can
# fall filled and an unmodified opinion blocked; and with the Financial Spine unreachable.
# A second engagement has no thresholds, and a third has nothing raised.
TCWG = "Test engagement T: TCWG extract"


def tcwg_extract(client: TestClient, engagement: str) -> Any:
    return got(client, f"/api/engagements/{engagement}/tcwg-extract")


def rep_attachment(client: TestClient, engagement: str) -> Any:
    """The written representation attachment (Pass 2, feature 4; architecture D63)."""
    return got(client, f"/api/engagements/{engagement}/rep-letter-attachment")


def test_the_tcwg_extract_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    spine = use_spine(api)
    act_as(api, SENIOR)

    # Nothing raised: nothing to communicate and nothing to request.
    nothing = with_thresholds(api, "Test engagement U: TCWG extract, nothing raised")
    check("tcwg-extract-nothing", tcwg_extract(api, nothing))
    check("rep-letter-attachment-nothing", rep_attachment(api, nothing))

    # No thresholds: nothing can be banded, so the extract is incomplete.
    unset = create(api, "Test engagement W: TCWG extract, no thresholds", **PINNED_LINK)
    item(api, unset, "300000.00", "Rent for the last quarter not accrued")
    check("tcwg-extract-no-thresholds", tcwg_extract(api, unset))
    check("rep-letter-attachment-no-thresholds", rep_attachment(api, unset))

    engagement = with_thresholds(api, TCWG)  # OM 4,00,000; PM 2,50,000; CTT 12,500
    item(api, engagement, "60000.00", "Rent for March not accrued")  # M-1
    item(
        api,
        engagement,
        "40000.00",
        "Sales cut-off errors projected over the March population",
        type="projected",
        pair=(4, 1),
        sample_ref="S-12",
        projection_basis="Ratio of error to sample value, applied to the population",
    )  # M-2
    refused = item(api, engagement, "50000.00", "Repairs charged to plant")  # M-3
    act_as(api, MANAGER)
    move(api, refused, "communicated")
    move(api, refused, "refused", "Management considers the amount immaterial")
    trivial = item(api, engagement, "2000.00", "Petty cash shortage")  # M-4: below CTT
    assert trivial
    settled = item(api, engagement, "45000.00", "Bonus provision understated")  # M-5
    move(api, settled, "communicated")
    move(api, settled, "corrected")
    # Nothing above PM, nothing escalated: the others only, and the opinion not blocked.
    check("tcwg-extract-not-blocked", tcwg_extract(api, engagement))

    act_as(api, SENIOR)
    item(
        api,
        engagement,
        "300000.00",
        "Depreciation on plant understated: useful life taken as 15 years",
        type="judgemental",
        pair=(15, 14),
        range_low="270000.00",
        range_high="330000.00",
    )  # M-6: above PM
    related = item(api, engagement, "3000.00", "Sale to a related party not invoiced")  # M-7
    act_as(api, MANAGER)
    post(
        api,
        f"/api/misstatements/{related}/qualitative",
        201,
        {"factor": "related_party", "note": "Sale to a firm owned by a director; see E-12"},
    )
    post(
        api,
        f"/api/engagements/{engagement}/prior-period",
        201,
        {
            "description": "Depreciation on plant understated in the prior year",
            "prior_period": "FY 2024-25",
            "source_ref": "PY schedule M-7",
            "current_profit_before_tax": "0.00",
            "current_net_assets": "-30000.00",
            "cumulative_profit_before_tax": "-30000.00",
            "cumulative_net_assets": "-30000.00",
            "basis": "Carrying amount still overstated at the year end; see PY F-3.4",
        },
    )
    post(api, f"/api/engagements/{engagement}/evaluation/runs", 201, REASSESSED)
    # Two items named individually, three others, one clearly trivial left outside, one
    # corrected; the aggregate at or above overall materiality: an unmodified opinion blocked.
    check("tcwg-extract-blocked", tcwg_extract(api, engagement))
    # The same moment as the attachment to the written representation: every caution
    # the auditor can meet is raised, and the statement is unchanged.
    check("rep-letter-attachment-cautions", rep_attachment(api, engagement))

    spine.unreachable = True
    check("tcwg-extract-spine-down", tcwg_extract(api, engagement))
    check("rep-letter-attachment-spine-down", rep_attachment(api, engagement))
    spine.unreachable = False


def test_the_representation_attachment_fixture_with_no_caution_is_the_apis_real_answer(
    api: TestClient,
) -> None:
    """An engagement whose evaluation sits with the statement: every item communicated to
    management, three types, one refused, the aggregate below PM, and a run recording it."""
    use_spine(api)
    act_as(api, SENIOR)
    engagement = with_thresholds(api, "Test engagement R: representation attachment")
    rent = item(api, engagement, "60000.00", "Rent for March not accrued")
    estimate = item(
        api,
        engagement,
        "35000.00",
        "Provision for doubtful debts understated",
        type="judgemental",
        pair=(5, 3),
        range_low="30000.00",
        range_high="40000.00",
    )
    projected = item(
        api,
        engagement,
        "40000.00",
        "Sales cut-off errors projected over the March population",
        type="projected",
        pair=(4, 1),
        sample_ref="S-12",
        projection_basis="Ratio of error to sample value, applied to the population",
    )
    reversal = item(api, engagement, "20000.00", "Repairs accrued twice", pair=(3, 5))
    act_as(api, MANAGER)
    for misstatement in (rent, estimate, projected, reversal):
        move(api, misstatement, "communicated")
    move(api, estimate, "refused", "Management considers its estimate reasonable")
    post(api, f"/api/engagements/{engagement}/evaluation/runs", 201, REASSESSED)
    check("rep-letter-attachment-ready", rep_attachment(api, engagement))


# The intake hooks (Pass 2, feature 5; architecture D64): one misstatement from each source,
# the schedule and detail that show their attribution, and each refusal a person can meet.
INTAKE = "Test engagement I: intake"
CITATIONS = [
    {
        "source": "sales_register.csv",
        "row": "1042",
        "detail": "Invoice dated 2 April booked in March",
    },
    {"source": "sales_register.csv", "row": "1057"},
]


def test_the_intake_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    use_spine(api)
    act_as(api, SENIOR)
    engagement = with_thresholds(api, INTAKE)
    path = f"/api/engagements/{engagement}/intake"
    common = {"type": "factual", "raised_from": None}
    del common["raised_from"]

    check(
        "intake-wp",
        post(
            api,
            f"{path}/wp",
            201,
            {
                **common,
                "description": "Rent for March not accrued",
                "working_paper_ref": "E-4.2",
                "lines": [{"line_no": 5, "dr": "60000.00"}, {"line_no": 3, "cr": "60000.00"}],
            },
        ),
    )
    act_as(api, "workmind@firm")
    run = post(
        api,
        f"{path}/run",
        201,
        {
            **common,
            "description": "Sales of April booked in March",
            "run_id": "run-2026-11-07-0042",
            "citations": CITATIONS,
            "lines": [{"line_no": 4, "dr": "40000.00"}, {"line_no": 1, "cr": "40000.00"}],
        },
    )
    check("intake-run", run)
    act_as(api, MANAGER)
    check(
        "intake-note",
        post(
            api,
            f"{path}/note",
            201,
            {
                **common,
                "description": "Repairs charged to plant",
                "note_ref": "RN-17",
                "note_link": "https://review.example.test/notes/RN-17",
                "lines": [{"line_no": 5, "dr": "50000.00"}, {"line_no": 3, "cr": "50000.00"}],
            },
        ),
    )
    act_as(api, SENIOR)
    check(
        "intake-manual",
        post(
            api,
            f"{path}/manual",
            201,
            {
                **common,
                "description": "Bonus provision understated",
                "working_paper_ref": "C-9.1",
                "lines": [{"line_no": 5, "dr": "45000.00"}, {"line_no": 3, "cr": "45000.00"}],
            },
        ),
    )
    # The schedule and the detail of the run's misstatement, with its citations.
    check("intake-engagement", api.get(f"/api/engagements/{engagement}").json())
    check("intake-misstatements", schedule_of(api, engagement, "misstatements"))
    check("intake-evaluation", schedule_of(api, engagement, "evaluation"))
    check("intake-detail-run", detail(api, run["id"]))
    # The general endpoint takes the same, with the source named.
    check(
        "intake-general-note",
        post(
            api,
            f"/api/engagements/{engagement}/misstatements",
            201,
            {
                **common,
                "description": "Freight accrued twice",
                "raised_from": "note",
                "note": {"note_ref": "RN-21"},
                "lines": [{"line_no": 3, "dr": "20000.00"}, {"line_no": 5, "cr": "20000.00"}],
            },
        ),
    )
    # What each hook refuses.
    check(
        "intake-run-without-citations",
        post(
            api,
            f"{path}/run",
            422,
            {
                **common,
                "description": "x",
                "run_id": "run-7",
                "citations": [],
                "lines": [{"line_no": 5, "dr": "1.00"}, {"line_no": 3, "cr": "1.00"}],
            },
        ),
    )
    check(
        "intake-run-without-id",
        post(
            api,
            f"{path}/run",
            422,
            {
                **common,
                "description": "x",
                "citations": CITATIONS,
                "lines": [{"line_no": 5, "dr": "1.00"}, {"line_no": 3, "cr": "1.00"}],
            },
        ),
    )
    check(
        "intake-note-without-ref",
        post(
            api,
            f"{path}/note",
            422,
            {
                **common,
                "description": "x",
                "lines": [{"line_no": 5, "dr": "1.00"}, {"line_no": 3, "cr": "1.00"}],
            },
        ),
    )
    check(
        "intake-manual-without-wp",
        post(
            api,
            f"{path}/manual",
            422,
            {
                **common,
                "description": "x",
                "lines": [{"line_no": 5, "dr": "1.00"}, {"line_no": 3, "cr": "1.00"}],
            },
        ),
    )
    check(
        "intake-general-run-without-details",
        post(
            api,
            f"/api/engagements/{engagement}/misstatements",
            422,
            {
                **common,
                "description": "x",
                "raised_from": "run",
                "source_ref": "run-7",
                "lines": [{"line_no": 5, "dr": "1.00"}, {"line_no": 3, "cr": "1.00"}],
            },
        ),
    )


# The generated working paper (Pass 2, feature 7; architecture D66). One engagement with
# every kind of record, read before a run (not exportable), exported after a run, read again
# (the export current), and after a move (the export stale); the registrations; a refusal.
WORKING_PAPER_ENGAGEMENT = "Test engagement W: working paper"


def working_paper(client: TestClient, engagement: str) -> Any:
    return got(client, f"/api/engagements/{engagement}/working-paper")


def test_the_working_paper_fixtures_are_the_apis_real_answers(api: TestClient) -> None:
    use_spine(api)
    act_as(api, SENIOR)
    engagement = with_thresholds(api, WORKING_PAPER_ENGAGEMENT)
    base = f"/api/engagements/{engagement}/working-paper"
    rent = item(api, engagement, "60000.00", "Rent for March not accrued")  # M-1
    estimate = item(
        api,
        engagement,
        "35000.00",
        "Provision for doubtful debts understated",
        type="judgemental",
        range_low="30000.00",
        range_high="40000.00",
    )  # M-2
    item(
        api,
        engagement,
        "40000.00",
        "Sales cut-off errors projected over the March population",
        type="projected",
        pair=(4, 1),
        sample_ref="S-12",
        projection_basis="Ratio of error to sample value, applied to the population",
    )  # M-3
    related = item(api, engagement, "3000.00", "Sale to a related party not invoiced")  # M-4
    settled = item(api, engagement, "45000.00", "Bonus provision understated")  # M-5
    act_as(api, MANAGER)
    move(api, rent, "communicated")
    move(api, estimate, "communicated")
    move(api, estimate, "refused", "Management considers its estimate reasonable")
    move(api, settled, "communicated")
    move(api, settled, "corrected")
    post(
        api,
        f"/api/misstatements/{related}/qualitative",
        201,
        {"factor": "related_party", "note": "Sale to a firm owned by a director; see E-12"},
    )
    post(
        api,
        f"/api/engagements/{engagement}/prior-period",
        201,
        {
            "description": "Depreciation on plant understated in the prior year",
            "prior_period": "FY 2024-25",
            "source_ref": "PY schedule M-7",
            "current_profit_before_tax": "0.00",
            "current_net_assets": "-30000.00",
            "cumulative_profit_before_tax": "-30000.00",
            "cumulative_net_assets": "-30000.00",
            "basis": "Carrying amount still overstated at the year end; see PY F-3.4",
        },
    )
    # Before a run: the paper generates, and says why it cannot be exported.
    check("working-paper-no-run", working_paper(api, engagement))
    check("working-paper-export-no-run", post(api, f"{base}/export", 409, {}))

    post(api, f"/api/engagements/{engagement}/evaluation/runs", 201, REASSESSED)
    check("working-paper-ready", working_paper(api, engagement))
    exported = post(api, f"{base}/export", 201, {})
    check("working-paper-exported", exported)
    check("working-paper-export-unchanged", post(api, f"{base}/export", 409, {}))
    check("working-paper-current", working_paper(api, engagement))
    check("working-paper-exports", got(api, f"{base}/exports"))
    check("working-paper-registered", got(api, f"/api/working-papers/{exported['paper']['id']}"))

    # The engagement moves on: the export is stale until a new run and a new export.
    act_as(api, SENIOR)
    move(api, rent, "corrected")
    check("working-paper-stale", working_paper(api, engagement))
