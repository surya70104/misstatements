"""Projected misstatements from Sampling (SA 530; SA 450 paragraph A3; spec section 3.2;
D65): a projected item names its sample and says how it was projected, the lines carry the
projected amount and are proposed to the Spine like any other, and the aggregate keeps the
projected items apart, with and without them (spec 3.2: "never aggregated as if it were
factual without saying so")."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from oak_misstatements.schemas.misstatements import MisstatementIn
from tests.conftest import use_spine
from tests.test_api_evaluation import SAMPLING, evaluation, linked, raise_item, thresholds
from tests.test_api_evaluation_runs import run
from tests.test_api_transitions import move

LINES = [{"line_no": 4, "dr": "40000.00"}, {"line_no": 1, "cr": "40000.00"}]


def ready(api: TestClient) -> str:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)  # OM 4,00,000; PM 2,50,000; CTT 12,500
    return engagement_id


def projected(**more: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "projected",
        "description": "Sales cut-off errors projected over the March population",
        "raised_from": "wp",
        "source_ref": "R-5.3",
        "lines": LINES,
        "sample_ref": "S-12",
        "projection_basis": "Ratio of error to sample value, applied to the population",
        "sampling_method": "ratio",
        "population_value": "4000000.00",
        "population_size": 1200,
        "sample_value": "400000.00",
        "sample_size": 120,
        "known_error_in_sample": "4000.00",
        "projected_amount": "40000.00",
    }
    body.update(more)
    return {key: value for key, value in body.items() if value is not ...}


def raise_body(api: TestClient, engagement_id: str, body: dict[str, Any]) -> Any:
    return api.post(f"/api/engagements/{engagement_id}/misstatements", json=body)


# ---- what a projected item records ---------------------------------------------------------------


def test_a_projected_item_records_its_sample_its_method_and_the_projection(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    answer = raise_body(api, engagement_id, projected())
    assert answer.status_code == 201, answer.text
    record = answer.json()
    current = record["current"]
    assert (current["type"], current["sample_ref"]) == ("projected", "S-12")
    assert current["projection_basis"].startswith("Ratio of error")
    assert current["sampling"] == {
        "method": "ratio",
        "population_value": "4000000.00",
        "population_size": 1200,
        "sample_value": "400000.00",
        "sample_size": 120,
        "known_error_in_sample": "4000.00",
    }
    # The projected amount is the lines, proposed to the Spine like any other misstatement:
    # it is not a figure of its own anywhere in this module.
    assert "projected_amount" not in current
    assert [(line["ledger_name"], line["dr"], line["cr"]) for line in record["spine"]["lines"]] == [
        ("Sales", "40000.00", "0.00"),
        ("Alpha Traders", "0.00", "40000.00"),
    ]
    assert record["spine"]["adjustment_status"] == "proposed"
    assert record["banding"]["projected"] is True
    assert record["effects"]["profit_before_tax"] == "-40000.00"
    assert current["state"] == "raised"
    # Every other type carries none of it.
    factual = raise_item(api, engagement_id, "60000.00")
    assert factual["current"]["sampling"] is None


def test_the_sampling_details_stay_on_every_later_version(api: TestClient) -> None:
    engagement_id = ready(api)
    record = raise_body(api, engagement_id, projected()).json()
    assert move(api, record["id"], "communicated").status_code == 201
    assert (
        move(api, record["id"], "refused", "Management disputes the projection").status_code == 201
    )
    read = api.get(f"/api/misstatements/{record['id']}").json()
    assert [v["state"] for v in read["versions"]] == ["raised", "communicated", "refused"]
    for version in read["versions"]:
        assert version["sampling"] == record["current"]["sampling"]
        assert version["sample_ref"] == "S-12"


def test_a_projected_item_can_arrive_through_an_intake_hook(api: TestClient) -> None:
    engagement_id = ready(api)
    body = projected(raised_from=..., source_ref=..., working_paper_ref="R-5.3")
    answer = api.post(f"/api/engagements/{engagement_id}/intake/wp", json=body)
    assert answer.status_code == 201, answer.text
    assert answer.json()["current"]["sampling"]["method"] == "ratio"
    assert answer.json()["current"]["raised_from"] == "wp"


# ---- acceptance: it accumulates, and is kept apart ----------------------------------------------


def test_a_projected_item_accumulates_and_the_aggregate_is_shown_with_and_without_it(
    api: TestClient,
) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "60000.00")  # M-1, factual
    answer = raise_body(api, engagement_id, projected())  # M-2, projected 40,000
    assert answer.status_code == 201, answer.text
    live = evaluation(api, engagement_id)
    total = live["aggregate"]
    assert total["counted"] == ["M-1", "M-2"]
    assert total["projected"] == ["M-2"]
    for measure in ("profit_before_tax", "net_assets"):
        assert total[measure]["gross"] == "100000.00"
        assert total[measure]["net"] == "-100000.00"
        assert total[measure]["gross_without_projected"] == "60000.00"
        assert total[measure]["net_without_projected"] == "-60000.00"
        assert total[measure]["projected_gross"] == "40000.00"
        assert total[measure]["factual_gross"] == "60000.00"
    # The gates say whether they depend on the projected items.
    assert live["gates"]["hard"]["depends_on_projected"] is False
    # A run records it the same way.
    recorded = run(api, engagement_id).json()
    assert recorded["agg_gross_pbt"] == "100000.00"
    assert recorded["detail"]["projected"] == ["M-2"]
    assert recorded["detail"]["figures"]["profit_before_tax"]["projected_gross"] == "40000.00"
    assert [item["type"] for item in recorded["detail"]["items"]] == ["factual", "projected"]
    # And the representation attachment and the TCWG extract keep the type apart.
    attachment = api.get(f"/api/engagements/{engagement_id}/rep-letter-attachment").json()
    by_type = {entry["type"]: entry for entry in attachment["schedule"]["by_type"]}
    assert by_type["projected"]["count"] == 1
    assert by_type["projected"]["profit_before_tax"]["gross"] == "40000.00"


def test_a_gate_reached_only_with_the_projected_item_says_so(api: TestClient) -> None:
    engagement_id = ready(api)
    raise_item(api, engagement_id, "230000.00")
    answer = raise_body(
        api,
        engagement_id,
        projected(
            lines=[{"line_no": 4, "dr": "30000.00"}, {"line_no": 1, "cr": "30000.00"}],
            projected_amount="30000.00",
        ),
    )
    assert answer.status_code == 201, answer.text
    soft = evaluation(api, engagement_id)["gates"]["soft"]
    assert soft["status"] == "fires"  # 2,60,000 at or above PM 2,50,000
    assert soft["depends_on_projected"] is True
    assert soft["fires_without_projected"] is False


# ---- what is refused ----------------------------------------------------------------------------


def test_a_projected_item_without_its_sampling_details_is_refused(api: TestClient) -> None:
    engagement_id = ready(api)
    for change, words in (
        ({"sample_ref": ...}, "sample_ref and projection_basis"),
        ({"projection_basis": ...}, "sample_ref and projection_basis"),
        ({"sampling_method": ...}, "sampling_method required"),
        ({"population_value": ...}, "population_value required"),
        ({"population_size": ...}, "population_size required"),
        ({"sample_value": ...}, "sample_value required"),
        ({"sample_size": ...}, "sample_size required"),
        ({"known_error_in_sample": ...}, "known_error_in_sample required"),
        ({"projected_amount": ...}, "projected_amount required"),
        ({"sampling_method": "haphazard"}, "sampling_method"),
        ({"sample_size": 1300}, "sample_size cannot exceed population_size"),
        ({"sample_value": "5000000.00"}, "sample_value cannot exceed population_value"),
        ({"population_size": 0}, "population_size"),
        ({"population_value": "0.00"}, "population_value"),
        ({"sample_value": "-1.00"}, "sample_value"),
        ({"population_value": "1.005"}, "population_value"),
    ):
        answer = raise_body(api, engagement_id, projected(**change))
        assert answer.status_code == 422, change
        assert words in answer.text, (change, answer.text)
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []


def test_the_lines_carry_the_projected_amount_and_a_different_figure_is_refused(
    api: TestClient,
) -> None:
    """Spec section 3.1 and acceptance 1: a misstatement is its lines, never a separate
    amount. The projected amount is checked against the debits and is not stored."""
    engagement_id = ready(api)
    answer = raise_body(api, engagement_id, projected(projected_amount="45000.00"))
    assert answer.status_code == 422
    assert "debits 40000.00 differ from projected_amount 45000.00" in answer.text
    # Unbalanced lines are refused before anything else, for a projected item too.
    unbalanced = raise_body(
        api,
        engagement_id,
        projected(lines=[{"line_no": 4, "dr": "40000.00"}, {"line_no": 1, "cr": "39000.00"}]),
    )
    assert unbalanced.status_code == 422 and "must balance" in unbalanced.text
    # An amount with no lines is not a misstatement at all.
    amount_only = raise_body(api, engagement_id, {**projected(), "lines": []})
    assert amount_only.status_code == 422
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []


def test_sampling_details_on_a_factual_or_judgemental_item_are_refused(api: TestClient) -> None:
    engagement_id = ready(api)
    for change in (
        {"sampling_method": "ratio"},
        {"population_value": "1000.00"},
        {"sample_size": 10},
        {"projected_amount": "60000.00"},
    ):
        answer = raise_body(
            api,
            engagement_id,
            {
                "type": "factual",
                "description": "x",
                "raised_from": "wp",
                "source_ref": "E-1",
                "lines": [{"line_no": 5, "dr": "60000.00"}, {"line_no": 3, "cr": "60000.00"}],
                **change,
            },
        )
        assert answer.status_code == 422, change
        assert "only a projected misstatement" in answer.text
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []


def test_the_schema_holds_the_same_rules_without_a_database() -> None:
    ok = MisstatementIn(**projected())
    assert ok.projected_amount == Decimal("40000.00") and ok.sample_size == 120
    assert ok.common()["sampling_method"] == "ratio"
    with pytest.raises(ValidationError, match="sampling_method"):
        MisstatementIn(**projected(sampling_method=...))
    with pytest.raises(ValidationError, match="differ from projected_amount"):
        MisstatementIn(**projected(projected_amount="1.00"))
    with pytest.raises(ValidationError, match="only a projected"):
        MisstatementIn(**projected(type="factual", sample_ref=..., projection_basis=...))
    assert SAMPLING["sampling_method"] == "ratio"
