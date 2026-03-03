"""
OpenAPI 3.1 extensions for MCP/AI discoverability.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List


def get_openapi_extra_tags() -> List[Dict[str, Any]]:
    return [
        {"name": "REST API",   "description": "Direct REST endpoints for transaction classification and export."},
        {"name": "MCP",        "description": "MCP Streamable HTTP endpoint (JSON-RPC 2.0) for AI agent access."},
        {"name": "Discovery",  "description": "Service discovery, health, and manifest endpoints."},
    ]


def get_openapi_servers() -> List[Dict[str, str]]:
    base = os.getenv("BASE_URL", "https://tunapay-tx-classifier.fly.dev")
    return [
        {"url": base,                  "description": "Production (Fly.io)"},
        {"url": "http://localhost:8080", "description": "Local development"},
    ]


OPENAPI_EXTENSIONS: Dict[str, Any] = {
    "x-mcp-endpoint":    "/mcp",
    "x-mcp-version":     "2024-11-05",
    "x-payment-required": {
        "protocol": "x402",
        "chain":    "base",
        "token":    "USDC",
        "amount":   os.getenv("PRICE_PER_REQUEST", "0.005"),
        "free_tier": os.getenv("FREE_TIER_LIMIT", "100"),
    },
    "x-agent-card": "/.well-known/agent-card.json",
}
