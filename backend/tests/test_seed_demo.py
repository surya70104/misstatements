"""The demo seed (``scripts/seed_demo.py``) against the real application.

The script is standalone and speaks HTTP; here its ``seed`` runs through the test client, so
every request it makes is validated by the same code a reviewer's backend runs. A change to
the API that the script does not follow fails here.
"""

from __future__ import annotations

import importlib.util
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import BACKEND_DIR, use_spine
from tests.test_api_evaluation import evaluation, linked, raise_item, thresholds

SCRIPT = BACKEND_DIR.parent / "scripts" / "seed_demo.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_demo", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def through(api: TestClient) -> Any:
    def call(method: str, path: str, body: dict[str, Any] | None) -> tuple[int, Any]:
        answer = api.request(method, path, json=body)
        return answer.status_code, answer.json()

    return call


def quiet(_line: str) -> None:
    return None


def test_the_demo_seeds_every_part_of_the_scenario(api: TestClient) -> None:
    use_spine(api)
    seeded = load().seed(through(api), say=quiet)
    engagement_id = seeded["engagement_id"]
    assert (seeded["misstatements"], seeded["run_no"]) == (5, 1)

    schedule = api.get(f"/api/engagements/{engagement_id}/misstatements").json()
    current = [item["current"] for item in schedule]
    assert [item["type"] for item in current] == [
        "factual",
        "judgemental",
        "projected",
        "factual",
        "factual",
    ]
    assert [item["raised_from"] for item in current] == ["wp", "wp", "wp", "run", "note"]
    assert [item["state"] for item in current] == [
        "communicated",
        "refused",
        "raised",
        "raised",
        "corrected",
    ]
    assert (current[1]["range_low"], current[1]["range_high"]) == ("30000.00", "40000.00")
    assert (current[2]["sample_ref"], current[2]["sampling"]["method"]) == ("S-12", "ratio")
    assert current[3]["origin"]["run_id"] == "RUN-DEMO-0412"

    checklist = api.get(f"/api/misstatements/{schedule[3]['id']}/qualitative").json()
    assert checklist["escalated"] is True

    carried = api.get(f"/api/engagements/{engagement_id}/prior-period").json()
    assert [item["ref"] for item in carried["items"]] == ["PY-1"]

    now = evaluation(api, engagement_id)
    assert now["threshold"]["om"] == "400000.00"
    assert now["latest_run"]["status"] == "current"


def test_the_demo_keeps_the_thresholds_an_engagement_already_has(api: TestClient) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id, om="900000.00", pm="600000.00")
    load().seed(through(api), engagement_id=engagement_id, say=quiet)
    history = api.get(f"/api/engagements/{engagement_id}/thresholds/history").json()
    assert [version["om"] for version in history] == ["900000.00"]


def test_the_demo_writes_nothing_into_an_engagement_that_has_misstatements(
    api: TestClient,
) -> None:
    use_spine(api)
    engagement_id = linked(api)
    thresholds(api, engagement_id)
    raise_item(api, engagement_id, "60000.00")
    module = load()
    with pytest.raises(module.SeedError, match="already has 1 misstatement"):
        module.seed(through(api), engagement_id=engagement_id, say=quiet)
    listed = api.get(f"/api/engagements/{engagement_id}/misstatements").json()
    assert len(listed) == 1
    assert api.get(f"/api/engagements/{engagement_id}/prior-period").json()["items"] == []


def test_the_demo_refuses_any_address_but_the_preview_unless_told() -> None:
    module = load()
    assert module.checked_url("http://127.0.0.1:8014/", False) == "http://127.0.0.1:8014"
    with pytest.raises(module.SeedError, match="append-only"):
        module.checked_url("http://127.0.0.1:8003", False)
    assert module.checked_url("http://127.0.0.1:8003", True) == "http://127.0.0.1:8003"
    for elsewhere in ("http://example.com:8014", "ftp://127.0.0.1:8014", "file:///etc/passwd"):
        with pytest.raises(module.SeedError, match="loopback"):
            module.checked_url(elsewhere, True)
