"""The evaluation over the API (spec sections 4.1, 7, 10.3; D37, D38, D39): the aggregate
with and without projected items, the gates at their exact boundaries, classification-only
items listed at nil, unresolved items making the gate indeterminate, the write-path block,
and the partner-only acknowledgement that fails closed without a trusted role claim."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oak_misstatements.models import Engagement
from oak_misstatements.services.evaluation import (
    GateBlocked,
    evaluate,
    require_sign_off_open,
)
from tests.conftest import act_as, use_spine
from tests.fake_spine import ENGAGEMENT_ID, OPEN_VERSION_ID

ROLES = "X-Authenticated-Roles"
PARTNER = {"X-Authenticated-User": "partner@firm", ROLES: "staff, engagement-partner"}
SENIOR = {"X-Authenticated-User": "senior@firm", ROLES: "staff"}


def linked(api: TestClient) -> str:
    created = api.post(
        "/api/engagements",
        json={
            "label": "FY26",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(OPEN_VERSION_ID),
        },
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def thresholds(api: TestClient, engagement_id: str, **overrides: Any) -> Any:
    values: dict[str, Any] = {
        "om": "400000.00",
        "pm": "250000.00",
        "ctt_fraction": "0.05",
        "basis": "C-1",
    }
    values.update(overrides)
    answer = api.post(f"/api/engagements/{engagement_id}/thresholds", json=values)
    assert answer.status_code == 201, answer.text
    return answer.json()


def raise_item(
    api: TestClient,
    engagement_id: str,
    amount: str,
    *,
    type: str = "factual",
    lines: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    body: dict[str, Any] = {
        "type": type,
        "description": f"{type} item of {amount}",
        "raised_from": "wp",
        "source_ref": "E-1",
        "lines": lines or [{"line_no": 5, "dr": amount}, {"line_no": 3, "cr": amount}],
    }
    if type == "projected":
        body |= {"sample_ref": "S-1", "projection_basis": "ratio of error in the sample"}
    if type == "judgemental":
        body |= {"range_low": amount, "range_high": amount}
    answer = api.post(f"/api/engagements/{engagement_id}/misstatements", json=body, headers=headers)
    assert answer.status_code == 201, answer.text
    return answer.json()


def evaluation(api: TestClient, engagement_id: str) -> Any:
    answer = api.get(f"/api/engagements/{engagement_id}/evaluation")
    assert answer.status_code == 200, answer.text
    return answer.json()


# ---- no thresholds, nothing raised ---------------------------------------------------------


def test_without_thresholds_no_gate_can_be_evaluated_and_sign_off_is_blocked(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    answer = evaluation(api, engagement_id)
    assert answer["threshold"] is None
    assert answer["gates"]["hard"]["status"] == "no_thresholds"
    assert answer["gates"]["hard"]["blocks"] is True
    assert answer["sign_off"] == {
        "blocked": True,
        "reasons": ["no thresholds have been set, so no gate can be evaluated"],
        "enforced_in": answer["sign_off"]["enforced_in"],
    }
    assert "sign_off_open" in answer["sign_off"]["enforced_in"]
    assert answer["gates"]["strategy_trigger"]["status"] == "not_configured"
    assert "B5" in answer["gates"]["strategy_trigger"]["detail"]
    thresholds(api, engagement_id)
    empty = evaluation(api, engagement_id)
    assert empty["aggregate"]["profit_before_tax"]["gross"] == "0.00"
    assert empty["gates"]["hard"]["status"] == "clear"
    assert empty["gates"]["soft"]["acknowledgement"]["status"] == "not_required"
    assert empty["sign_off"]["blocked"] is False


# ---- acceptance 4: gross and net, profit and net assets, with and without projected -----


def test_the_aggregate_is_shown_gross_and_net_for_profit_and_net_assets(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "10000.00")  # Dr rent / Cr provisions: both -10,000
    raise_item(  # Dr provisions / Cr sales: profit +4,000, net assets +4,000
        api,
        engagement_id,
        "4000.00",
        lines=[{"line_no": 3, "dr": "4000.00"}, {"line_no": 4, "cr": "4000.00"}],
    )
    raise_item(  # Dr receivables / Cr general reserve: profit 0, net assets +8,000
        api,
        engagement_id,
        "8000.00",
        lines=[{"line_no": 1, "dr": "8000.00"}, {"line_no": 9, "cr": "8000.00"}],
    )
    total = evaluation(api, engagement_id)["aggregate"]
    assert total["profit_before_tax"] == {
        "gross": "14000.00",
        "net": "-6000.00",
        "gross_without_projected": "14000.00",
        "net_without_projected": "-6000.00",
        "projected_gross": "0.00",
        "factual_gross": "14000.00",
        "judgemental_gross": "0.00",
    }
    assert total["net_assets"] == {
        "gross": "22000.00",
        "net": "2000.00",
        "gross_without_projected": "22000.00",
        "net_without_projected": "2000.00",
        "projected_gross": "0.00",
        "factual_gross": "22000.00",
        "judgemental_gross": "0.00",
    }
    assert total["counted"] == ["M-1", "M-2", "M-3"]
    assert total["complete"] is True
    assert "F3" in total["basis"] and "B8" in total["basis"]


# ---- the boundaries through the API, factual, projected and mixed -------------------------


@pytest.mark.parametrize(
    ("amount", "hard", "soft"),
    [
        ("249999.99", "clear", "clear"),
        ("250000.00", "clear", "fires"),
        ("399999.99", "clear", "fires"),
        ("400000.00", "fires", "fires"),
    ],
)
def test_a_factual_item_at_each_boundary(
    api: TestClient, amount: str, hard: str, soft: str
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, amount)
    gates = evaluation(api, engagement_id)["gates"]
    assert (gates["hard"]["status"], gates["soft"]["status"]) == (hard, soft)
    assert gates["hard"]["depends_on_projected"] is False
    assert gates["hard"]["line"] == "400000.00" and gates["soft"]["line"] == "250000.00"


@pytest.mark.parametrize(
    ("amount", "hard", "soft"),
    [("399999.99", "clear", "fires"), ("400000.00", "fires", "fires")],
)
def test_a_projected_only_item_is_treated_alike_and_the_dependence_is_disclosed(
    api: TestClient, amount: str, hard: str, soft: str
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, amount, type="projected")
    answer = evaluation(api, engagement_id)
    assert answer["aggregate"]["projected"] == ["M-1"]
    assert answer["aggregate"]["profit_before_tax"]["gross_without_projected"] == "0.00"
    gates = answer["gates"]
    assert gates["hard"]["status"] == hard
    assert gates["hard"]["fires_without_projected"] is False
    assert gates["hard"]["depends_on_projected"] is (hard == "fires")
    assert gates["soft"]["status"] == soft
    assert gates["soft"]["depends_on_projected"] is True
    item = answer["items"][0]
    assert item["type"] == "projected" and item["projected"] is True
    if hard == "fires":
        assert any("pending decision B8" in r for r in answer["sign_off"]["reasons"])


def test_a_mixed_aggregate_says_whether_the_factual_items_alone_reach_each_line(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "150000.00")
    raise_item(api, engagement_id, "50000.00", type="judgemental")
    raise_item(api, engagement_id, "200000.00", type="projected")
    answer = evaluation(api, engagement_id)
    measure = answer["aggregate"]["profit_before_tax"]
    assert (measure["factual_gross"], measure["judgemental_gross"], measure["projected_gross"]) == (
        "150000.00",
        "50000.00",
        "200000.00",
    )
    assert measure["gross_without_projected"] == "200000.00"  # factual and judgemental
    gates = answer["gates"]
    for name in ("hard", "soft"):
        assert gates[name]["status"] == "fires", name
        assert gates[name]["fires_without_projected"] is False, name
        assert gates[name]["depends_on_projected"] is True, name
    assert gates["hard"]["highest_measure"] == "400000.00"
    raise_item(api, engagement_id, "200000.00")  # the factual items now reach OM alone
    again = evaluation(api, engagement_id)["gates"]["hard"]
    assert again["fires_without_projected"] is True
    assert again["depends_on_projected"] is False


def test_items_that_cancel_on_net_still_reach_the_line_on_gross(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "300000.00")
    raise_item(
        api,
        engagement_id,
        "300000.00",
        lines=[{"line_no": 3, "dr": "300000.00"}, {"line_no": 4, "cr": "300000.00"}],
    )
    answer = evaluation(api, engagement_id)
    assert answer["aggregate"]["profit_before_tax"]["net"] == "0.00"
    assert answer["gates"]["hard"]["fires_on"] == ["profit.gross", "net_assets.gross"]
    assert answer["individually_significant"]["blocking"] == ["M-1", "M-2"]
    assert answer["sign_off"]["blocked"] is True
    assert "M-1 is individually significant and raised" in answer["sign_off"]["reasons"]


# ---- D37: classification-only items ------------------------------------------------------


def test_a_classification_only_item_is_listed_at_nil_and_never_moves_a_gate(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    big = raise_item(
        api,
        engagement_id,
        "900000.00",
        lines=[{"line_no": 1, "dr": "900000.00"}, {"line_no": 2, "cr": "900000.00"}],
    )
    assert big["current"]["spine_kind"] == "reclass"
    assert spine.adjustments[uuid.UUID(big["spine"]["adjustment_id"])].kind == "reclass"
    answer = evaluation(api, engagement_id)
    assert answer["aggregate"]["classification_only"] == ["M-1"]
    assert answer["aggregate"]["counted"] == ["M-1"]
    assert answer["aggregate"]["profit_before_tax"]["gross"] == "0.00"
    assert answer["aggregate"]["net_assets"]["gross"] == "0.00"
    assert answer["gates"]["hard"]["status"] == "clear"
    item = answer["items"][0]
    assert item["classification_only"] is True
    assert item["measure"] == "900000.00"  # the gross size is still shown
    assert item["band"] == "clearly_trivial"
    assert answer["sign_off"]["blocked"] is False


# ---- unresolved items: indeterminate, never a guess ----------------------------------------


def test_an_unresolved_item_makes_the_gates_indeterminate_and_blocks(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "1000.00")
    spine.rekey_ledger("Rent", "rent (indirect)")
    answer = evaluation(api, engagement_id)
    assert answer["aggregate"]["unresolved"] == ["M-1"]
    assert answer["aggregate"]["complete"] is False
    assert answer["gates"]["hard"]["status"] == "indeterminate"
    assert answer["gates"]["soft"]["status"] == "indeterminate"
    assert answer["individually_significant"]["unbanded"] == ["M-1"]
    assert answer["sign_off"]["blocked"] is True
    assert "M-1 is raised and cannot be banded" in answer["sign_off"]["reasons"]
    spine.unreachable = True
    down = evaluation(api, engagement_id)
    assert down["items"][0]["spine_status"] == "unreachable"
    assert down["gates"]["hard"]["status"] == "indeterminate"


# ---- the write-path check -------------------------------------------------------------------


def test_the_write_path_check_fails_closed_with_the_reasons(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "400000.00")
    app = cast(FastAPI, api.app)
    with app.state.session_factory() as session:
        engagement = session.get(Engagement, uuid.UUID(engagement_id))
        assert engagement is not None
        result = evaluate(session, app.state.spine_client, engagement, app.state.settings)
        with pytest.raises(GateBlocked, match="hard gate") as blocked:
            require_sign_off_open(result)
        assert blocked.value.status_code == 409
        assert "M-1 is individually significant" in str(blocked.value)


# ---- D39, D40: the acknowledgement is partner-only and fails closed -------------------------

TRUSTED_PROXY = "10.0.0.5"


def soft_gate_firing(api: TestClient) -> str:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "250000.00")
    return engagement_id


def header_mode(api: TestClient, *, roles: bool, trusted: bool = True) -> TestClient:
    """Switch the running app to header mode and return a client whose socket peer is the
    listed proxy address. The fixture's own client keeps the peer 'testclient'."""
    settings = cast(FastAPI, api.app).state.settings
    settings.auth = "header"
    settings.dev_user = None
    settings.trusted_proxies = "10.0.0.0/24" if trusted else ""
    settings.auth_roles_header = ROLES if roles else None
    settings.partner_role = "engagement-partner" if roles else None
    return TestClient(api.app, client=(TRUSTED_PROXY, 40000))


