"""
Fixed-window rate limiting via Redis INCR + EXPIRE — cheap, good enough
for per-user/IP throttling. Swap for a token-bucket (e.g. redis-cell) if
you need smoother burst handling later.
"""
import time

import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

settings = get_settings()
_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1/auth"):
            key_source = request.client.host if request.client else "unknown"
        else:
            auth_header = request.headers.get("authorization", "")
            key_source = auth_header[-32:] if auth_header else (request.client.host if request.client else "unknown")

        window = int(time.time() // 60)
        key = f"ratelimit:{key_source}:{window}"

        try:
            r = _get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 60)
        except redis.RedisError:
            # Fail open — Redis being down shouldn't take the API down with it.
            return await call_next(request)

        if count > settings.rate_limit_per_minute:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")

        return await call_next(request)
