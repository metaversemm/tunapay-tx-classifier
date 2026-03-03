"""
Google A2A agent card: /.well-known/agent-card.json
"""
from __future__ import annotations

import os
from typing import Any, Dict


def get_agent_card() -> Dict[str, Any]:
    base_url = os.getenv("BASE_URL", "https://tunapay-tx-classifier.fly.dev")
    return {
        "schema_version":  "a2a-v1",
        "name":            "TunaPay TX Classifier",
        "description":     (
            "An AI-accessible microservice that classifies Solana on-chain transactions "
            "for tax reporting and compliance."
        ),
        "url":             base_url,
        "version":         "1.0.0",
        "provider": {
            "name":    "TaishanDigital",
            "url":     "https://tunapay.ai",
            "contact": "support@tunapay.ai",
        },
        "capabilities": [
            "solana_transaction_classification",
            "tax_category_assignment",
            "compliance_flag_detection",
            "csv_export",
            "batch_processing",
        ],
        "protocols": ["MCP", "REST", "x402"],
        "authentication": {
            "type":        "optional",
            "description": "Admin API key via X-Api-Key header; x402 payment for paid tier.",
        },
        "pricing": {
            "free_tier":  "First 100 requests free",
            "paid_tier":  "$0.005 USDC per request via x402 on Base chain",
            "payment_address": os.getenv("WALLET_ADDRESS", "0xYourBaseChainAddress"),
        },
        "endpoints": {
            "mcp":          f"{base_url}/mcp",
            "classify":     f"{base_url}/api/v1/classify",
            "batch":        f"{base_url}/api/v1/batch",
            "export":       f"{base_url}/api/v1/export/{{session_id}}",
            "usage":        f"{base_url}/api/v1/usage",
            "health":       f"{base_url}/health",
            "openapi":      f"{base_url}/openapi.json",
            "mcp_manifest": f"{base_url}/.well-known/mcp.json",
        },
    }
