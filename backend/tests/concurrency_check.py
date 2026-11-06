"""Requests truly at the same moment (register V3). Development tooling only: nothing in the
application imports it, and it leaves nothing behind.

    .venv\\Scripts\\python.exe -m tests.concurrency_check

The test suite runs every request inside one rolled-back transaction, so it can never show
two transactions meeting. Rows that two transactions can both see have to be committed, and
the module's tables allow no delete. So this check does not touch them: it creates a
**scratch schema** in ``oak_misstatements_test``, builds the tables there, runs the real
application against it with the Financial Spine double, and **drops the schema** whatever
happens. ``oak_misstatements`` is never connected to, and the ``public`` schema of the test
database is not written.

What it shows: with several requests released together, the engagement row lock serialises
them. Every evaluation run is recorded and numbered once, and every misstatement gets its
own reference; no request fails and no number is issued twice.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import distinct, func, select, text
from sqlalchemy.orm import sessionmaker

from oak_misstatements.db import Base, make_engine
from oak_misstatements.main import create_app
from oak_misstatements.models.evaluation import EvaluationRun
from tests.conftest import APP_URL, IsolatedSettings, test_url
from tests.fake_spine import ENGAGEMENT_ID, OPEN_VERSION_ID, FakeSpine

REQUESTS = 8


def together(app: Any, calls: list[tuple[str, dict[str, Any]]]) -> list[tuple[int, Any]]:
    """Send every call from its own thread and its own client, released at one moment."""
    barrier = threading.Barrier(len(calls))
    answers: list[tuple[int, Any]] = []
    lock = threading.Lock()

    def send(path: str, body: dict[str, Any]) -> None:
        client = TestClient(app, raise_server_exceptions=False)
        barrier.wait()
        answer = client.post(path, json=body)
        with lock:
            answers.append((answer.status_code, answer.json()))

    threads = [threading.Thread(target=send, args=call) for call in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return answers


def main() -> None:
    url = test_url("OAK_TEST_DATABASE_URL")
    if not url:
        raise SystemExit("OAK_TEST_DATABASE_URL is not set: the check needs the test database")
    schema = f"v3_scratch_{uuid.uuid4().hex[:8]}"
    admin = make_engine(url)
    with admin.connect() as connection:
        database = connection.execute(text("select current_database()")).scalar_one()
        if database != "oak_misstatements_test":
            raise SystemExit(f"refusing to run on {database!r}")
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.commit()
    try:
        engine = admin.execution_options(schema_translate_map={None: schema})
        Base.metadata.create_all(engine)
        settings = IsolatedSettings(env="test", database_url=APP_URL, dev_user="v3@localhost")
        app = create_app(settings)
        app.state.engine.dispose()  # the placeholder for the main database is never used
        app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        app.state.backing_store = "postgresql"
        app.state.spine_client = FakeSpine().client()

        client = TestClient(app)
        created = client.post(
            "/api/engagements",
            json={
                "label": "V3 scratch engagement",
                "spine_engagement_id": str(ENGAGEMENT_ID),
                "spine_version_id": str(OPEN_VERSION_ID),
            },
        )
        assert created.status_code == 201, created.text
        engagement = created.json()["id"]
        base = f"/api/engagements/{engagement}"
        set_ = client.post(
            f"{base}/thresholds",
            json={"om": "400000.00", "pm": "250000.00", "ctt_fraction": "0.05", "basis": "V3"},
        )
        assert set_.status_code == 201, set_.text

        raise_body = {
            "type": "factual",
            "description": "V3 concurrent item",
            "raised_from": "wp",
            "source_ref": "E-1",
            "lines": [{"line_no": 5, "dr": "20000.00"}, {"line_no": 3, "cr": "20000.00"}],
        }
        raised = together(app, [(f"{base}/misstatements", raise_body)] * REQUESTS)
        statuses = sorted(status for status, _ in raised)
        refs = sorted(body.get("ref", "?") for _, body in raised)
        print(f"{REQUESTS} misstatements raised together: statuses {statuses}")
        print(f"  references issued: {refs}")
        assert statuses == [201] * REQUESTS, raised
        assert refs == sorted(f"M-{n}" for n in range(1, REQUESTS + 1)), refs

        runs = together(
            app, [(f"{base}/evaluation/runs", {"materiality_reassessed": True})] * REQUESTS
        )
        statuses = sorted(status for status, _ in runs)
        numbers = sorted(body.get("run_no", -1) for _, body in runs)
        print(f"{REQUESTS} evaluation runs recorded together: statuses {statuses}")
        print(f"  run numbers issued: {numbers}")
        assert statuses == [201] * REQUESTS, runs
        assert numbers == list(range(1, REQUESTS + 1)), numbers

        with engine.connect() as connection:
            counted = connection.execute(
                select(func.count(), func.count(distinct(EvaluationRun.run_no)))
            ).one()
            public = connection.execute(text("SELECT count(*) FROM public.evaluation")).scalar_one()
        assert public == 0, "the public schema must not have been written"
        print(
            f"  rows in the scratch evaluation table: {counted[0]}, distinct numbers: {counted[1]}"
        )
        assert tuple(counted) == (REQUESTS, REQUESTS)
        print("V3: passed. Requests at the same moment are serialised; nothing is issued twice.")
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            connection.commit()
            left = connection.execute(
                text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'v3_scratch_%'")
            ).scalar_one()
        admin.dispose()
        print(f"scratch schema dropped; scratch schemas left in the database: {left}")


if __name__ == "__main__":
    main()
