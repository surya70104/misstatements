"""The misstatement record over the API (spec sections 1, 3, 8, 9; acceptance 1; D22, D23).
Runs on the in-memory stand-in when no test database is configured (D24)."""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from tests.conftest import act_as, use_spine
from tests.fake_spine import ENGAGEMENT_ID, LOCKED_VERSION_ID, OPEN_VERSION_ID, FakeSpine

RENT_ACCRUAL = [{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "10000.00"}]
BS_ONLY = [{"line_no": 1, "dr": "700.00"}, {"line_no": 2, "cr": "700.00"}]


def linked_engagement(api: TestClient, version: uuid.UUID = OPEN_VERSION_ID) -> str:
    created = api.post(
        "/api/engagements",
        json={
            "label": "FY26",
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(version),
        },
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def body(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "type": "factual",
        "description": "Rent for March not accrued",
        "raised_from": "wp",
        "source_ref": "E-4.2",
        "lines": RENT_ACCRUAL,
    }
    values.update(overrides)
    return values


def raise_one(api: TestClient, engagement_id: str, **overrides: Any) -> Any:
    return api.post(f"/api/engagements/{engagement_id}/misstatements", json=body(**overrides))


def test_raising_a_misstatement_proposes_it_to_the_spine_and_keeps_only_the_link(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    answer = raise_one(api, engagement_id)
    assert answer.status_code == 201, answer.text
    record = answer.json()
    assert record["ref"] == "M-1"
    assert record["created_by"] == "senior@firm"
    current = record["current"]
    assert current["version_no"] == 1
    assert current["state"] == "raised"
    assert current["type"] == "factual"
    assert current["raised_from"] == "wp"
    assert current["source_ref"] == "E-4.2"
    assert current["spine_kind"] == "correction"
    assert current["refusal_reason"] is None and current["withdrawal_reason"] is None
    # The amounts live in the Spine: the record carries the adjustment id, and the Spine's
    # adjustment carries our reference and working paper (D15).
    adjustment = spine.adjustments[uuid.UUID(current["spine_adjustment_id"])]
    assert adjustment.status == "proposed"
    assert adjustment.kind == "correction"
    assert adjustment.finding_ref == "M-1"
    assert adjustment.working_paper_ref == "E-4.2"
    assert adjustment.narration == "Rent for March not accrued"
    assert record["spine"]["status"] == "ok"
    assert record["spine"]["adjustment_status"] == "proposed"
    assert record["spine"]["measure"] == "10000.00"
    assert [line["ledger_name"] for line in record["spine"]["lines"]] == [
        "Rent",
        "Provision for expenses",
    ]
    assert record["spine"]["lines"][0]["nature"] == "PL"
    assert ("POST", f"/api/spine-versions/{OPEN_VERSION_ID}/adjustments") in spine.calls


def test_the_effects_are_computed_from_the_spines_lines(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    effects = raise_one(api, engagement_id).json()["effects"]
    assert effects["profit_before_tax"] == "-10000.00"
    assert effects["profit_partial"] is False
    assert effects["captions"] == [
        {"head_id": "pl.expenses.other", "nature": "PL", "signed": "10000.00"},
        {"head_id": "bs.liabilities.current.provisions", "nature": "BS", "signed": "-10000.00"},
    ]
    assert effects["classification_only"] is False
    assert effects["partial"] is False
    assert effects["net_assets"] == "-10000.00"
    assert "assets less liabilities" in effects["net_assets_basis"]
    assert "item IX" in effects["profit_basis"]
    assert effects["tree_version_at_raise"] == "double-division1-2026-11-04"
    assert effects["spine_version_at_raise"] == str(OPEN_VERSION_ID)


def test_references_are_sequential_per_engagement_and_never_reused(api: TestClient) -> None:
    use_spine(api)
    first = linked_engagement(api)
    second = linked_engagement(api)
    assert raise_one(api, first).json()["ref"] == "M-1"
    assert raise_one(api, first).json()["ref"] == "M-2"
    assert raise_one(api, second).json()["ref"] == "M-1"
    listed = api.get(f"/api/engagements/{first}/misstatements").json()
    assert [entry["ref"] for entry in listed] == ["M-1", "M-2"]
    assert api.get(f"/api/engagements/{first}").json()["misstatements"] == 2


def test_acceptance_1_a_single_amount_cannot_be_created_and_nothing_reaches_the_spine(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    calls_before = len(spine.calls)
    assert (
        raise_one(api, engagement_id, lines=[{"line_no": 5, "dr": "10000.00"}]).status_code == 422
    )
    unbalanced = raise_one(
        api, engagement_id, lines=[{"line_no": 5, "dr": "10000.00"}, {"line_no": 3, "cr": "1.00"}]
    )
    assert unbalanced.status_code == 422
    assert "must balance" in unbalanced.text
    assert (
        raise_one(
            api,
            engagement_id,
            lines=[{"line_no": 5, "dr": "1", "cr": "1"}, {"line_no": 3, "cr": "1"}],
        ).status_code
        == 422
    )
    assert spine.calls[calls_before:] == []
    assert spine.adjustments == {}
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []


def test_a_classification_only_item_is_proposed_as_a_reclassification_and_says_so(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    api.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
    )
    created = raise_one(api, engagement_id, lines=BS_ONLY)
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["current"]["spine_kind"] == "reclass"
    adjustment = spine.adjustments[uuid.UUID(record["spine"]["adjustment_id"])]
    assert adjustment.kind == "reclass"  # never dressed up as a correction (D37)
    assert record["spine"]["kind"] == "reclass"
    assert record["effects"]["profit_before_tax"] == "0.00"
    assert record["effects"]["net_assets"] == "0.00"
    assert record["effects"]["classification_only"] is True
    assert record["spine"]["measure"] == "700.00"  # the gross size, shown beside nil effects
    assert record["band"] == "clearly_trivial"
    assert record["banding"]["classification_only"] is True
    assert "reclassification" in record["band_basis"] and "qualitative" in record["band_basis"]
    # A proposed reclassification moves nothing in the Spine until it is accepted.
    assert spine.adjusted_balance(OPEN_VERSION_ID, "Alpha Traders") == Decimal("500000.00")
    pl_only = raise_one(
        api, engagement_id, lines=[{"line_no": 5, "dr": "500.00"}, {"line_no": 6, "cr": "500.00"}]
    )
    assert pl_only.status_code == 201
    assert pl_only.json()["current"]["spine_kind"] == "reclass"
    assert pl_only.json()["ref"] == "M-2"


def test_an_unmapped_ledger_is_refused_before_the_spine_is_asked(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    refused = raise_one(
        api, engagement_id, lines=[{"line_no": 7, "dr": "50.00"}, {"line_no": 4, "cr": "50.00"}]
    )
    assert refused.status_code == 422
    assert "cannot be classified: Suspense" in refused.json()["detail"]
    assert spine.adjustments == {}
    unknown = raise_one(
        api, engagement_id, lines=[{"line_no": 99, "dr": "50.00"}, {"line_no": 4, "cr": "50.00"}]
    )
    assert unknown.status_code == 422
    assert "line_no 99" in unknown.json()["detail"]


def test_a_ledger_the_import_lacks_can_be_introduced(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    lines = [
        {
            "ledger_name": "Audit fee provision",
            "parent_chain": ["Provisions"],
            "head_id": "bs.liabilities.current.provisions",
            "cr": "25000.00",
        },
        {"line_no": 5, "dr": "25000.00"},
    ]
    answer = raise_one(api, engagement_id, lines=lines)
    assert answer.status_code == 201, answer.text
    assert answer.json()["spine"]["lines"][0]["head_id"] == "bs.liabilities.current.provisions"
    assert answer.json()["effects"]["profit_before_tax"] == "-25000.00"
    not_leaf = raise_one(
        api,
        engagement_id,
        lines=[{"ledger_name": "X", "head_id": "bs", "cr": "1"}, {"line_no": 5, "dr": "1"}],
    )
    assert not_leaf.status_code == 422
    assert "not a mappable leaf" in not_leaf.json()["detail"]


def test_the_pinned_version_must_exist_be_unlocked_and_be_reachable(api: TestClient) -> None:
    unconfigured = api.post("/api/engagements", json={"label": "no spine"}).json()["id"]
    assert raise_one(api, unconfigured).status_code == 409
    assert "OAK_SPINE_URL" in raise_one(api, unconfigured).json()["detail"]
    spine = use_spine(api)
    unpinned = api.post(
        "/api/engagements", json={"label": "FY26", "spine_engagement_id": str(ENGAGEMENT_ID)}
    ).json()["id"]
    refused = raise_one(api, unpinned)
    assert refused.status_code == 409
    assert "no Financial Spine version is pinned" in refused.json()["detail"]
    locked = linked_engagement(api, LOCKED_VERSION_ID)
    frozen = raise_one(api, locked)
    assert frozen.status_code == 409
    assert "is locked" in frozen.json()["detail"]
    engagement_id = linked_engagement(api)
    spine.unreachable = True
    assert raise_one(api, engagement_id).status_code == 503
    assert spine.adjustments == {}


def test_judgemental_and_projected_items_carry_their_own_fields(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    assert raise_one(api, engagement_id, type="judgemental").status_code == 422
    judgemental = raise_one(
        api, engagement_id, type="judgemental", range_low="5000", range_high="15000.5"
    )
    assert judgemental.status_code == 201, judgemental.text
    assert judgemental.json()["current"]["range_low"] == "5000.00"
    assert judgemental.json()["current"]["range_high"] == "15000.50"
    assert raise_one(api, engagement_id, type="projected").status_code == 422
    projected = raise_one(
        api,
        engagement_id,
        type="projected",
        sample_ref="S-3",
        projection_basis="ratio projection over the population",
    )
    assert projected.status_code == 201
    assert projected.json()["current"]["sample_ref"] == "S-3"
    assert projected.json()["current"]["range_low"] is None


def test_reading_one_misstatement_shows_its_versions_and_the_spines_side(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    read = api.get(f"/api/misstatements/{created['id']}")
    assert read.status_code == 200
    assert [v["version_no"] for v in read.json()["versions"]] == [1]
    assert read.json()["effects"]["profit_before_tax"] == "-10000.00"
    assert api.get(f"/api/misstatements/{uuid.uuid4()}").status_code == 404
    spine.unreachable = True
    unreachable = api.get(f"/api/misstatements/{created['id']}").json()
    assert unreachable["spine"]["status"] == "unreachable"
    assert unreachable["effects"] is None
    assert (
        unreachable["current"]["spine_adjustment_id"] == created["current"]["spine_adjustment_id"]
    )


def test_the_list_says_when_the_spine_is_not_configured_or_has_lost_the_adjustment(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    spine.adjustments.clear()
    lost = api.get(f"/api/engagements/{engagement_id}/misstatements").json()[0]
    assert lost["spine"]["status"] == "missing"
    assert lost["effects"] is None
    use_spine(api, FakeSpine())  # a fresh double without the adjustment behaves the same
    assert api.get(f"/api/misstatements/{created['id']}").json()["spine"]["status"] == "missing"
    api.app.state.spine_client = None  # type: ignore[attr-defined]
    none = api.get(f"/api/engagements/{engagement_id}/misstatements").json()[0]
    assert none["spine"]["status"] == "not_configured"


def test_re_pointing_the_version_is_refused_once_a_misstatement_exists(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    raise_one(api, engagement_id)
    refused = api.post(
        f"/api/engagements/{engagement_id}/spine-link",
        json={
            "spine_engagement_id": str(ENGAGEMENT_ID),
            "spine_version_id": str(LOCKED_VERSION_ID),
        },
    )
    assert refused.status_code == 409
    assert refused.json()["pending_decision"] == "B10"
    same = api.post(
        f"/api/engagements/{engagement_id}/spine-link",
        json={"spine_engagement_id": str(ENGAGEMENT_ID), "spine_version_id": str(OPEN_VERSION_ID)},
    )
    assert same.status_code == 200


def test_raising_needs_an_identity(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    act_as(api, None)
    assert raise_one(api, engagement_id).status_code == 503


# ---- D-1: a database failure after the Spine accepted names the orphan and the cause ----


def test_a_database_failure_after_the_proposal_names_the_orphan_and_the_real_error(
    api: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)

    real_flush = Session.flush

    def lose_the_connection(self: Session, *args: Any, **kwargs: Any) -> None:
        # Fail only once the Spine holds the proposal: that is the orphan case of D22.
        if spine.adjustments:
            raise OperationalError("INSERT INTO misstatement", {}, Exception("connection lost"))
        real_flush(self, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", lose_the_connection)
    with caplog.at_level(logging.ERROR, logger="oak_misstatements.services.misstatements"):
        answer = raise_one(api, engagement_id)
    monkeypatch.undo()
    assert answer.status_code == 409
    detail = answer.json()["detail"]
    # The Spine holds exactly one proposal: the orphan. Its id and the database's own error
    # are in the answer and in the log, and nothing here was written.
    (orphan_id,) = spine.adjustments
    assert str(orphan_id) in detail
    assert "M-1" in detail
    assert "connection lost" in detail
    assert "orphan" in detail and "D22" in detail
    assert any(
        str(orphan_id) in record.getMessage() and "connection lost" in record.getMessage()
        for record in caplog.records
    )
    assert api.get(f"/api/engagements/{engagement_id}/misstatements").json() == []
    assert api.get(f"/api/engagements/{engagement_id}").json()["misstatements"] == 0


# ---- D31: the effects matrix through the Spine double, by import line number ------------
# 3 provisions · 9 general reserve · 10 capital reserve · 11 share application money (I(2))
# 12 provision for tax · 13 deferred tax liability · 14 accumulated depreciation
# 15 depreciation · 16 current tax · 17 deferred tax expense · 20 share application refundable


def effects_of(api: TestClient, engagement_id: str, lines: list[dict[str, str | int]]) -> Any:
    answer = raise_one(api, engagement_id, lines=lines)
    assert answer.status_code == 201, answer.text
    return answer.json()


@pytest.mark.parametrize(
    ("label", "lines", "pbt", "net_assets"),
    [
        (
            "tax expense only",
            [{"line_no": 16, "dr": "3000.00"}, {"line_no": 12, "cr": "3000.00"}],
            "0.00",
            "-3000.00",
        ),
        (
            "direct equity",
            [{"line_no": 9, "dr": "8000.00"}, {"line_no": 3, "cr": "8000.00"}],
            "0.00",
            "-8000.00",
        ),
        (
            "deferred tax",
            [{"line_no": 17, "dr": "1200.00"}, {"line_no": 13, "cr": "1200.00"}],
            "0.00",
            "-1200.00",
        ),
        (
            "contra asset",
            [{"line_no": 15, "dr": "2000.00"}, {"line_no": 14, "cr": "2000.00"}],
            "-2000.00",
            "-2000.00",
        ),
        (
            "correction with its tax lines",
            [
                {"line_no": 5, "dr": "10000.00"},
                {"line_no": 3, "cr": "10000.00"},
                {"line_no": 12, "dr": "2500.00"},
                {"line_no": 16, "cr": "2500.00"},
            ],
            "-10000.00",
            "-7500.00",
        ),
        (
            "compound, mixed",
            [
                {"line_no": 5, "dr": "6000.00"},
                {"line_no": 1, "dr": "4000.00"},
                {"line_no": 3, "cr": "10000.00"},
            ],
            "-6000.00",
            "-6000.00",
        ),
    ],
)
def test_the_matrix_through_the_spine(
    api: TestClient, label: str, lines: list[dict[str, str | int]], pbt: str, net_assets: str
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    record = effects_of(api, engagement_id, lines)
    effects = record["effects"]
    assert effects["profit_before_tax"] == pbt, label
    assert effects["net_assets"] == net_assets, label
    assert effects["partial"] is False, label
    assert effects["classification_only"] is False, label
    assert record["current"]["spine_kind"] == "correction", label
    sections = {line["ledger_name"]: line["section"] for line in record["spine"]["lines"]}
    assert all(section != "unresolved" for section in sections.values()), sections


def test_regression_a_direct_equity_entry_is_a_correction_not_a_classification(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    record = effects_of(
        api, engagement_id, [{"line_no": 9, "dr": "8000.00"}, {"line_no": 3, "cr": "8000.00"}]
    )
    assert record["effects"]["profit_before_tax"] == "0.00"
    assert record["effects"]["net_assets"] == "-8000.00"
    assert record["effects"]["classification_only"] is False
    sections = {line["ledger_name"]: line["section"] for line in record["spine"]["lines"]}
    assert sections == {"General reserve": "equity", "Provision for expenses": "liabilities"}


def test_regression_a_tax_line_leaves_profit_before_tax_alone(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    record = effects_of(
        api, engagement_id, [{"line_no": 16, "dr": "3000.00"}, {"line_no": 12, "cr": "3000.00"}]
    )
    assert record["effects"]["profit_before_tax"] == "0.00"
    assert record["effects"]["net_assets"] == "-3000.00"
    sections = {line["ledger_name"]: line["section"] for line in record["spine"]["lines"]}
    assert sections == {"Current tax": "pl_after_tax", "Provision for tax": "liabilities"}


def test_classification_only_needs_both_effects_nil(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    within_equity = raise_one(
        api, engagement_id, lines=[{"line_no": 9, "dr": "700.00"}, {"line_no": 10, "cr": "700.00"}]
    )
    assert within_equity.status_code == 201
    assert within_equity.json()["current"]["spine_kind"] == "reclass"
    refundable = raise_one(
        api,
        engagement_id,
        lines=[{"line_no": 20, "dr": "5000.00"}, {"line_no": 2, "cr": "5000.00"}],
    )
    assert refundable.status_code == 201  # a classified liability against cash: both effects nil
    assert refundable.json()["current"]["spine_kind"] == "reclass"
    # A direct equity entry moves net assets: a correction, never a reclassification (D31).
    equity = raise_one(
        api, engagement_id, lines=[{"line_no": 9, "dr": "700.00"}, {"line_no": 3, "cr": "700.00"}]
    )
    assert equity.status_code == 201
    assert equity.json()["current"]["spine_kind"] == "correction"
    assert equity.json()["banding"]["classification_only"] is False


def test_share_application_money_pending_allotment_is_not_guessed(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    refused = raise_one(
        api,
        engagement_id,
        lines=[{"line_no": 11, "dr": "5000.00"}, {"line_no": 2, "cr": "5000.00"}],
    )
    assert refused.status_code == 422
    assert "cannot be classified: Share application money" in refused.json()["detail"]
    assert "share application money pending allotment" in refused.json()["detail"]
    assert spine.adjustments == {}


# ---- D32: the classification snapshot keeps old figures stable and reports drift ----------

RESERVE = "bs.liabilities.shareholders_funds.reserves.general"


def test_raising_records_a_classification_snapshot_with_labels_only(api: TestClient) -> None:
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import select

    from oak_misstatements.models import MisstatementLineClass

    use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    assert created["classification"] == {
        "spine_version_at_raise": str(OPEN_VERSION_ID),
        "tree_version_at_raise": "double-division1-2026-11-04",
        "tree_version_now": "double-division1-2026-11-04",
        "drift": [],
        "unmatched": [],
        "effects_on_current_classification": None,
    }
    factory = api.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as session:
        rows = list(
            session.scalars(select(MisstatementLineClass).order_by(MisstatementLineClass.position))
        )
    assert [
        (row.position, row.ledger_name, row.head_id, row.section, row.head_item) for row in rows
    ] == [
        (1, "Rent", "pl.expenses.other", "pl_before_tax", None),
        (
            2,
            "Provision for expenses",
            "bs.liabilities.current.provisions",
            "liabilities",
            "I(4)(d)",
        ),
    ]
    assert all(row.tree_version == "double-division1-2026-11-04" for row in rows)
    assert all(row.spine_version_id == OPEN_VERSION_ID for row in rows)
    columns = {column.key for column in sa_inspect(MisstatementLineClass).columns}
    assert not columns & {"dr", "cr", "amount", "signed", "measure"}


def test_regression_a_remapped_ledger_does_not_change_an_old_misstatement(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    assert created["effects"]["net_assets"] == "-10000.00"
    # The client later remaps the provision ledger to a reserve: on the Spine's current
    # classification the entry would move no net assets at all.
    spine.remap("Provision for expenses", RESERVE)
    read = api.get(f"/api/misstatements/{created['id']}").json()
    assert read["effects"]["profit_before_tax"] == "-10000.00"
    assert read["effects"]["net_assets"] == "-10000.00"
    assert read["effects"]["classification_only"] is False
    assert read["effects"]["partial"] is False
    sections = {line["ledger_name"]: line["section"] for line in read["spine"]["lines"]}
    assert sections["Provision for expenses"] == "liabilities"  # the snapshot, not the live map
    listed = api.get(f"/api/engagements/{engagement_id}/misstatements").json()[0]
    assert listed["effects"]["net_assets"] == "-10000.00"


def test_regression_classification_drift_is_reported_not_applied(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    spine.remap("Provision for expenses", RESERVE)
    classification = api.get(f"/api/misstatements/{created['id']}").json()["classification"]
    assert classification["drift"] == [
        {
            "position": 2,
            "ledger_name": "Provision for expenses",
            "ledger_key": "provision for expenses",
            "parent_chain": ["Provisions"],
            "snapshot": {"head_id": "bs.liabilities.current.provisions", "section": "liabilities"},
            "live": {"head_id": RESERVE, "section": "equity"},
        }
    ]
    assert classification["unmatched"] == []
    current = classification["effects_on_current_classification"]
    assert current["profit_before_tax"] == "-10000.00"
    assert current["net_assets"] == "0.00"  # what the live map would say, shown beside, not used
    assert classification["tree_version_at_raise"] == classification["tree_version_now"]


def test_regression_a_changed_tree_does_not_silently_alter_old_calculations(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    # A new tree retires the rent head: on the live classification the line is unresolved.
    spine.retire_head("pl.expenses.other", tree_version="double-division1-2026-12-01")
    read = api.get(f"/api/misstatements/{created['id']}").json()
    assert read["effects"]["profit_before_tax"] == "-10000.00"
    assert read["effects"]["net_assets"] == "-10000.00"
    assert read["effects"]["partial"] is False
    assert read["effects"]["tree_version_at_raise"] == "double-division1-2026-11-04"
    classification = read["classification"]
    assert classification["tree_version_now"] == "double-division1-2026-12-01"
    assert classification["drift"][0]["ledger_name"] == "Rent"
    assert classification["drift"][0]["live"] == {
        "head_id": "pl.expenses.other",
        "section": "unresolved",
    }
    current = classification["effects_on_current_classification"]
    assert current["partial"] is True and current["profit_before_tax"] is None
    assert read["spine"]["tree_version_now"] == "double-division1-2026-12-01"
    # A head moved under a classifying item is drift too, even though its id survives: the
    # item reference decides the section before the id does.
    other = raise_one(
        api,
        engagement_id,
        lines=[{"line_no": 16, "dr": "3000.00"}, {"line_no": 12, "cr": "3000.00"}],
    ).json()
    spine.move_head(
        "pl.tax_expense",
        parent="bs.liabilities.current",
        item="I(4)",
        tree_version="double-division1-2027-01-01",
    )
    moved = api.get(f"/api/misstatements/{other['id']}").json()
    assert moved["effects"]["profit_before_tax"] == "0.00"  # the snapshot: tax is after PBT
    assert moved["effects"]["net_assets"] == "-3000.00"
    drift = moved["classification"]["drift"]
    assert [(entry["ledger_name"], entry["live"]["section"]) for entry in drift] == [
        ("Current tax", "liabilities")
    ]
    current = moved["classification"]["effects_on_current_classification"]
    assert (current["profit_before_tax"], current["net_assets"]) == ("0.00", "0.00")


def test_regression_a_new_version_gets_its_own_snapshot_and_the_old_one_is_kept(
    api: TestClient,
) -> None:
    from sqlalchemy import select

    from oak_misstatements.models import MisstatementVersion
    from oak_misstatements.services.misstatements import snapshot_for, snapshot_lines

    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    spine.remap("Provision for expenses", RESERVE)
    client = spine.client()
    factory = api.app.state.session_factory  # type: ignore[attr-defined]
    with factory.begin() as session:
        first = session.scalar(select(MisstatementVersion).order_by(MisstatementVersion.version_no))
        assert first is not None
        # Stage 3 will create new versions through its own transitions; the snapshot rule is
        # the same for every version: a version 2 records the classification it was read with.
        second = MisstatementVersion(
            misstatement_id=first.misstatement_id,
            version_no=2,
            type=first.type,
            description=first.description,
            raised_by=first.raised_by,
            raised_from=first.raised_from,
            source_ref=first.source_ref,
            state="raised",
            spine_adjustment_id=first.spine_adjustment_id,
            spine_kind=first.spine_kind,
            created_by=first.created_by,
        )
        session.add(second)
        session.flush()
        adjustment = client.adjustment(OPEN_VERSION_ID, first.spine_adjustment_id)
        from oak_misstatements.services.misstatements import resolve_spine_lines

        live = resolve_spine_lines(adjustment, client.ledgers(OPEN_VERSION_ID), client.tree())
        snapshot_lines(
            session, second.id, live, spine_version_id=OPEN_VERSION_ID, tree=client.tree()
        )
        first_rows = snapshot_for(session, first.id)
        second_rows = snapshot_for(session, second.id)
    assert [row.section for row in first_rows] == ["pl_before_tax", "liabilities"]
    assert [row.section for row in second_rows] == ["pl_before_tax", "equity"]
    assert {row.id for row in first_rows}.isdisjoint({row.id for row in second_rows})
    read = api.get(f"/api/misstatements/{created['id']}").json()
    assert read["current"]["version_no"] == 2
    assert read["effects"]["net_assets"] == "0.00"  # version 2 was classified with the new map
    assert read["classification"]["drift"] == []


def test_regression_an_unmatched_line_gives_unresolved_effects_not_a_guess(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    # The Spine now derives another key for the rent ledger: the live line no longer
    # matches its snapshot line.
    spine.rekey_ledger("Rent", "rent (indirect)")
    read = api.get(f"/api/misstatements/{created['id']}").json()
    effects = read["effects"]
    assert effects["partial"] is True
    assert effects["profit_before_tax"] is None
    assert effects["net_assets"] is None
    assert effects["classification_only"] is False
    assert sorted(effects["unresolved"]) == ["Rent", "Rent"]  # the live line and the snapshot line
    assert sorted(read["classification"]["unmatched"]) == ["Rent", "Rent"]
    assert {line["ledger_name"]: line["section"] for line in read["spine"]["lines"]} == {
        "Rent": "unresolved",
        "Provision for expenses": "liabilities",
    }


def test_regression_a_changed_parent_chain_with_the_same_key_is_unmatched_not_guessed(
    api: TestClient,
) -> None:
    from sqlalchemy import select

    from oak_misstatements.models import MisstatementLineClass

    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    created = raise_one(api, engagement_id).json()
    factory = api.app.state.session_factory  # type: ignore[attr-defined]

    def snapshot_rows() -> list[tuple[int, str, str, list[str], str | None, str]]:
        with factory() as session:
            rows = session.scalars(
                select(MisstatementLineClass).order_by(MisstatementLineClass.position)
            )
            return [
                (
                    r.position,
                    r.ledger_name,
                    r.ledger_key,
                    list(r.parent_chain),
                    r.head_id,
                    r.section,
                )
                for r in rows
            ]

    before = snapshot_rows()
    assert before == [
        (1, "Rent", "rent", ["Indirect Expenses"], "pl.expenses.other", "pl_before_tax"),
        (
            2,
            "Provision for expenses",
            "provision for expenses",
            ["Provisions"],
            "bs.liabilities.current.provisions",
            "liabilities",
        ),
    ]
    # The Spine now serves the rent line under another parent chain; its key is unchanged.
    spine.rechain_ledger("Rent", ["Direct Expenses"])
    read = api.get(f"/api/misstatements/{created['id']}").json()
    # 1. The original snapshot is untouched.
    assert snapshot_rows() == before
    # 2. The live line no longer matches its snapshot line; both are named.
    assert sorted(read["classification"]["unmatched"]) == ["Rent", "Rent"]
    # 3. Both effects are null, with the reason.
    effects = read["effects"]
    assert effects["profit_before_tax"] is None
    assert effects["net_assets"] is None
    assert effects["partial"] is True
    assert "not computed" in effects["net_assets_basis"]
    # 4. The unmatched line is reported explicitly, with the chain the Spine now gives: the
    #    live line carries the amount, and the orphaned snapshot line is listed beside it at
    #    nil so that nothing recorded disappears silently.
    rent_lines = [line for line in read["spine"]["lines"] if line["ledger_name"] == "Rent"]
    (live,) = [line for line in rent_lines if line["dr"] == "10000.00"]
    (orphan,) = [line for line in rent_lines if line["dr"] == "0.00"]
    assert (live["ledger_key"], live["parent_chain"]) == ("rent", ["Direct Expenses"])
    assert (orphan["ledger_key"], orphan["parent_chain"]) == ("rent", ["Indirect Expenses"])
    assert sorted(effects["unresolved"]) == ["Rent", "Rent"]
    # 5. Nothing is guessed: the live line gets no head, no nature and no section; the
    #    orphan keeps what was recorded but is unresolved too; no classification-only
    #    verdict; no drift entry pretending the line matched.
    assert (live["head_id"], live["nature"], live["section"]) == (None, None, "unresolved")
    assert orphan["section"] == "unresolved"
    assert effects["classification_only"] is False
    assert read["classification"]["drift"] == []
    other = {line["ledger_name"]: line for line in read["spine"]["lines"]}
    assert other["Provision for expenses"]["section"] == "liabilities"


# ---- D33: bands on the answer, both effects, the literal boundaries ----------------------


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


def test_a_direct_equity_entry_is_trivial_on_profit_and_banded_on_net_assets(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    thresholds(api, engagement_id)  # CTT 12,500 · PM 250,000
    record = effects_of(
        api, engagement_id, [{"line_no": 9, "dr": "300000.00"}, {"line_no": 3, "cr": "300000.00"}]
    )
    assert record["banding"]["bands"] == {
        "profit": "clearly_trivial",
        "net_assets": "individually_significant",
    }
    assert record["band"] == "individually_significant"
    assert record["banding"]["amounts"] == {"profit": "0.00", "net_assets": "300000.00"}


def test_exactly_pm_accumulates_and_a_paisa_more_is_individually_significant(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    thresholds(api, engagement_id)
    at_pm = effects_of(
        api, engagement_id, [{"line_no": 5, "dr": "250000.00"}, {"line_no": 3, "cr": "250000.00"}]
    )
    assert at_pm["band"] == "accumulated"
    above = effects_of(
        api, engagement_id, [{"line_no": 5, "dr": "250000.01"}, {"line_no": 3, "cr": "250000.01"}]
    )
    assert above["band"] == "individually_significant"
    at_ctt = effects_of(
        api, engagement_id, [{"line_no": 5, "dr": "12500.00"}, {"line_no": 3, "cr": "12500.00"}]
    )
    assert at_ctt["band"] == "accumulated"
    below_ctt = effects_of(
        api, engagement_id, [{"line_no": 5, "dr": "12499.99"}, {"line_no": 3, "cr": "12499.99"}]
    )
    assert below_ctt["band"] == "clearly_trivial"


def test_judgemental_items_band_on_the_point_estimate_and_say_if_the_range_crosses_pm(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    thresholds(api, engagement_id)
    record = raise_one(
        api, engagement_id, type="judgemental", range_low="5000", range_high="260000"
    ).json()
    # The point estimate, 10,000, is below CTT, but the range reaches it: where it is not
    # certain that an item is clearly trivial, it is not (SA 450 paragraph A2; D56).
    assert record["band"] == "accumulated"
    assert record["banding"]["bands"] == {
        "profit": "clearly_trivial",
        "net_assets": "clearly_trivial",
    }
    assert "A2" in record["banding"]["basis"]
    assert record["banding"]["range_crosses_pm"] is True  # the range's top is above PM
    assert record["banding"]["projected"] is False
    narrow = raise_one(
        api, engagement_id, type="judgemental", range_low="5000", range_high="15000"
    ).json()
    assert narrow["banding"]["range_crosses_pm"] is False
    assert narrow["band"] == "accumulated"  # 15,000 is at or above CTT too
    certain = raise_one(
        api, engagement_id, type="judgemental", range_low="5000", range_high="12499.99"
    ).json()
    assert certain["band"] == "clearly_trivial"  # the whole range is below CTT
    assert "A2" not in certain["banding"]["basis"]


def test_projected_items_keep_their_identification_in_the_band(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    thresholds(api, engagement_id)
    record = raise_one(
        api, engagement_id, type="projected", sample_ref="S-3", projection_basis="ratio"
    ).json()
    assert record["banding"]["projected"] is True
    assert record["band"] == "clearly_trivial"
    factual = raise_one(api, engagement_id).json()
    assert factual["banding"]["projected"] is False
    assert factual["banding"]["range_crosses_pm"] is None


def test_unresolved_effects_get_no_band_with_the_reason(api: TestClient) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    thresholds(api, engagement_id)
    created = raise_one(api, engagement_id).json()
    assert created["band"] == "clearly_trivial"
    spine.rekey_ledger("Rent", "rent (indirect)")
    read = api.get(f"/api/misstatements/{created['id']}").json()
    assert read["band"] is None
    assert read["banding"]["bands"] is None
    assert "unresolved" in read["band_basis"] and "Rent" in read["band_basis"]
    assert read["banding"]["threshold_id"] is not None  # the lines existed; the effects did not
    spine.unreachable = True
    down = api.get(f"/api/misstatements/{created['id']}").json()
    assert down["band"] is None
    assert "could not be read" in down["band_basis"]


# ---- D37 regressions: classification only is never guessed and never inflates ------------


def test_regression_an_unresolved_line_ends_the_classification_only_verdict(
    api: TestClient,
) -> None:
    spine = use_spine(api)
    engagement_id = linked_engagement(api)
    api.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
    )
    created = raise_one(api, engagement_id, lines=BS_ONLY).json()
    assert created["banding"]["classification_only"] is True
    assert [call for call in spine.calls if call[0] == "POST"] == [
        ("POST", f"/api/spine-versions/{OPEN_VERSION_ID}/adjustments")
    ]
    assert spine.adjustments[uuid.UUID(created["spine"]["adjustment_id"])].kind == "reclass"
    spine.rekey_ledger("Alpha Traders", "alpha traders (old)")
    read = api.get(f"/api/misstatements/{created['id']}").json()
    assert read["effects"]["classification_only"] is False
    assert read["effects"]["profit_before_tax"] is None
    assert read["banding"]["classification_only"] is False
    assert read["band"] is None
    assert read["current"]["spine_kind"] == "reclass"  # the recorded choice never changes
    evaluation = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert evaluation["aggregate"]["classification_only"] == []
    assert evaluation["aggregate"]["unresolved"] == ["M-1"]
    assert evaluation["gates"]["hard"]["status"] == "indeterminate"
    assert evaluation["sign_off"]["blocked"] is True


def test_regression_a_large_reclassification_stays_in_the_schedule_and_moves_no_aggregate(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked_engagement(api)
    api.post(
        f"/api/engagements/{engagement_id}/thresholds",
        json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "C-1"},
    )
    raise_one(
        api,
        engagement_id,
        lines=[{"line_no": 1, "dr": "5000000.00"}, {"line_no": 2, "cr": "5000000.00"}],
    )
    raise_one(  # a factual correction of 20,000, above the clearly-trivial threshold
        api,
        engagement_id,
        lines=[{"line_no": 5, "dr": "20000.00"}, {"line_no": 3, "cr": "20000.00"}],
    )
    schedule = api.get(f"/api/engagements/{engagement_id}/misstatements").json()
    assert [row["ref"] for row in schedule] == ["M-1", "M-2"]
    reclass = schedule[0]
    assert reclass["spine"]["kind"] == "reclass"
    assert reclass["spine"]["measure"] == "5000000.00"
    assert reclass["band"] == "clearly_trivial"
    assert "qualitative" in reclass["band_basis"]
    evaluation = api.get(f"/api/engagements/{engagement_id}/evaluation").json()
    assert evaluation["aggregate"]["counted"] == ["M-1", "M-2"]
    assert evaluation["aggregate"]["classification_only"] == ["M-1"]
    assert evaluation["aggregate"]["not_accumulated"] == []
    assert evaluation["aggregate"]["profit_before_tax"]["gross"] == "20000.00"
    assert evaluation["aggregate"]["net_assets"]["gross"] == "20000.00"
    assert evaluation["gates"]["hard"]["status"] == "clear"
    assert evaluation["items"][0]["measure"] == "5000000.00"
