"""Redis-backed fixed-window rate limiter middleware.

Attaches ``X-RateLimit-*`` headers and returns 429 when the per-minute
budget for the client IP is exceeded.  Falls open when Redis is down.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.cache import get_redis
from app.config import get_settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        max_requests = settings.rate_limit_per_minute

        if request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        client_host = request.client.host if request.client else "anonymous"
        key = f"rate:{client_host}:{request.url.path}"

        try:
            redis_client = get_redis(settings)
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, 60)
        except Exception as exc:
            logger.warning("rate-limit-bypass err=%s", exc)
            return await call_next(request)

        if current > max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(max_requests - current, 0))
        return response
