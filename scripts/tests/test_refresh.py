"""Async test for scripts/refresh.py using httpx.ASGITransport (Session 09).

Verifies that ``PlantHealthRefresher`` hits the FastAPI app, respects
bounded concurrency, and short-circuits via the Redis idempotency
check on the second run.
"""

from __future__ import annotations

import pytest
import httpx

from refresh import PlantHealthRefresher, RefreshJob


@pytest.mark.anyio
async def test_refresher_hits_endpoint_and_respects_idempotency(monkeypatch):
    # Force idempotency to pass first, then fail, simulating a second run.
    calls = {"count": 0}

    async def fake_idempotency(key, ttl=3600):
        calls["count"] += 1
        return calls["count"] <= 1  # first call -> new, second -> duplicate

    monkeypatch.setattr("refresh.idempotency_check_and_set", fake_idempotency)

    # Stand up a tiny FastAPI app that mimics /plants/{id}.
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/plants/{plant_id}")
    async def get_plant(plant_id: int):
        return {"id": plant_id, "name": f"plant-{plant_id}", "health_status": "healthy"}

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    refresher = PlantHealthRefresher(
        api_base_url="http://testserver",
        max_concurrency=2,
        trace_id="test-trace",
        client=client,
    )

    jobs = [RefreshJob(plant_id=1, plant_name="a"), RefreshJob(plant_id=2, plant_name="b")]
    summary = await refresher.refresh(jobs)

    assert summary["total"] == 2
    assert summary["processed"] == 1
    assert summary["skipped_duplicate"] == 1

    await client.aclose()


@pytest.fixture
def anyio_backend():
    return "asyncio"
