"""
Per-caller usage tracking and free-tier metering.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Dict, Optional

FREE_TIER_LIMIT = int(os.getenv("FREE_TIER_LIMIT", "100"))

_usage: Dict[str, Dict] = {}


def caller_id_from_request(api_key: Optional[str], ip: str) -> str:
    if api_key:
        return "apikey:" + hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return "ip:" + hashlib.sha256(ip.encode()).hexdigest()[:16]


def get_usage(caller_id: str) -> Dict:
    return _usage.get(caller_id, {"count": 0})


def get_free_remaining(caller_id: str) -> int:
    used = _usage.get(caller_id, {"count": 0})["count"]
    return max(0, FREE_TIER_LIMIT - used)


def record_request(caller_id: str) -> None:
    now = time.time()
    if caller_id not in _usage:
        _usage[caller_id] = {"count": 0, "first_seen": now, "last_seen": now}
    _usage[caller_id]["count"] += 1
    _usage[caller_id]["last_seen"] = now