def acknowledge(client: TestClient, engagement_id: str, **kwargs: Any) -> Any:
    return client.post(
        f"/api/engagements/{engagement_id}/evaluation/soft-gate-acknowledgements",
        json=kwargs.pop("json", {"note": "reviewed with the manager"}),
        **kwargs,
    )


def events(client: TestClient, engagement_id: str) -> Any:
    return client.get(f"/api/engagements/{engagement_id}/events").json()


def test_in_dev_mode_the_acknowledgement_is_unavailable_and_nothing_is_written(
    api: TestClient,
) -> None:
    engagement_id = soft_gate_firing(api)
    before = evaluation(api, engagement_id)
    assert before["gates"]["soft"]["acknowledgement"]["status"] == "required"
    assert before["authorisation"]["partner_actions"] == {
        "enforced": True,
        "available": False,
        "actions": ["soft_gate_acknowledgement", "conclusion"],
        "source": None,
        "detail": before["authorisation"]["partner_actions"]["detail"],
    }
    refused = acknowledge(api, engagement_id, headers=PARTNER)  # the claim is sent, unread
    assert refused.status_code == 403
    assert "unavailable" in refused.json()["detail"] and "B9" in refused.json()["detail"]
    assert events(api, engagement_id) == []
    assert evaluation(api, engagement_id)["sign_off"]["blocked"] is True
    act_as(api, None)
    assert acknowledge(api, engagement_id).status_code == 503  # no identity at all


