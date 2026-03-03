"""
JSON-RPC 2.0 MCP message handler.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from fastapi.responses import JSONResponse

from src.models import ClassifiedTransaction

logger = logging.getLogger(__name__)

MCP_TOOLS = [
    {
        "name": "classify_transaction",
        "description": (
            "Classify a Solana on-chain transaction for tax reporting and compliance. "
            "Returns transaction type (swap/transfer/stake/nft_trade/defi_interaction/token_mint/unknown), "
            "IRS-aligned tax category, human-readable tax notes, and compliance flags."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tx_hash": {
                    "type": "string",
                    "description": "Solana transaction signature (base-58 encoded, ~88 characters)",
                },
                "api_key": {
                    "type": "string",
                    "description": "Optional admin API key to bypass payment requirements",
                },
            },
            "required": ["tx_hash"],
        },
    },
    {
        "name": "batch_classify",
        "description": (
            "Classify up to 100 Solana transactions in a single call. "
            "Returns all classifications plus a session_id for CSV export."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tx_hashes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of 1-100 Solana transaction signatures",
                    "maxItems": 100,
                },
                "api_key": {
                    "type": "string",
                    "description": "Optional admin API key",
                },
            },
            "required": ["tx_hashes"],
        },
    },
    {
        "name": "export_report",
        "description": (
            "Export a previous batch classification session as CSV or JSON. "
            "Supports audit, CoinTracker, and TurboTax formats."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID from a previous batch_classify call",
                },
                "format": {
                    "type": "string",
                    "enum": ["csv", "json"],
                    "description": "Output format (default: csv)",
                },
                "style": {
                    "type": "string",
                    "enum": ["audit", "cointracker", "turbotax"],
                    "description": "CSV style (default: audit)",
                },
            },
            "required": ["session_id"],
        },
    },
]


def _ok(request_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _err(request_id: Any, code: int, message: str, data: Any = None) -> JSONResponse:
    error: Dict = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": error})


async def handle_mcp_message(
    body: Dict[str, Any],
    classify_fn: Callable,
    batch_fn:    Callable,
    export_fn:   Callable,
    base_url:    str,
    sessions:    Dict[str, List[ClassifiedTransaction]],
) -> JSONResponse:
    request_id = body.get("id")
    method     = body.get("method", "")
    params     = body.get("params", {})

    if method == "initialize":
        return _ok(request_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "tunapay-tx-classifier", "version": "1.0.0"},
        })

    if method == "tools/list":
        return _ok(request_id, {"tools": MCP_TOOLS})

    if method == "tools/call":
        tool_name  = params.get("name", "")
        tool_input = params.get("arguments", params.get("input", {}))

        if tool_name == "classify_transaction":
            tx_hash = tool_input.get("tx_hash", "")
            if not tx_hash:
                return _err(request_id, -32602, "Missing required parameter: tx_hash")
            try:
                result: ClassifiedTransaction = await classify_fn(tx_hash)
                return _ok(request_id, {
                    "content": [{"type": "text", "text": result.model_dump_json(indent=2)}],
                    "isError": False,
                })
            except Exception as exc:
                return _err(request_id, -32000, str(exc))

        elif tool_name == "batch_classify":
            tx_hashes = tool_input.get("tx_hashes", [])
            if not tx_hashes:
                return _err(request_id, -32602, "Missing required parameter: tx_hashes")
            if len(tx_hashes) > 100:
                return _err(request_id, -32602, "Maximum 100 transactions per batch")
            try:
                results = await batch_fn(tx_hashes)
                import uuid, json
                session_id = str(uuid.uuid4())
                sessions[session_id] = results
                payload = {
                    "session_id": session_id,
                    "count": len(results),
                    "csv_download_url": f"{base_url}/api/v1/export/{session_id}?format=csv&style=audit",
                    "results": [r.model_dump(mode="json") for r in results],
                }
                return _ok(request_id, {
                    "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
                    "isError": False,
                })
            except Exception as exc:
                return _err(request_id, -32000, str(exc))

        elif tool_name == "export_report":
            session_id = tool_input.get("session_id", "")
            fmt        = tool_input.get("format", "csv")
            style      = tool_input.get("style", "audit")
            if not session_id:
                return _err(request_id, -32602, "Missing required parameter: session_id")
            try:
                content = await export_fn(session_id, fmt, style)
                return _ok(request_id, {
                    "content": [{"type": "text", "text": content if isinstance(content, str) else str(content)}],
                    "isError": False,
                })
            except ValueError as exc:
                return _err(request_id, -32602, str(exc))
            except Exception as exc:
                return _err(request_id, -32000, str(exc))

        else:
            return _err(request_id, -32601, f"Unknown tool: {tool_name}")

    return _err(request_id, -32601, f"Method not found: {method}")
