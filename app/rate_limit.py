"""
Distributed rate limiting (Redis) with in-process fallback.

Set REDIS_URL for shared counters across workers/replicas (Render, Kubernetes, etc.).
Without Redis, uses the previous deque+Lock implementation (per-process only).
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

import redis.asyncio as redis_async
from fastapi import Request

from app.config import settings

_LOCK = Lock()
_MEMORY_STATE: dict[str, deque[float]] = {}


def get_client_ip(request: Request) -> str:
    if settings.RATE_LIMIT_TRUST_X_FORWARDED_FOR:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    client = request.client
    if not client:
        return "unknown"
    return client.host or "unknown"


def _memory_is_limited(client_ip: str, action: str, max_requests: int, window_seconds: int) -> bool:
    now = time.monotonic()
    state_key = f"{action}:{client_ip}"
    with _LOCK:
        request_times = _MEMORY_STATE.get(state_key)
        if request_times is None:
            request_times = deque()
            _MEMORY_STATE[state_key] = request_times
        while request_times and now - request_times[0] > window_seconds:
            request_times.popleft()
        if len(request_times) >= max_requests:
            return True
        request_times.append(now)
    return False


async def _redis_is_limited(
    redis_client: redis_async.Redis,
    client_ip: str,
    action: str,
    max_requests: int,
    window_seconds: int,
) -> bool:
    key = f"{settings.RATE_LIMIT_REDIS_KEY_PREFIX}:{action}:{client_ip}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window_seconds)
    return count > max_requests


async def check_rate_limited(
    request: Request,
    *,
    action: str,
    max_requests: int,
    window_seconds: int,
) -> bool:
    client_ip = get_client_ip(request)
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        try:
            return await _redis_is_limited(redis_client, client_ip, action, max_requests, window_seconds)
        except Exception:
            return _memory_is_limited(client_ip, action, max_requests, window_seconds)
    return _memory_is_limited(client_ip, action, max_requests, window_seconds)