def test_a_configured_claim_without_a_listed_proxy_is_still_unavailable(api: TestClient) -> None:
    """D40: a role header is never believed merely because it is configured."""
    engagement_id = soft_gate_firing(api)
    proxy = header_mode(api, roles=True, trusted=False)
    assert evaluation(api, engagement_id)["authorisation"]["partner_actions"]["available"] is False
    refused = proxy.post(
        f"/api/engagements/{engagement_id}/evaluation/soft-gate-acknowledgements",
        json={"note": "x"},
        headers=PARTNER,
    )
    assert refused.status_code == 403
    assert "OAK_TRUSTED_PROXIES" in refused.json()["detail"]
    assert events(api, engagement_id) == []


def test_in_header_mode_without_a_role_claim_configured_it_is_still_unavailable(
    api: TestClient,
) -> None:
    engagement_id = soft_gate_firing(api)
    proxy = header_mode(api, roles=False)
    refused = acknowledge(proxy, engagement_id, headers=PARTNER)  # the header is sent, unread
    assert refused.status_code == 403
    assert "unavailable" in refused.json()["detail"]
    assert events(proxy, engagement_id) == []


def test_a_partner_named_by_the_trusted_proxys_role_claim_may_acknowledge(
    api: TestClient,
) -> None:
    engagement_id = soft_gate_firing(api)
    proxy = header_mode(api, roles=True)
    assert evaluation(api, engagement_id)["authorisation"]["partner_actions"]["available"] is True
    answer = acknowledge(proxy, engagement_id, headers=PARTNER)
    assert answer.status_code == 201, answer.text
    event = answer.json()["acknowledgement_event"]
    assert event["kind"] == "soft_gate_acknowledged"
    assert event["actor"] == "partner@firm"
    assert event["payload"]["note"] == "reviewed with the manager"
    assert event["payload"]["fires_on"] == [
        "profit.gross",
        "profit.net",
        "net_assets.gross",
        "net_assets.net",
    ]
    assert event["payload"]["figures"]["profit_before_tax"]["gross"] == "250000.00"
    assert event["payload"]["identity_mode"] == "header"
    after = answer.json()
    assert after["gates"]["soft"]["acknowledgement"]["status"] == "acknowledged"
    assert after["sign_off"]["blocked"] is False
    assert evaluation(api, engagement_id)["sign_off"]["blocked"] is False
    # Twice is refused: the figures are already acknowledged.
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 409
    assert [e["kind"] for e in events(proxy, engagement_id)] == ["soft_gate_acknowledged"]


