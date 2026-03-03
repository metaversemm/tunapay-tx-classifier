"""
Solana RPC client for fetching transaction data.
Falls back to synthetic demo data if the RPC is unreachable.
"""
from __future__ import annotations

import logging
import os
import random
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
RPC_TIMEOUT    = 10.0  # seconds

# ─── Known program IDs ───────────────────────────────────────────────────────
DEX_PROGRAMS = {
    "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin": "Serum v3",
    "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX":  "Serum v4",
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB":  "Jupiter v4",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4":  "Jupiter v6",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc":  "Orca Whirlpool",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
    "EewxydAPCCVuNEyrVN68PuSYdQ7wKn27V9Gjeoi8dy3S": "Lifinity",
}

NFT_PROGRAMS = {
    "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K":  "Magic Eden v2",
    "mmm3XBJg5gk8XJxEKBvdgptZz6SgK4tXvn36sodowMc":  "Magic Eden MMM",
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s":  "Metaplex Token Metadata",
    "CndyV3LdqHUfDLmE5naZjVN8rBZz4tqhdefbAnjHG3JR": "Candy Machine v3",
}

STAKE_PROGRAMS = {
    "Stake11111111111111111111111111111111111111112": "Solana Stake Program",
    "Vote111111111111111111111111111111111111111111": "Vote Program",
}

DEFI_PROGRAMS = {
    "MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD":  "Marinade",
    "So1endDq2YkqhipRh3WViPa8hdiSpxWy6z3Z6tMCpAo":  "Solend",
    "TuLipcqtGVXP9XR62wM8WWCm6a9vhLs7T1uoWBk6FDs":  "Tulip",
    "Port7uDYB3wDa8BZDkb7EZkABHGkwBXeAKZDGWyPLTH":  "Port Finance",
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "Orca v1",
    "DjVE6JNiYqPL2QXyCUUh8rNjHrbz9hXHNYt99MQ59qw1": "Orca v2",
}

ALL_KNOWN_PROGRAMS: Dict[str, str] = {**DEX_PROGRAMS, **NFT_PROGRAMS, **STAKE_PROGRAMS, **DEFI_PROGRAMS}

# ─── Demo transactions ───────────────────────────────────────────────────────
_DEMO_TRANSACTIONS = [
    {
        "demo_mode": True,
        "blockTime": 1705320896,
        "timestamp": 1705320896,
        "slot": 247891234,
        "transaction": {
            "message": {
                "accountKeys": [
                    {"pubkey": "7xKpMNFRWoLd8nBqFJmfNEhQ5Yf3FhNoPqbBsQ3Ab3xy", "signer": True,  "writable": True},
                    {"pubkey": "3mNqRrZWMEZcBdQnr6JKAbmLCE49VNT2FPzwxd7YhJ3m", "signer": False, "writable": True},
                    {"pubkey": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  "signer": False, "writable": False},
                ],
                "instructions": [
                    {"programId": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4", "accounts": [], "data": ""}
                ],
            }
        },
        "meta": {
            "fee": 5000,
            "preBalances":  [100000000, 0, 0],
            "postBalances": [ 74495000, 0, 0],
            "preTokenBalances":  [],
            "postTokenBalances": [],
            "err": None,
        },
    },
    {
        "demo_mode": True,
        "blockTime": 1705307200,
        "timestamp": 1705307200,
        "slot": 247820000,
        "transaction": {
            "message": {
                "accountKeys": [
                    {"pubkey": "9ZNTfG4NyQgxy2SWjSiQoUyBPEvXT2xo7fKc5hPYYJ7b", "signer": True,  "writable": True},
                    {"pubkey": "AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVv", "signer": False, "writable": True},
                    {"pubkey": "Stake11111111111111111111111111111111111111112", "signer": False, "writable": False},
                ],
                "instructions": [
                    {"programId": "Stake11111111111111111111111111111111111111112", "accounts": [], "data": ""}
                ],
            }
        },
        "meta": {
            "fee": 5000,
            "preBalances":  [500000000, 0, 0],
            "postBalances": [497995000, 0, 0],
            "preTokenBalances":  [],
            "postTokenBalances": [],
            "err": None,
        },
    },
    {
        "demo_mode": True,
        "blockTime": 1705280000,
        "timestamp": 1705280000,
        "slot": 247700000,
        "transaction": {
            "message": {
                "accountKeys": [
                    {"pubkey": "BcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJkLmNoPqRs", "signer": True,  "writable": True},
                    {"pubkey": "XyZaBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJkLmNo", "signer": False, "writable": True},
                    {"pubkey": "11111111111111111111111111111111", "signer": False, "writable": False},
                ],
                "instructions": [
                    {"programId": "11111111111111111111111111111111", "accounts": [], "data": ""}
                ],
            }
        },
        "meta": {
            "fee": 5000,
            "preBalances":  [1000000000, 0, 0],
            "postBalances": [899995000,  100000000, 0],
            "preTokenBalances":  [],
            "postTokenBalances": [],
            "err": None,
        },
    },
]


def _pick_demo(tx_hash: str) -> Dict[str, Any]:
    idx = sum(ord(c) for c in tx_hash) % len(_DEMO_TRANSACTIONS)
    demo = dict(_DEMO_TRANSACTIONS[idx])
    demo["_tx_hash"] = tx_hash
    return demo


async def fetch_transaction(tx_hash: str) -> Dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            tx_hash,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=RPC_TIMEOUT) as client:
            resp = await client.post(SOLANA_RPC_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result")
        if result is None:
            logger.warning("RPC returned null for tx %s – using demo data", tx_hash)
            return _pick_demo(tx_hash)

        if "blockTime" in result and "timestamp" not in result:
            result["timestamp"] = result["blockTime"]

        result["demo_mode"] = False
        return result

    except Exception as exc:
        logger.warning("RPC error for %s (%s) – using demo data", tx_hash, exc)
        return _pick_demo(tx_hash)
