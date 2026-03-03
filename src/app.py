"""
TunaPay TX Classifier – FastAPI main application.

Routes:
  POST /mcp                              – MCP Streamable HTTP (JSON-RPC 2.0)
  POST /api/v1/classify                  – REST: classify single transaction
  POST /api/v1/batch                     – REST: classify batch of transactions
  GET  /api/v1/export/{session_id}       – REST: export report
  GET  /api/v1/usage                     – REST: check usage/quota
  GET  /.well-known/mcp.json             – MCP manifest
  GET  /.well-known/agent-card.json      – Google A2A agent card
  GET  /health                           – Health check
  GET  /openapi.json + /docs             – Auto-generated OpenAPI
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import uuid
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from src.models import (
    ClassifiedTransaction,
    ClassifyRequest,
    BatchClassifyRequest,
    BatchClassifyResponse,
    ExportReportRequest,
    ExportReportResponse,
    TransactionType,
    TaxCategory,
)
from src.classifier.solana import fetch_transaction
from src.classifier.taxonomy import classify_type, extract_amount_and_token, extract_addresses
from src.classifier.tax_rules import classify_tax
from src.payment.x402 import (
    check_payment,
    PaymentRequiredError,
    PaymentInvalidError,
    build_payment_required_header,
)
from src.middleware.metering import (
    get_usage,
    record_request,
    get_free_remaining,
    caller_id_from_request,
)
from src.middleware.rate_limit import check_rate_limit, get_client_ip
from src.discovery.mcp_handler import handle_mcp_message, MCP_TOOLS
from src.discovery.mcp_manifest import get_mcp_manifest
from src.discovery.a2a_card import get_agent_card
from src.discovery.openapi_ext import get_openapi_extra_tags, get_openapi_servers, OPENAPI_EXTENSIONS
from src.export.csv_export import build_export_csv, to_json_report

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = os.getenv("BASE_URL", "https://tunapay-tx-classifier.fly.dev")

# ─── In-memory session store ──────────────────────────────────────────────────
_sessions: dict[str, list[ClassifiedTransaction]] = {}

# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="TunaPay TX Classifier",
    description=(
        "Classifies Solana on-chain transactions for tax and compliance purposes. "
        "Outputs TurboTax/CoinTracker-compatible CSV and JSON. "
        "Powered by [TunaPay](https://tunapay.ai)."
    ),
    version="1.0.0",
    contact={"name": "TaishanDigital", "url": "https://tunapay.ai"},
    license_info={"name": "MIT"},
    openapi_tags=get_openapi_extra_tags(),
    servers=get_openapi_servers(),
)

_original_openapi = app.openapi

def _custom_openapi():
    schema = _original_openapi()
    schema.update(OPENAPI_EXTENSIONS)
    return schema

app.openapi = _custom_openapi  # type: ignore[method-assign]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Payment-Required", "X-Free-Remaining", "X-Session-Id"],
)


async def _classify_one(tx_hash: str) -> ClassifiedTransaction:
    if not tx_hash or len(tx_hash) < 32:
        return ClassifiedTransaction(
            tx_hash=tx_hash,
            type=TransactionType.unknown,
            tax_category=TaxCategory.not_taxable,
            tax_notes="Invalid transaction hash format.",
            error="Invalid tx_hash",
        )

    try:
        tx = await fetch_transaction(tx_hash)
        tx_type              = classify_type(tx)
        from_addr, to_addr   = extract_addresses(tx)
        amount, token, usd   = extract_amount_and_token(tx, tx_type)
        tax_cat, notes, flags = classify_tax(
            tx_type, tx, amount, token, usd, from_addr, to_addr
        )

        raw_ts = tx.get("timestamp")
        ts_str: Optional[str] = None
        if raw_ts:
            try:
                ts_str = datetime.datetime.fromtimestamp(
                    int(raw_ts), tz=datetime.timezone.utc
                ).isoformat()
            except Exception:
                ts_str = str(raw_ts)

        return ClassifiedTransaction(
            tx_hash=tx_hash,
            timestamp=ts_str,
            type=tx_type,
            from_address=from_addr,
            to_address=to_addr,
            amount=amount,
            token=token,
            usd_value_estimate=usd,
            tax_category=tax_cat,
            tax_notes=notes,
            compliance_flags=flags,
            demo_mode=tx.get("demo_mode", False),
            error=tx.get("error"),
        )

    except Exception as exc:
        logger.exception("Unexpected error classifying %s", tx_hash)
        return ClassifiedTransaction(
            tx_hash=tx_hash,
            type=TransactionType.unknown,
            tax_category=TaxCategory.not_taxable,
            tax_notes="An unexpected error occurred during classification.",
            error=str(exc),
        )


def _get_caller(request: Request, api_key: Optional[str]) -> str:
    ip = get_client_ip(request)
    return caller_id_from_request(api_key, ip)


def _gate(request: Request, api_key: Optional[str], x_payment: Optional[str]) -> dict:
    caller_id = _get_caller(request, api_key)
    check_rate_limit(caller_id)
    free_left = get_free_remaining(caller_id)
    return check_payment(caller_id, free_left, x_payment, api_key)


@app.get("/health", tags=["Discovery"])
async def health():
    return {"status": "ok", "service": "tunapay-tx-classifier", "version": "1.0.0"}


@app.post("/api/v1/classify", response_model=ClassifiedTransaction, tags=["REST API"])
async def classify_transaction(
    body: ClassifyRequest,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_payment: Optional[str] = Header(None, alias="X-Payment"),
):
    try:
        payment_status = _gate(request, x_api_key, x_payment)
    except PaymentRequiredError as exc:
        resp = JSONResponse(status_code=402, content={"detail": str(exc)})
        resp.headers["Payment-Required"] = build_payment_required_header()
        return resp
    except PaymentInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    caller_id = _get_caller(request, x_api_key)
    result = await _classify_one(body.tx_hash)
    record_request(caller_id)

    response = JSONResponse(content=result.model_dump(mode="json"))
    response.headers["X-Free-Remaining"] = str(get_free_remaining(caller_id))
    return response


@app.post("/api/v1/batch", response_model=BatchClassifyResponse, tags=["REST API"])
async def batch_classify(
    body: BatchClassifyRequest,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_payment: Optional[str] = Header(None, alias="X-Payment"),
):
    if len(body.tx_hashes) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 transactions per batch.")

    try:
        payment_status = _gate(request, x_api_key, x_payment)
    except PaymentRequiredError as exc:
        resp = JSONResponse(status_code=402, content={"detail": str(exc)})
        resp.headers["Payment-Required"] = build_payment_required_header()
        return resp
    except PaymentInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    caller_id = _get_caller(request, x_api_key)
    results = await asyncio.gather(*[_classify_one(h) for h in body.tx_hashes])

    for _ in results:
        record_request(caller_id)

    session_id = str(uuid.uuid4())
    _sessions[session_id] = list(results)

    counts = {
        "total": len(results),
        "by_type": {},
        "by_tax_category": {},
        "errors": sum(1 for r in results if r.error),
    }
    for r in results:
        counts["by_type"][r.type.value] = counts["by_type"].get(r.type.value, 0) + 1
        counts["by_tax_category"][r.tax_category.value] = counts["by_tax_category"].get(r.tax_category.value, 0) + 1

    csv_url = f"{BASE_URL}/api/v1/export/{session_id}?format=csv&style=audit"

    return BatchClassifyResponse(
        session_id=session_id,
        results=list(results),
        counts=counts,
        csv_download_url=csv_url,
    )


@app.get("/api/v1/export/{session_id}", tags=["REST API"])
async def export_report(
    session_id: str,
    format: str = "csv",
    style: str = "audit",
):
    txs = _sessions.get(session_id)
    if not txs:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    if format == "json":
        return JSONResponse(content=to_json_report(txs))

    csv_content = build_export_csv(txs, style=style)
    filename = f"tunapay-export-{session_id[:8]}-{style}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/usage", tags=["REST API"])
async def usage(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
):
    caller_id = _get_caller(request, x_api_key)
    usage_data = get_usage(caller_id)
    free_remaining = get_free_remaining(caller_id)
    return {
        "caller_id": caller_id[:8] + "...",
        "total_requests": usage_data.get("count", 0),
        "free_remaining": free_remaining,
        "paid_tier": free_remaining == 0,
    }


@app.post("/mcp", tags=["MCP"])
async def mcp_endpoint(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_payment: Optional[str] = Header(None, alias="X-Payment"),
):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
        )

    async def _classify_wrapper(tx_hash: str) -> ClassifiedTransaction:
        try:
            _gate(request, x_api_key, x_payment)
        except PaymentRequiredError:
            raise
        except PaymentInvalidError as e:
            raise HTTPException(status_code=400, detail=str(e))
        caller_id = _get_caller(request, x_api_key)
        result = await _classify_one(tx_hash)
        record_request(caller_id)
        return result

    async def _batch_wrapper(tx_hashes: list) -> list:
        try:
            _gate(request, x_api_key, x_payment)
        except PaymentRequiredError:
            raise
        caller_id = _get_caller(request, x_api_key)
        results = await asyncio.gather(*[_classify_one(h) for h in tx_hashes])
        for _ in results:
            record_request(caller_id)
        return list(results)

    async def _export_wrapper(session_id: str, fmt: str = "csv", style: str = "audit"):
        txs = _sessions.get(session_id)
        if not txs:
            raise ValueError("Session not found")
        if fmt == "json":
            return to_json_report(txs)
        return build_export_csv(txs, style=style)

    return await handle_mcp_message(
        body,
        classify_fn=_classify_wrapper,
        batch_fn=_batch_wrapper,
        export_fn=_export_wrapper,
        base_url=BASE_URL,
        sessions=_sessions,
    )


@app.get("/.well-known/mcp.json", tags=["Discovery"])
async def mcp_manifest():
    return JSONResponse(content=get_mcp_manifest())


@app.get("/.well-known/agent-card.json", tags=["Discovery"])
async def agent_card():
    return JSONResponse(content=get_agent_card())