def test_a_direct_client_cannot_impersonate_a_partner_by_sending_the_headers(
    api: TestClient,
) -> None:
    """D40: the claim is believed from the listed proxy address and from nowhere else."""
    engagement_id = soft_gate_firing(api)
    header_mode(api, roles=True)
    direct = TestClient(api.app, client=("203.0.113.9", 40000))  # not the proxy
    forged = direct.post(
        f"/api/engagements/{engagement_id}/evaluation/soft-gate-acknowledgements",
        json={"note": "x"},
        headers=PARTNER,
    )
    assert forged.status_code == 401  # the identity itself is not believed
    assert "trusted proxy" in forged.json()["detail"]
    unparseable = TestClient(api.app, client=("not-an-address", 1))
    assert (
        unparseable.post(
            f"/api/engagements/{engagement_id}/evaluation/soft-gate-acknowledgements",
            json={"note": "x"},
            headers=PARTNER,
        ).status_code
        == 401
    )
    assert events(api, engagement_id) == []
    assert evaluation(api, engagement_id)["sign_off"]["blocked"] is True


def test_a_non_partner_a_missing_claim_and_a_duplicated_claim_are_refused(
    api: TestClient,
) -> None:
    engagement_id = soft_gate_firing(api)
    proxy = header_mode(api, roles=True)
    not_partner = acknowledge(proxy, engagement_id, headers=SENIOR)
    assert not_partner.status_code == 403
    assert "does not hold the partner role" in not_partner.json()["detail"]
    missing = acknowledge(proxy, engagement_id, headers={"X-Authenticated-User": "partner@firm"})
    assert missing.status_code == 403
    assert "no role claim" in missing.json()["detail"]
    blank = acknowledge(
        proxy, engagement_id, headers={"X-Authenticated-User": "partner@firm", ROLES: "  "}
    )
    assert blank.status_code == 403
    # A client's own header that the proxy appended to instead of replacing: two values.
    twice = acknowledge(
        proxy,
        engagement_id,
        headers=[
            ("X-Authenticated-User", "partner@firm"),
            (ROLES, "staff"),
            (ROLES, "engagement-partner"),
        ],
    )
    assert twice.status_code == 403
    assert "presented 2 times" in twice.json()["detail"]
    # The partner role must be the whole value, never a substring or a different case.
    for lookalike in ("engagement-partner-assistant", "Engagement-Partner", "engagement partner"):
        answer = acknowledge(
            proxy, engagement_id, headers={"X-Authenticated-User": "x@firm", ROLES: lookalike}
        )
        assert answer.status_code == 403, lookalike
    assert events(proxy, engagement_id) == []
    assert evaluation(api, engagement_id)["sign_off"]["blocked"] is True


