"""
x402 micro-payment protocol implementation.

Spec: https://x402.org
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

WALLET_ADDRESS   = os.getenv("WALLET_ADDRESS", "0xYourBaseChainAddress")
PRICE_PER_REQUEST = float(os.getenv("PRICE_PER_REQUEST", "0.005"))

_used_nonces: Set[str] = set()
_nonce_timestamps: Dict[str, float] = {}
NONCE_TTL = 3600


class PaymentRequiredError(Exception):
    pass


class PaymentInvalidError(Exception):
    pass


def _purge_old_nonces() -> None:
    now = time.time()
    expired = [n for n, ts in _nonce_timestamps.items() if now - ts > NONCE_TTL]
    for n in expired:
        _used_nonces.discard(n)
        del _nonce_timestamps[n]


def build_payment_required_header() -> str:
    payload = {
        "protocol":   "x402",
        "version":    "1",
        "chain":      "base",
        "token":      "USDC",
        "amount":     str(PRICE_PER_REQUEST),
        "to":         WALLET_ADDRESS,
        "description": f"TunaPay TX Classifier – ${PRICE_PER_REQUEST} USDC per classification",
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _decode_payment_header(header: str) -> Dict[str, Any]:
    try:
        decoded = base64.b64decode(header.encode()).decode()
        payload = json.loads(decoded)
    except Exception as exc:
        raise PaymentInvalidError(f"Cannot decode X-Payment header: {exc}")

    required_fields = {"protocol", "version", "chain", "token", "amount", "to", "tx_hash", "nonce"}
    missing = required_fields - set(payload.keys())
    if missing:
        raise PaymentInvalidError(f"X-Payment header missing fields: {missing}")

    if payload["protocol"] != "x402":
        raise PaymentInvalidError("Unsupported payment protocol")

    if payload["chain"] != "base":
        raise PaymentInvalidError("Payment must be on Base chain")

    if payload["token"] not in ("USDC", "usdc"):
        raise PaymentInvalidError("Payment token must be USDC")

    try:
        amount = float(payload["amount"])
    except (ValueError, TypeError):
        raise PaymentInvalidError("Invalid payment amount")

    if amount < PRICE_PER_REQUEST:
        raise PaymentInvalidError(
            f"Payment amount {amount} USDC is less than required {PRICE_PER_REQUEST} USDC"
        )

    return payload


def check_payment(
    caller_id: str,
    free_remaining: int,
    x_payment: Optional[str],
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    admin_key = os.getenv("ADMIN_API_KEY", "")

    if api_key and admin_key and api_key == admin_key:
        return {"authorised": True, "method": "admin_key", "free_remaining": free_remaining}

    if free_remaining > 0:
        return {"authorised": True, "method": "free_tier", "free_remaining": free_remaining}

    if not x_payment:
        raise PaymentRequiredError(
            f"Free tier exhausted. Include X-Payment header with {PRICE_PER_REQUEST} USDC on Base chain."
        )

    payload = _decode_payment_header(x_payment)

    _purge_old_nonces()
    nonce = payload["nonce"]
    if nonce in _used_nonces:
        raise PaymentInvalidError("Payment nonce already used (replay attack prevented)")

    # TODO: Verify on-chain USDC transfer via Base chain RPC
    logger.info("Payment accepted (structure validated, on-chain TODO): nonce=%s", nonce)

    _used_nonces.add(nonce)
    _nonce_timestamps[nonce] = time.time()

    return {
        "authorised": True,
        "method":     "x402_payment",
        "tx_hash":    payload.get("tx_hash"),
        "amount":     payload.get("amount"),
        "free_remaining": 0,
    }
