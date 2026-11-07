"""The intake hooks (spec section 8; acceptance 1; D64): every source of a misstatement,
each with what it attaches, through its own endpoint and through the general one; balanced
Dr/Cr lines over the Spine's ledgers; the record raised in the ``raised`` state with its
origin kept on every later version."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import act_as, use_spine
from tests.test_api_evaluation import linked, thresholds
from tests.test_api_transitions import move

RENT = [{"line_no": 5, "dr": "60000.00"}, {"line_no": 3, "cr": "60000.00"}]
CITATIONS = [
    {
        "source": "sales_register.csv",
        "row": "1042",
        "detail": "Invoice dated 2 April booked in March",
    },
    {"source": "sales_register.csv", "row": "1057"},
]


def ready(api: TestClient) -> str:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    return engagement_id


def intake(api: TestClient, engagement_id: str, source: str, body: dict[str, Any]) -> Any:
    return api.post(f"/api/engagements/{engagement_id}/intake/{source}", json=body)


def general(api: TestClient, engagement_id: str, body: dict[str, Any]) -> Any:
    return api.post(f"/api/engagements/{engagement_id}/misstatements", json=body)


def base(**more: Any) -> dict[str, Any]:
    return {"type": "factual", "description": "Rent for March not accrued", "lines": RENT, **more}


def versions(api: TestClient, misstatement_id: str) -> list[dict[str, Any]]:
    answer = api.get(f"/api/misstatements/{misstatement_id}")
    assert answer.status_code == 200, answer.text
    return list(answer.json()["versions"])


# ---- each source, through its own hook ---------------------------------------------------------


def test_an_area_tester_raises_with_the_working_paper_attached(api: TestClient) -> None:
    engagement_id = ready(api)
    answer = intake(api, engagement_id, "wp", base(working_paper_ref="E-4.2"))
    assert answer.status_code == 201, answer.text
    current = answer.json()["current"]
    assert (current["raised_from"], current["source_ref"], current["origin"]) == (
        "wp",
        "E-4.2",
        None,
    )
    assert current["state"] == "raised" and current["version_no"] == 1
    assert answer.json()["ref"] == "M-1"
    # The Spine holds the lines, with the working paper as its reference.
    assert [
        (line["ledger_name"], line["dr"], line["cr"]) for line in answer.json()["spine"]["lines"]
    ] == [
        ("Rent", "60000.00", "0.00"),
        ("Provision for expenses", "0.00", "60000.00"),
    ]
    assert answer.json()["effects"]["profit_before_tax"] == "-60000.00"


def test_an_agent_runs_exception_carries_the_run_id_and_the_citations(api: TestClient) -> None:
    engagement_id = ready(api)
    act_as(api, "workmind@firm")
    answer = intake(
        api, engagement_id, "run", base(run_id="run-2026-11-07-0042", citations=CITATIONS)
    )
    assert answer.status_code == 201, answer.text
    current = answer.json()["current"]
    assert current["raised_from"] == "run"
    assert current["raised_by"] == "workmind@firm"
    # The run id is the reference; the citations are kept with it, as sent.
    assert current["source_ref"] == "run-2026-11-07-0042"
    assert current["origin"] == {
        "run_id": "run-2026-11-07-0042",
        "citations": [
            {
                "source": "sales_register.csv",
                "row": "1042",
                "detail": "Invoice dated 2 April booked in March",
            },
            {"source": "sales_register.csv", "row": "1057"},
        ],
    }
    assert current["state"] == "raised"


def test_a_review_note_is_converted_with_its_reference_and_link(api: TestClient) -> None:
    engagement_id = ready(api)
    answer = intake(
        api,
        engagement_id,
        "note",
        base(note_ref="RN-17", note_link="https://review.example.test/notes/RN-17"),
    )
    assert answer.status_code == 201, answer.text
    current = answer.json()["current"]
    assert (current["raised_from"], current["source_ref"]) == ("note", "RN-17")
    assert current["origin"] == {
        "note_ref": "RN-17",
        "note_link": "https://review.example.test/notes/RN-17",
    }
    # A link is not required: a note may live only in the binder.
    bare = intake(api, engagement_id, "note", base(note_ref="RN-18"))
    assert bare.status_code == 201, bare.text
    assert bare.json()["current"]["origin"] == {"note_ref": "RN-18", "note_link": None}


def test_a_manual_entry_is_allowed_and_requires_a_working_paper(api: TestClient) -> None:
    engagement_id = ready(api)
    answer = intake(api, engagement_id, "manual", base(working_paper_ref="C-9.1"))
    assert answer.status_code == 201, answer.text
    current = answer.json()["current"]
    assert (current["raised_from"], current["source_ref"], current["origin"]) == (
        "manual",
        "C-9.1",
        None,
    )
    refused = intake(api, engagement_id, "manual", base())
    assert refused.status_code == 422
    assert "working_paper_ref" in refused.text


def test_sampling_arrives_as_a_projected_misstatement_naming_its_sample(api: TestClient) -> None:
    engagement_id = ready(api)
    answer = intake(
        api,
        engagement_id,
        "wp",
        base(
            type="projected",
            working_paper_ref="R-5.3",
            sample_ref="S-12",
            projection_basis="Ratio of error to sample value, applied to the population",
        ),
    )
    assert answer.status_code == 201, answer.text
    current = answer.json()["current"]
    assert (current["type"], current["sample_ref"]) == ("projected", "S-12")
    without = intake(api, engagement_id, "wp", base(type="projected", working_paper_ref="R-5.3"))
    assert without.status_code == 422 and "sample_ref" in without.text


# ---- the same through the general endpoint ----------------------------------------------------


def test_the_general_endpoint_takes_every_source_with_its_attribution(api: TestClient) -> None:
    engagement_id = ready(api)
    wp = general(api, engagement_id, base(raised_from="wp", source_ref="E-4.2"))
    run = general(
        api,
        engagement_id,
        base(raised_from="run", run={"run_id": "run-7", "citations": CITATIONS[:1]}),
    )
    note = general(api, engagement_id, base(raised_from="note", note={"note_ref": "RN-3"}))
    manual = general(api, engagement_id, base(raised_from="manual", source_ref="C-1"))
    for answer in (wp, run, note, manual):
        assert answer.status_code == 201, answer.text
    assert [a.json()["current"]["raised_from"] for a in (wp, run, note, manual)] == [
        "wp",
        "run",
        "note",
        "manual",
    ]
    assert run.json()["current"]["source_ref"] == "run-7"
    assert run.json()["current"]["origin"]["citations"] == [CITATIONS[0]]
    assert note.json()["current"]["origin"] == {"note_ref": "RN-3", "note_link": None}
    # The hooks and the general endpoint write the same record.
    hooked = intake(api, engagement_id, "run", base(run_id="run-7", citations=CITATIONS[:1]))
    assert hooked.status_code == 201
    assert hooked.json()["current"]["origin"] == run.json()["current"]["origin"]
    assert hooked.json()["ref"] == "M-5"


# ---- what is refused --------------------------------------------------------------------------


def test_acceptance_1_unbalanced_or_single_lines_are_refused_by_every_hook(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    attributions: dict[str, dict[str, Any]] = {
        "wp": {"working_paper_ref": "E-4.2"},
        "run": {"run_id": "run-7", "citations": CITATIONS[:1]},
        "note": {"note_ref": "RN-3"},
        "manual": {"working_paper_ref": "C-1"},
    }
    for source, attribution in attributions.items():
        unbalanced = intake(
            api,
            engagement_id,
            source,
            base(
                lines=[{"line_no": 5, "dr": "60000.00"}, {"line_no": 3, "cr": "59999.99"}],
                **attribution,
            ),
        )
        assert unbalanced.status_code == 422, source
        assert "must balance" in unbalanced.text
        single = intake(
            api,
            engagement_id,
            source,
            base(lines=[{"line_no": 5, "dr": "60000.00"}], **attribution),
        )
        assert single.status_code == 422, source
        amount_only = intake(
            api, engagement_id, source, {**base(**attribution), "lines": [], "amount": "60000.00"}
        )
        assert amount_only.status_code == 422, source
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []


def test_a_source_cannot_arrive_without_its_attribution(api: TestClient) -> None:
    engagement_id = ready(api)
    refusals = [
        ("wp", base(), "working_paper_ref"),
        ("wp", base(working_paper_ref="   "), "working_paper_ref"),
        ("run", base(citations=CITATIONS), "run_id"),
        ("run", base(run_id="run-7"), "citations"),
        ("run", base(run_id="run-7", citations=[]), "citations"),
        ("run", base(run_id="run-7", citations=[{"source": "x"}]), "row"),
        ("run", base(run_id="run-7", citations=[{"row": "1"}]), "source"),
        ("run", base(run_id="run-7", citations=[{"source": "x", "row": "1", "page": 2}]), "page"),
        ("note", base(), "note_ref"),
        ("note", base(note_ref="  "), "note_ref"),
        ("manual", base(), "working_paper_ref"),
        # A hook takes only its own attribution.
        ("wp", base(working_paper_ref="E-1", run_id="run-7"), "run_id"),
        (
            "run",
            base(run_id="run-7", citations=CITATIONS, working_paper_ref="E-1"),
            "working_paper_ref",
        ),
        ("note", base(note_ref="RN-1", citations=CITATIONS), "citations"),
        # Who raised it is never taken from the request.
        ("wp", base(working_paper_ref="E-1", raised_by="partner@firm"), "raised_by"),
        ("wp", base(working_paper_ref="E-1", state="communicated"), "state"),
    ]
    for source, body, field in refusals:
        answer = intake(api, engagement_id, source, body)
        assert answer.status_code == 422, (source, body)
        assert field in answer.text, (source, field)
    # And through the general endpoint, the source and what it attaches must agree.
    for body, words in (
        (base(raised_from="run", source_ref="E-1"), "run.run_id"),
        (base(raised_from="run", run={"run_id": "run-7", "citations": []}), "citations"),
        (base(raised_from="note", source_ref="RN-1"), "note.note_ref"),
        (base(raised_from="wp"), "working paper reference"),
        (base(raised_from="manual"), "working paper reference"),
        (
            base(raised_from="wp", source_ref="E-1", run={"run_id": "r", "citations": CITATIONS}),
            "only a run",
        ),
        (
            base(raised_from="run", run={"run_id": "r", "citations": CITATIONS}, source_ref="E-1"),
            "not source_ref",
        ),
        (base(raised_from="sampling", source_ref="S-1"), "raised_from"),
    ):
        answer = general(api, engagement_id, body)
        assert answer.status_code == 422, body
        assert words in answer.text, (words, answer.text)
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []
    # An unknown source has no hook.
    assert intake(api, engagement_id, "sampling", base(working_paper_ref="S-1")).status_code == 404
    assert intake(api, str(uuid.uuid4()), "wp", base(working_paper_ref="E-1")).status_code == 404
    act_as(api, None)
    assert intake(api, engagement_id, "wp", base(working_paper_ref="E-1")).status_code == 503


def test_a_hook_needs_a_spine_like_the_general_endpoint(api: TestClient) -> None:
    use_spine(api)
    unlinked = api.post("/api/engagements", json={"label": "FY26, unlinked"}).json()["id"]
    answer = intake(api, unlinked, "run", base(run_id="run-7", citations=CITATIONS))
    assert answer.status_code == 409
    assert "no Financial Spine version is pinned" in answer.json()["detail"]


# ---- the origin stays with the record --------------------------------------------------------


def test_the_origin_is_copied_onto_every_later_version_and_never_changes(api: TestClient) -> None:
    engagement_id = ready(api)
    raised = intake(api, engagement_id, "run", base(run_id="run-7", citations=CITATIONS)).json()
    assert move(api, raised["id"], "communicated").status_code == 201
    assert move(api, raised["id"], "refused", "Management disputes the run").status_code == 201
    trail = versions(api, raised["id"])
    assert [v["state"] for v in trail] == ["raised", "communicated", "refused"]
    for version in trail:
        assert (version["raised_from"], version["source_ref"]) == ("run", "run-7")
        assert version["origin"] == raised["current"]["origin"]
    # The schedule carries it too.
    row = api.get(f"/api/engagements/{engagement_id}/misstatements").json()[0]
    assert row["current"]["origin"]["run_id"] == "run-7"
    assert len(row["current"]["origin"]["citations"]) == 2