def test_a_role_in_the_request_body_is_always_refused(api: TestClient) -> None:
    engagement_id = soft_gate_firing(api)
    proxy = header_mode(api, roles=True)
    for body in (
        {"note": "x", "roles": ["engagement-partner"]},
        {"note": "x", "role": "engagement-partner"},
        {"note": "x", "partner": True},
        {"note": "x", "acknowledged_by": "partner@firm"},
    ):
        forged = acknowledge(proxy, engagement_id, json=body, headers=PARTNER)
        assert forged.status_code == 422, body
        assert "Extra inputs are not permitted" in forged.text
    assert events(proxy, engagement_id) == []


def test_an_acknowledgement_goes_stale_when_the_figures_or_the_threshold_change(
    api: TestClient,
) -> None:
    engagement_id = soft_gate_firing(api)
    proxy = header_mode(api, roles=True)
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    raise_item(proxy, engagement_id, "1000.00", headers=SENIOR)
    stale = evaluation(proxy, engagement_id)
    assert stale["gates"]["soft"]["acknowledgement"]["status"] == "stale"
    assert "aggregate has changed" in stale["gates"]["soft"]["acknowledgement"]["detail"]
    assert stale["sign_off"]["blocked"] is True
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    assert evaluation(proxy, engagement_id)["sign_off"]["blocked"] is False
    revised = proxy.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "400000.00", "pm": "240000.00", "ctt_fraction": "0.05", "basis": "C-2"},
        headers=SENIOR,
    )
    assert revised.status_code == 201, revised.text
    again = evaluation(proxy, engagement_id)["gates"]["soft"]["acknowledgement"]
    assert again["status"] == "stale"
    assert "another threshold version" in again["detail"]
    assert evaluation(proxy, engagement_id)["sign_off"]["blocked"] is True
    # Every acknowledgement stays in the trail; nothing is rewritten.
    assert [e["kind"] for e in events(proxy, engagement_id)] == [
        "soft_gate_acknowledged",
        "soft_gate_acknowledged",
        "threshold_recompute",
    ]


def test_nothing_to_acknowledge_when_the_soft_gate_is_clear(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "1000.00")
    proxy = header_mode(api, roles=True)
    refused = acknowledge(proxy, engagement_id, headers=PARTNER)
    assert refused.status_code == 409
    assert "nothing to acknowledge" in refused.json()["detail"]


def test_the_firm_may_make_the_pm_gate_hard_and_an_acknowledgement_does_not_open_it(
    api: TestClient,
) -> None:
    engagement_id = soft_gate_firing(api)
    proxy = header_mode(api, roles=True)
    cast(FastAPI, api.app).state.settings.pm_gate = "hard"
    assert acknowledge(proxy, engagement_id, headers=PARTNER).status_code == 201
    answer = evaluation(proxy, engagement_id)
    assert answer["gates"]["soft"]["pm_gate"] == "hard"
    assert answer["gates"]["soft"]["acknowledgement"]["status"] == "acknowledged"
    assert answer["sign_off"]["blocked"] is True
    assert "OAK_PM_GATE" in answer["sign_off"]["reasons"][0]
