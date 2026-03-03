"""
Sliding-window rate limiter.
Default: 60 requests per minute per caller.
"""
from __future__ import annotations

import collections
import os
import time
from typing import Deque, Dict

from fastapi import HTTPException, Request

RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
WINDOW_SECONDS = 60

_windows: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(caller_id: str) -> None:
    now = time.time()
    window = _windows[caller_id]

    while window and window[0] < now - WINDOW_SECONDS:
        window.popleft()

    if len(window) >= RATE_LIMIT_RPM:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {RATE_LIMIT_RPM} requests per minute.",
            headers={"Retry-After": "60"},
        )

    window.append(now)
