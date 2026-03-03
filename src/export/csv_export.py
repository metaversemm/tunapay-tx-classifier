"""
CSV export module for classified transactions.

Supports three export styles:
  - audit:       Full record of all fields (default)
  - cointracker: CoinTracker import format
  - turbotax:    TurboTax Form 8949-compatible format
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List

from src.models import ClassifiedTransaction


AUDIT_FIELDS = [
    "tx_hash", "timestamp", "type", "from_address", "to_address",
    "amount", "token", "usd_value_estimate", "tax_category",
    "tax_notes", "compliance_flags", "demo_mode", "error",
]


def _audit_row(tx: ClassifiedTransaction) -> Dict[str, Any]:
    return {
        "tx_hash":           tx.tx_hash,
        "timestamp":         tx.timestamp or "",
        "type":              tx.type.value,
        "from_address":      tx.from_address or "",
        "to_address":        tx.to_address or "",
        "amount":            tx.amount if tx.amount is not None else "",
        "token":             tx.token or "",
        "usd_value_estimate": tx.usd_value_estimate if tx.usd_value_estimate is not None else "",
        "tax_category":      tx.tax_category.value,
        "tax_notes":         tx.tax_notes,
        "compliance_flags":  ",".join(tx.compliance_flags),
        "demo_mode":         str(tx.demo_mode).lower(),
        "error":             tx.error or "",
    }


COINTRACKER_FIELDS = [
    "Date", "Received Quantity", "Received Currency",
    "Sent Quantity", "Sent Currency", "Fee Amount", "Fee Currency", "Tag",
]


def _cointracker_row(tx: ClassifiedTransaction) -> Dict[str, Any]:
    from src.models import TransactionType, TaxCategory

    tag_map = {
        TaxCategory.income:        "staking",
        TaxCategory.capital_gain:  "",
        TaxCategory.capital_loss:  "",
        TaxCategory.gift:          "gift",
        TaxCategory.self_transfer: "transfer",
        TaxCategory.fee:           "",
        TaxCategory.not_taxable:   "",
    }
    tag = tag_map.get(tx.tax_category, "")

    if tx.type == TransactionType.swap:
        return {
            "Date": tx.timestamp or "",
            "Received Quantity": tx.amount or "",
            "Received Currency": tx.token or "",
            "Sent Quantity": tx.amount or "",
            "Sent Currency": tx.token or "",
            "Fee Amount": "",
            "Fee Currency": "SOL",
            "Tag": tag,
        }

    sent_qty  = tx.amount if tx.type in (TransactionType.transfer, TransactionType.nft_trade) else ""
    recv_qty  = tx.amount if tx.type in (TransactionType.stake, TransactionType.token_mint, TransactionType.defi_interaction) else ""

    return {
        "Date": tx.timestamp or "",
        "Received Quantity": recv_qty,
        "Received Currency": tx.token or "" if recv_qty else "",
        "Sent Quantity": sent_qty,
        "Sent Currency": tx.token or "" if sent_qty else "",
        "Fee Amount": "",
        "Fee Currency": "SOL",
        "Tag": tag,
    }


TURBOTAX_FIELDS = [
    "Description", "Date Acquired", "Date Sold",
    "Proceeds", "Cost Basis", "Gain or Loss", "Term",
]


def _turbotax_row(tx: ClassifiedTransaction) -> Dict[str, Any]:
    desc = f"{tx.token or 'Unknown'} – {tx.type.value}"
    proceeds = tx.usd_value_estimate or ""
    return {
        "Description":  desc,
        "Date Acquired": "",
        "Date Sold":    tx.timestamp or "",
        "Proceeds":     proceeds,
        "Cost Basis":   "",
        "Gain or Loss": "",
        "Term":         "SHORT",
    }


def build_export_csv(txs: List[ClassifiedTransaction], style: str = "audit") -> str:
    buf = io.StringIO()

    if style == "cointracker":
        fields   = COINTRACKER_FIELDS
        row_func = _cointracker_row
    elif style == "turbotax":
        fields   = TURBOTAX_FIELDS
        row_func = _turbotax_row
    else:
        fields   = AUDIT_FIELDS
        row_func = _audit_row

    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for tx in txs:
        writer.writerow(row_func(tx))

    return buf.getvalue()


def to_json_report(txs: List[ClassifiedTransaction]) -> Dict[str, Any]:
    results = [tx.model_dump(mode="json") for tx in txs]
    return {
        "count":   len(results),
        "results": results,
    }
