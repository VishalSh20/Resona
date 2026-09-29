"""Health and readiness endpoint tests."""

from __future__ import annotations


async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_request_id_header_echoed(client):
    resp = await client.get("/health", headers={"X-Request-ID": "req-123"})
    assert resp.headers["X-Request-ID"] == "req-123"


async def test_request_id_generated_when_absent(client):
    resp = await client.get("/health")
    assert resp.headers.get("X-Request-ID")
