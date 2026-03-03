"""
Comprehensive test suite for TunaPay TX Classifier.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("WALLET_ADDRESS", "0xTestWallet")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key-12345")
os.environ.setdefault("FREE_TIER_LIMIT", "1000")

from src.app import app

client = TestClient(app)

TEST_TX = "5wHuVGNbNEW9kSNYDhR9e5oU2F7CcgMH3eTJtpNR9oP"
ADMIN_KEY = "test-admin-key-12345"


class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "tunapay-tx-classifier"


class TestRESTAPI:

    def test_classify_free_tier(self):
        r = client.post("/api/v1/classify", json={"tx_hash": TEST_TX})
        assert r.status_code == 200
        data = r.json()
        assert data["tx_hash"] == TEST_TX
        assert "type" in data
        assert "tax_category" in data
        assert "tax_notes" in data
        assert isinstance(data["compliance_flags"], list)

    def test_classify_admin_key(self):
        r = client.post(
            "/api/v1/classify",
            json={"tx_hash": TEST_TX},
            headers={"X-Api-Key": ADMIN_KEY},
        )
        assert r.status_code == 200

    def test_classify_invalid_hash(self):
        r = client.post("/api/v1/classify", json={"tx_hash": "short"})
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "unknown"
        assert data["error"] is not None

    def test_classify_response_fields(self):
        r = client.post("/api/v1/classify", json={"tx_hash": TEST_TX})
        data = r.json()
        for field in ["tx_hash", "type", "tax_category", "tax_notes", "compliance_flags", "demo_mode"]:
            assert field in data, f"Missing field: {field}"

    def test_classify_type_is_valid_enum(self):
        valid_types = {"transfer", "swap", "stake", "nft_trade", "defi_interaction", "token_mint", "unknown"}
        r = client.post("/api/v1/classify", json={"tx_hash": TEST_TX})
        assert r.json()["type"] in valid_types

    def test_classify_tax_category_is_valid_enum(self):
        valid_cats = {"income", "capital_gain", "capital_loss", "gift", "self_transfer", "fee", "not_taxable"}
        r = client.post("/api/v1/classify", json={"tx_hash": TEST_TX})
        assert r.json()["tax_category"] in valid_cats

    def test_classify_free_remaining_header(self):
        r = client.post("/api/v1/classify", json={"tx_hash": TEST_TX})
        assert "x-free-remaining" in r.headers

    def test_batch_classify_basic(self):
        hashes = [TEST_TX, "3xKqRrZWMEZcBdQnr6JKAbmLCE49VNT2FPzwxd7YhJ3m"]
        r = client.post("/api/v1/batch", json={"tx_hashes": hashes})
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data
        assert "results" in data
        assert len(data["results"]) == 2
        assert "csv_download_url" in data
        assert "counts" in data

    def test_batch_classify_too_many(self):
        hashes = [f"tx{i}" * 10 for i in range(101)]
        r = client.post("/api/v1/batch", json={"tx_hashes": hashes})
        assert r.status_code == 400

    def test_export_csv_audit(self):
        r = client.post("/api/v1/batch", json={"tx_hashes": [TEST_TX]})
        session_id = r.json()["session_id"]
        r2 = client.get(f"/api/v1/export/{session_id}?format=csv&style=audit")
        assert r2.status_code == 200
        assert "text/csv" in r2.headers["content-type"]
        lines = r2.text.strip().split("\n")
        assert len(lines) >= 2
        assert "tx_hash" in lines[0]

    def test_export_json(self):
        r = client.post("/api/v1/batch", json={"tx_hashes": [TEST_TX]})
        session_id = r.json()["session_id"]
        r2 = client.get(f"/api/v1/export/{session_id}?format=json")
        assert r2.status_code == 200
        data = r2.json()
        assert "results" in data

    def test_export_not_found(self):
        r = client.get("/api/v1/export/nonexistent-session-id?format=csv")
        assert r.status_code == 404

    def test_usage_endpoint(self):
        r = client.get("/api/v1/usage")
        assert r.status_code == 200
        data = r.json()
        assert "free_remaining" in data
        assert "total_requests" in data


class TestMCPEndpoint:

    def test_mcp_initialize(self):
        r = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "test", "version": "1.0"}},
        })
        assert r.status_code == 200
        data = r.json()
        assert data["result"]["protocolVersion"] == "2024-11-05"

    def test_mcp_tools_list(self):
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert r.status_code == 200
        tools = r.json()["result"]["tools"]
        names = [t["name"] for t in tools]
        assert "classify_transaction" in names
        assert "batch_classify" in names
        assert "export_report" in names

    def test_mcp_classify_transaction(self):
        r = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "classify_transaction", "arguments": {"tx_hash": TEST_TX}},
        })
        assert r.status_code == 200
        content = json.loads(r.json()["result"]["content"][0]["text"])
        assert content["tx_hash"] == TEST_TX

    def test_mcp_unknown_method(self):
        r = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 9, "method": "unknown/method", "params": {},
        })
        assert r.json()["error"]["code"] == -32601


class TestDiscovery:

    def test_mcp_manifest(self):
        r = client.get("/.well-known/mcp.json")
        assert r.status_code == 200
        data = r.json()
        assert "name_for_human" in data
        assert "tools" in data

    def test_agent_card(self):
        r = client.get("/.well-known/agent-card.json")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "capabilities" in data

    def test_openapi_schema(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert "openapi" in r.json()


class TestPayment:

    def test_admin_key_bypasses_limit(self):
        for _ in range(5):
            r = client.post(
                "/api/v1/classify",
                json={"tx_hash": TEST_TX},
                headers={"X-Api-Key": ADMIN_KEY},
            )
            assert r.status_code == 200
