"""
Pydantic models and enumerations for TunaPay TX Classifier.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    transfer         = "transfer"
    swap             = "swap"
    stake            = "stake"
    nft_trade        = "nft_trade"
    defi_interaction = "defi_interaction"
    token_mint       = "token_mint"
    unknown          = "unknown"


class TaxCategory(str, Enum):
    income        = "income"
    capital_gain  = "capital_gain"
    capital_loss  = "capital_loss"
    gift          = "gift"
    self_transfer = "self_transfer"
    fee           = "fee"
    not_taxable   = "not_taxable"


class ClassifiedTransaction(BaseModel):
    tx_hash:           str
    timestamp:         Optional[str]   = None
    type:              TransactionType = TransactionType.unknown
    from_address:      Optional[str]   = None
    to_address:        Optional[str]   = None
    amount:            Optional[float] = None
    token:             Optional[str]   = None
    usd_value_estimate: Optional[float] = None
    tax_category:      TaxCategory     = TaxCategory.not_taxable
    tax_notes:         str             = ""
    compliance_flags:  List[str]       = Field(default_factory=list)
    demo_mode:         bool            = False
    error:             Optional[str]   = None


class ClassifyRequest(BaseModel):
    tx_hash: str = Field(..., description="Solana transaction signature (base-58, ~88 chars)")
    api_key: Optional[str] = Field(None, description="Admin API key (bypasses payment)")


class BatchClassifyRequest(BaseModel):
    tx_hashes: List[str] = Field(..., description="1-100 Solana transaction signatures")
    api_key:   Optional[str] = None


class BatchClassifyResponse(BaseModel):
    session_id:       str
    results:          List[ClassifiedTransaction]
    counts:           Dict[str, Any]
    csv_download_url: str


class ExportReportRequest(BaseModel):
    session_id: str
    format:     str = "csv"
    style:      str = "audit"


class ExportReportResponse(BaseModel):
    session_id: str
    format:     str
    content:    str
