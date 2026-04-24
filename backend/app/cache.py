"""Redis cache helpers.

The helpers degrade gracefully: when Redis is unreachable the backend
continues to serve requests (so local dev without Redis still works),
just without the caching/idempotency speed-up.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import redis.asyncio as redis

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)


def get_redis(settings: Settings | None = None) -> redis.Redis:
    settings = settings or get_settings()
    return _client(settings.redis_url)


async def cache_get(key: str) -> Any | None:
    try:
        raw = await get_redis().get(key)
    except Exception as exc:  # pragma: no cover - depends on runtime
        logger.warning("redis-get-failed key=%s err=%s", key, exc)
        return None
    return json.loads(raw) if raw else None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    try:
        client = get_redis()
        payload = json.dumps(value, default=str)
        if ttl:
            await client.setex(key, ttl, payload)
        else:
            await client.set(key, payload)
    except Exception as exc:  # pragma: no cover
        logger.warning("redis-set-failed key=%s err=%s", key, exc)


async def cache_delete(*keys: str) -> None:
    if not keys:
        return
    try:
        await get_redis().delete(*keys)
    except Exception as exc:  # pragma: no cover
        logger.warning("redis-del-failed keys=%s err=%s", keys, exc)


async def invalidate_plants_cache() -> None:
    """Drop any cached plant list / advice entries."""
    try:
        client = get_redis()
        keys: list[str] = []
        # list keys are parametrized: plants:list:{skip}:{limit}
        async for key in client.scan_iter(match="plants:list:*"):
            keys.append(key)
        async for key in client.scan_iter(match="plants:advice:*"):
            keys.append(key)
        if keys:
            await client.delete(*keys)
    except Exception as exc:  # pragma: no cover
        logger.warning("redis-invalidate-failed err=%s", exc)


async def idempotency_check_and_set(key: str, ttl: int = 3600) -> bool:
    """Return True if this is the first time we see ``key`` (within TTL).

    Uses ``SET NX`` so the check + insert is atomic in Redis.
    """
    try:
        result = await get_redis().set(key, "1", nx=True, ex=ttl)
    except Exception as exc:  # pragma: no cover
        logger.warning("redis-idempotency-failed key=%s err=%s", key, exc)
        # Fail open: allow the work if Redis is down rather than skip it.
        return True
    return bool(result)
