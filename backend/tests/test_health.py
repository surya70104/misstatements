"""The API starts and answers the health check without touching a database, and every
response carries the headers that keep audit content out of caches."""

from __future__ import annotations

from fastapi.testclient import TestClient

from oak_misstatements import __version__


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "module": "misstatements-rollup",
        "version": __version__,
    }


def test_every_response_is_uncacheable_and_unsniffable(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    missing = client.get("/api/nothing-here")
    assert missing.status_code == 404
    assert missing.headers["Cache-Control"] == "no-store"
