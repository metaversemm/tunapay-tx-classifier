"""
MCP manifest endpoint: /.well-known/mcp.json
"""
from __future__ import annotations

import os
from typing import Any, Dict


def get_mcp_manifest() -> Dict[str, Any]:
    base_url = os.getenv("BASE_URL", "https://tunapay-tx-classifier.fly.dev")
    return {
        "schema_version": "v1",
        "name_for_human": "TunaPay TX Classifier",
        "name_for_model": "tunapay_tx_classifier",
        "description_for_human": (
            "Classify Solana transactions for tax reporting. "
            "Returns type, IRS tax category, and CSV export for TurboTax/CoinTracker."
        ),
        "description_for_model": (
            "Solana transaction classifier for tax/compliance. "
            "Use classify_transaction for single tx, batch_classify for multiple, "
            "export_report for CSV download. "
            "Free for first 100 calls, then $0.005 USDC per call via x402."
        ),
        "auth": {"type": "none"},
        "api": {
            "type": "openapi",
            "url": f"{base_url}/openapi.json",
        },
        "pricing": {
            "free_tier": "100 requests",
            "paid_tier": "$0.005 USDC per request via x402 (Base chain)",
        },
        "tools": [
            {
                "name": "classify_transaction",
                "endpoint": f"{base_url}/mcp",
                "description": "Classify a single Solana tx for tax purposes",
            },
            {
                "name": "batch_classify",
                "endpoint": f"{base_url}/mcp",
                "description": "Classify up to 100 transactions",
            },
            {
                "name": "export_report",
                "endpoint": f"{base_url}/mcp",
                "description": "Export batch results as CSV (audit/CoinTracker/TurboTax)",
            },
        ],
    }
