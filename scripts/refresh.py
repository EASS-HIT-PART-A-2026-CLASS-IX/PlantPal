"""Async plant health refresher (Session 09 deliverable).

For each plant in the backend, POSTs a ``last_watered`` no-op PATCH to
re-trigger the health evaluation.  Uses bounded concurrency with an
``asyncio.Semaphore``, retries transient errors via ``tenacity``, and
guards against duplicate work with a Redis-backed idempotency key.

Usage:
    uv run python scripts/refresh.py --limit 10
    uv run python scripts/refresh.py --limit 10 --api-url http://localhost:8000
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import httpx
import typer
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

# Allow running from repo root (scripts/refresh.py) or from inside the
# backend container (/app where app.* is already importable).
_repo_backend = Path(__file__).resolve().parent.parent / "backend"
if _repo_backend.exists():
    sys.path.insert(0, str(_repo_backend))

from app.cache import idempotency_check_and_set  # noqa: E402
from app.config import get_settings  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("plantpal.refresh")

cli = typer.Typer(help="Async plant health refresher", add_completion=False)


@dataclass
class RefreshJob:
    plant_id: int
    plant_name: str


class PlantHealthRefresher:
    """Re-evaluates health for each plant asynchronously."""

    def __init__(
        self,
        *,
        api_base_url: str,
        max_concurrency: int,
        trace_id: str,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_base_url = api_base_url
        self.trace_id = trace_id
        self.token = token
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=api_base_url,
            timeout=10.0,
        )

    async def close(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def __aenter__(self) -> "PlantHealthRefresher":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def fetch_jobs(self, limit: int) -> list[RefreshJob]:
        resp = await self._client.get(
            "/plants/",
            params={"limit": limit},
            headers={"X-Trace-Id": self.trace_id},
        )
        resp.raise_for_status()
        return [
            RefreshJob(plant_id=p["id"], plant_name=p.get("name", "?"))
            for p in resp.json()
        ]

    async def refresh(self, jobs: Iterable[RefreshJob]) -> dict:
        tasks = [self._bounded(job) for job in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return {
            "processed": sum(1 for r in results if r == "ok"),
            "skipped_duplicate": sum(1 for r in results if r == "duplicate"),
            "total": len(results),
        }

    async def _bounded(self, job: RefreshJob) -> str:
        async with self._semaphore:
            idempotency_key = f"plant-health:{job.plant_id}:{date.today().isoformat()}"
            is_new = await idempotency_check_and_set(idempotency_key, ttl=3600)
            if not is_new:
                logger.info(
                    "skip-duplicate plant_id=%s idempotency_key=%s trace_id=%s",
                    job.plant_id,
                    idempotency_key,
                    self.trace_id,
                )
                return "duplicate"

            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential_jitter(initial=0.5, max=5.0),
                retry=retry_if_exception_type(httpx.HTTPError),
                reraise=True,
            ):
                with attempt:
                    await self._refresh_one(job, idempotency_key)
            logger.info(
                "refreshed plant_id=%s idempotency_key=%s trace_id=%s",
                job.plant_id,
                idempotency_key,
                self.trace_id,
            )
            return "ok"

    async def _refresh_one(self, job: RefreshJob, idempotency_key: str) -> None:
        headers = {
            "X-Trace-Id": self.trace_id,
            "Idempotency-Key": idempotency_key,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # A GET /plants/{id} triggers _refresh_health server-side without
        # needing auth — cheap and safe for EX2 read-only flows.
        resp = await self._client.get(f"/plants/{job.plant_id}", headers=headers)
        resp.raise_for_status()


async def _run(limit: int, api_url: str, token: str | None) -> dict:
    settings = get_settings()
    trace_id = f"{settings.trace_id}-{uuid.uuid4().hex[:8]}"
    async with PlantHealthRefresher(
        api_base_url=api_url,
        max_concurrency=settings.refresh_max_concurrency,
        trace_id=trace_id,
        token=token,
    ) as refresher:
        jobs = await refresher.fetch_jobs(limit)
        logger.info("starting trace_id=%s jobs=%d", trace_id, len(jobs))
        summary = await refresher.refresh(jobs)
        logger.info("done trace_id=%s summary=%s", trace_id, summary)
        return summary


@cli.command()
def run(
    limit: int = typer.Option(10, help="Maximum plants to refresh"),
    api_url: str = typer.Option(
        None, "--api-url", help="Override backend URL (default: settings.api_base_url)"
    ),
    token: str = typer.Option(None, "--token", help="Optional Bearer token"),
) -> None:
    """Refresh the health status for up to ``limit`` plants."""
    settings = get_settings()
    url = api_url or os.getenv("API_URL") or settings.api_base_url
    summary = asyncio.run(_run(limit=limit, api_url=url, token=token))
    typer.echo(summary)


if __name__ == "__main__":
    cli()
