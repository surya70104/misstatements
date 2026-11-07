"""The generated working paper (SA 230; SA 450 paragraph 15; spec section 6 item 5; D66):
the engagement's whole record as one structured paper; the three things paragraph 15
requires, checked; the export that freezes the paper against the current evaluation run,
with a hash that is reproducible; and what the Binder would receive."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from oak_misstatements.core import working_paper as core
from oak_misstatements.models.guard import AppendOnlyViolation
from oak_misstatements.models.working_paper import WorkingPaper
from tests.conftest import act_as, use_spine
from tests.test_api_conclusions import conclude, record
from tests.test_api_evaluation import (
    SENIOR,
    evaluation,
    header_mode,
    linked,
    raise_item,
    thresholds,
)
from tests.test_api_evaluation_runs import run
from tests.test_api_sampling import projected
from tests.test_api_tcwg import escalate
from tests.test_api_transitions import move


def ready(api: TestClient) -> str:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)  # OM 4,00,000; PM 2,50,000; CTT 12,500
    return engagement_id


def paper(api: TestClient, engagement_id: str, **kwargs: Any) -> Any:
    answer = api.get(f"/api/engagements/{engagement_id}/working-paper", **kwargs)
    assert answer.status_code == 200, answer.text
    return answer.json()


def export(api: TestClient, engagement_id: str, **kwargs: Any) -> Any:
    return api.post(f"/api/engagements/{engagement_id}/working-paper/export", **kwargs)


def exports(api: TestClient, engagement_id: str) -> Any:
    answer = api.get(f"/api/engagements/{engagement_id}/working-paper/exports")
    assert answer.status_code == 200, answer.text
    return answer.json()


def full_record(api: TestClient, engagement_id: str) -> dict[str, Any]:
    """An engagement with every kind of record the paper gathers."""
    rent = raise_item(api, engagement_id, "60000.00")  # M-1, factual, communicated
    assert move(api, rent["id"], "communicated").status_code == 201
    estimate = raise_item(api, engagement_id, "35000.00", type="judgemental")  # M-2, refused
    assert move(api, estimate["id"], "communicated").status_code == 201
    assert move(api, estimate["id"], "refused", "Management disagrees").status_code == 201
    sampled = api.post(f"/api/engagements/{engagement_id}/misstatements", json=projected())  # M-3
    assert sampled.status_code == 201, sampled.text
    small = raise_item(api, engagement_id, "3000.00")  # M-4, escalated
    escalate(api, small["id"], "related_party", "Sale to a director's firm; see E-12")
    settled = raise_item(api, engagement_id, "45000.00")  # M-5, corrected
    assert move(api, settled["id"], "communicated").status_code == 201
    assert move(api, settled["id"], "corrected").status_code == 201
    carried = api.post(
        f"/api/engagements/{engagement_id}/prior-period",
        json={
            "description": "Depreciation understated in the prior year",
            "prior_period": "FY 2024-25",
            "source_ref": "PY schedule M-7",
            "current_profit_before_tax": "0.00",
            "current_net_assets": "-30000.00",
            "cumulative_profit_before_tax": "-30000.00",
            "cumulative_net_assets": "-30000.00",
            "basis": "Still stands at the year end",
        },
    )
    assert carried.status_code == 201, carried.text
    return {"rent": rent, "estimate": estimate, "small": small, "sampled": sampled.json()}


# ---- the paper -------------------------------------------------------------------------------


def test_the_paper_gathers_the_whole_record_of_the_engagement(api: TestClient) -> None:
    engagement_id = ready(api)
    full_record(api, engagement_id)
    assert run(api, engagement_id).status_code == 201
    answer = paper(api, engagement_id)

    assert answer["paper"] == {
        "title": core.TITLE,
        "standards": ["SA 450", "SA 230"],
        "module": "misstatements-rollup",
        "module_version": "0.1.0",
    }
    # The engagement and its Spine link.
    assert answer["engagement"]["id"] == engagement_id
    assert answer["engagement"]["spine"]["status"] == "verified"
    # The thresholds, and that materiality was reassessed at the run.
    assert answer["thresholds"]["current"]["version_no"] == 1
    assert answer["thresholds"]["current"]["ctt"] == "12500.00"
    assert [v["version_no"] for v in answer["thresholds"]["history"]] == [1]
    assert answer["materiality_reassessment"]["runs"] == [1]
    assert [e["kind"] for e in answer["materiality_reassessment"]["events"]] == [
        "materiality_reassessed"
    ]
    # Every misstatement, with its lines, effects, band, trail, origin, factors and sample.
    by_ref = {m["ref"]: m for m in answer["misstatements"]}
    assert list(by_ref) == ["M-1", "M-2", "M-3", "M-4", "M-5"]
    assert [line["ledger_name"] for line in by_ref["M-1"]["spine"]["lines"]] == [
        "Rent",
        "Provision for expenses",
    ]
    assert by_ref["M-1"]["effects"]["profit_before_tax"] == "-60000.00"
    assert by_ref["M-1"]["band"] == "accumulated"
    assert [v["state"] for v in by_ref["M-2"]["versions"]] == ["raised", "communicated", "refused"]
    assert by_ref["M-2"]["current"]["refusal_reason"] == "Management disagrees"
    assert by_ref["M-2"]["current"]["range_low"] == "35000.00"
    assert by_ref["M-3"]["current"]["sampling"]["method"] == "ratio"
    assert by_ref["M-3"]["current"]["sample_ref"] == "S-12"
    assert by_ref["M-4"]["qualitative"]["escalated"] is True
    assert (
        by_ref["M-4"]["qualitative"]["history"][0]["note"] == "Sale to a director's firm; see E-12"
    )
    assert by_ref["M-1"]["current"]["raised_from"] == "wp"
    assert by_ref["M-5"]["current"]["state"] == "corrected"
    # The prior-period items, the evaluation, the runs, the events, the two documents.
    assert [item["ref"] for item in answer["prior_period"]["items"]] == ["PY-1"]
    assert answer["evaluation"]["aggregate"]["counted"] == ["M-1", "M-2", "M-3", "M-4"]
    assert answer["evaluation"]["prior_period"]["items"][0]["ref"] == "PY-1"
    assert [r["run_no"] for r in answer["runs"]] == [1]
    assert answer["runs"][0]["py_carried"]["items"] == [{"ref": "PY-1", "version_no": 1}]
    assert answer["conclusions"] == []
    assert "materiality_reassessed" in [e["kind"] for e in answer["events"]]
    assert answer["tcwg_extract"]["counts"]["communicated"] == 4
    assert answer["representation_attachment"]["schedule"]["count"] == 4
    assert "SA 450 paragraph 15" in answer["basis"]
    # No authorisation notice anywhere inside the paper: it hashes the same anywhere.
    assert "authorisation" not in json.dumps(
        {k: v for k, v in answer.items() if k != "authorisation"}
    )
    assert answer["authorisation"]["enforced"] is False


def test_sa_450_paragraph_15_is_documented_as_fields(api: TestClient) -> None:
    engagement_id = ready(api)
    full_record(api, engagement_id)
    documentation = paper(api, engagement_id)["documentation"]
    assert documentation["standard"] == "SA 450 paragraph 15"
    assert documentation["clearly_trivial_amount"] == {
        "documented": True,
        "amount": "12500.00",
        "fraction_of_pm": "0.05",
        "basis": "C-1",
        "threshold_version_no": 1,
    }
    assert documentation["misstatements_accumulated_and_whether_corrected"] == {
        "documented": True,
        "count": 5,
        "uncorrected": ["M-1", "M-2", "M-3", "M-4"],
        "corrected": ["M-5"],
        "withdrawn": [],
    }
    # No conclusion yet: that is said, and the documentation is not complete.
    assert documentation["conclusion_and_basis"]["documented"] is False
    assert documentation["complete"] is False


def test_the_conclusion_and_its_basis_are_documented_once_a_partner_concludes(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    item = raise_item(api, engagement_id, "60000.00")
    assert move(api, item["id"], "communicated").status_code == 201
    proxy = header_mode(api, roles=True)
    reviewed = record(proxy, engagement_id)
    assert conclude(proxy, engagement_id, "not-material", reviewed["id"]).status_code == 201
    answer = paper(proxy, engagement_id, headers=SENIOR)
    concluded = answer["documentation"]["conclusion_and_basis"]
    assert concluded["documented"] is True
    assert concluded["determination"] == "not_material"
    assert concluded["conclusion"].startswith("Uncorrected misstatements are not material")
    assert concluded["basis"].startswith("The aggregate is below performance materiality")
    assert (concluded["concluded_by"], concluded["run_no"], concluded["status"]) == (
        "partner@firm",
        2,
        "current",
    )
    assert answer["documentation"]["complete"] is True
    assert [c["run_no"] for c in answer["conclusions"]] == [2]
    assert [r["run_no"] for r in answer["runs"]] == [2, 1]
    assert "evaluation_concluded" in [e["kind"] for e in answer["events"]]


def test_without_thresholds_the_paper_still_generates_and_says_what_is_missing(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    raise_item(api, engagement_id, "60000.00")
    answer = paper(api, engagement_id)
    assert answer["thresholds"]["current"] is None
    assert answer["documentation"]["clearly_trivial_amount"]["documented"] is False
    assert answer["documentation"]["complete"] is False
    assert answer["exportable"]["allowed"] is False
    assert any("no thresholds" in reason for reason in answer["exportable"]["reasons"])
    assert answer["export"]["status"] == "none"


# ---- the export: frozen, reproducible, tied to a run ----------------------------------------


def test_the_export_is_refused_until_a_current_run_records_the_figures(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")
    answer = paper(api, engagement_id)
    assert answer["exportable"] == {
        "allowed": False,
        "reasons": [
            "no evaluation run records the figures as they stand: record a run first, so the "
            "paper rests on a recorded evaluation (SA 450 paragraph 15; architecture D66)"
        ],
    }
    refused = export(api, engagement_id)
    assert refused.status_code == 409
    assert "record a run first" in refused.json()["detail"]
    # A run that has gone stale is refused too.
    assert run(api, engagement_id).status_code == 201
    raise_item(api, engagement_id, "40000.00")
    stale = export(api, engagement_id)
    assert stale.status_code == 409
    assert "no longer records the figures" in stale.json()["detail"]
    assert exports(api, engagement_id) == []


def test_the_export_freezes_the_paper_with_a_reproducible_hash(api: TestClient) -> None:
    engagement_id = ready(api)
    full_record(api, engagement_id)
    recorded = run(api, engagement_id).json()
    first = paper(api, engagement_id)
    # The same content hashes the same on every read.
    assert paper(api, engagement_id)["content_hash"] == first["content_hash"]
    assert len(first["content_hash"]) == 64
    assert first["exportable"] == {"allowed": True, "reasons": []}

    act_as(api, "manager@firm")
    answer = export(api, engagement_id)
    assert answer.status_code == 201, answer.text
    registered = answer.json()["paper"]
    assert registered["paper_no"] == 1
    assert registered["run_no"] == 1
    assert registered["evaluation_run_id"] == recorded["id"]
    assert registered["generated_by"] == "manager@firm"
    assert registered["content_hash"] == first["content_hash"]
    # The live paper now says the latest export matches it.
    assert paper(api, engagement_id)["export"] == {
        "status": "current",
        "latest": registered,
    }
    # The registered paper is the content exactly, and its hash is the hash of that content.
    stored = api.get(f"/api/working-papers/{registered['id']}").json()
    content = stored["content"]
    expected = {
        k: v
        for k, v in first.items()
        if k not in ("content_hash", "exportable", "export", "authorisation")
    }
    assert content == expected
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == registered["content_hash"]
    assert stored["verification"] == {
        "recorded_hash": registered["content_hash"],
        "recomputed_hash": registered["content_hash"],
        "matches": True,
    }
    assert "authorisation" not in json.dumps(content)
    assert [p["paper_no"] for p in exports(api, engagement_id)] == [1]


def test_nothing_changed_means_nothing_to_export_and_a_change_means_a_new_paper(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    rent = raise_item(api, engagement_id, "60000.00")
    assert run(api, engagement_id).status_code == 201
    assert export(api, engagement_id).status_code == 201
    again = export(api, engagement_id)
    assert again.status_code == 409
    assert "nothing has changed since paper 1" in again.json()["detail"]

    # The engagement moves on: the latest export is stale, and a new run allows paper 2.
    assert move(api, rent["id"], "communicated").status_code == 201
    live = paper(api, engagement_id)
    assert live["export"]["status"] == "stale"
    assert live["exportable"]["allowed"] is False
    assert run(api, engagement_id).status_code == 201
    second = export(api, engagement_id)
    assert second.status_code == 201, second.text
    assert second.json()["paper"]["paper_no"] == 2
    assert second.json()["paper"]["run_no"] == 2
    assert [p["paper_no"] for p in exports(api, engagement_id)] == [2, 1]
    # Paper 1 is exactly as it was frozen.
    first_id = exports(api, engagement_id)[1]["id"]
    frozen = api.get(f"/api/working-papers/{first_id}").json()
    assert frozen["content"]["misstatements"][0]["current"]["state"] == "raised"
    assert frozen["verification"]["matches"] is True
    assert api.get(f"/api/working-papers/{uuid.uuid4()}").status_code == 404


def test_a_registered_paper_can_never_be_changed_or_deleted(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")
    assert run(api, engagement_id).status_code == 201
    assert export(api, engagement_id).status_code == 201
    factory = cast(FastAPI, api.app).state.session_factory
    with factory() as session:
        row = session.scalars(select(WorkingPaper)).one()
        row.content_hash = "0" * 64
        with pytest.raises(AppendOnlyViolation, match="never an update"):
            session.flush()
    with factory() as session:
        row = session.scalars(select(WorkingPaper)).one()
        session.delete(row)
        with pytest.raises(AppendOnlyViolation, match="never deleted"):
            session.flush()
    with factory() as session:
        with pytest.raises(AppendOnlyViolation, match="UPDATE is not allowed"):
            session.execute(update(WorkingPaper).values(paper_no=9))
        with pytest.raises(AppendOnlyViolation, match="DELETE is not allowed"):
            session.execute(delete(WorkingPaper))
    assert exports(api, engagement_id)[0]["paper_no"] == 1


def test_an_export_needs_an_identity_and_an_engagement(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")
    assert run(api, engagement_id).status_code == 201
    assert export(api, str(uuid.uuid4())).status_code == 404
    assert api.get(f"/api/engagements/{uuid.uuid4()}/working-paper").status_code == 404
    act_as(api, None)
    assert export(api, engagement_id).status_code == 503
    act_as(api, "senior@firm")
    assert exports(api, engagement_id) == []


# ---- the Binder --------------------------------------------------------------------------------


def test_the_delivery_is_in_the_binders_shape_and_is_not_sent(api: TestClient) -> None:
    engagement_id = ready(api)
    full_record(api, engagement_id)
    assert run(api, engagement_id).status_code == 201
    answer = export(api, engagement_id).json()
    delivery = answer["binder_delivery"]
    assert delivery["deliverable"] is False
    assert "has no source for this module" in delivery["not_deliverable_because"]
    assert delivery["binder_endpoint"] == "POST /api/binders/{binder_id}/generated-papers"
    assert delivery["paper"]["ref"] == "W-SA450-1"
    assert delivery["paper"]["section"] == "W"
    assert delivery["paper"]["sa_refs"] == ["SA 450", "SA 230"]
    assert "content hash " + answer["paper"]["content_hash"] in delivery["paper"]["procedure"]
    assert "5 misstatements recorded" in delivery["paper"]["result"]
    assert "profit before tax gross 138000.00" in delivery["paper"]["result"]
    assert delivery["paper"]["conclusion"] is None  # no partner has concluded
    generated = delivery["generated"]
    assert generated["source"] is None
    assert generated["module"] == "misstatements-rollup"
    assert generated["run_id"] == answer["paper"]["evaluation_run_id"]
    assert generated["inputs"]["content_hash"] == answer["paper"]["content_hash"]
    assert generated["inputs"]["threshold_version_no"] == 1
    assert [c["ref"] for c in generated["citations"]] == [
        "M-1",
        "M-2",
        "M-3",
        "M-4",
        "M-5",
        "evaluation run 1",
    ]
    # Nothing was sent anywhere: the only writes are the paper's own row and the run.
    events_ = api.get(f"/api/engagements/{engagement_id}/events").json()
    assert [e["kind"] for e in events_].count("materiality_reassessed") == 1


# ---- the pieces themselves ----------------------------------------------------------------------


def test_the_hash_is_of_canonical_json_and_ignores_every_authorisation_block() -> None:
    content = {"b": 1, "a": {"authorisation": {"x": 1}, "y": [{"authorisation": 2, "z": "é"}]}}
    stripped = core.without_authorisation(content)
    assert stripped == {"b": 1, "a": {"y": [{"z": "é"}]}}
    assert core.canonical(stripped) == '{"a":{"y":[{"z":"é"}]},"b":1}'
    assert (
        core.content_hash(stripped)
        == hashlib.sha256('{"a":{"y":[{"z":"é"}]},"b":1}'.encode()).hexdigest()
    )
    assert core.content_hash({"b": 1, "a": 2}) == core.content_hash({"a": 2, "b": 1})
    assert "paragraph 15" in core.WORKING_PAPER_BASIS
    evaluated = evaluation  # the import is used by other suites; keep the name bound
    assert callable(evaluated)
