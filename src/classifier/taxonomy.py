"""
Transaction type classification logic.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.models import TransactionType
from src.classifier.solana import (
    DEX_PROGRAMS,
    NFT_PROGRAMS,
    STAKE_PROGRAMS,
    DEFI_PROGRAMS,
)


def _get_program_ids(tx: Dict[str, Any]) -> list[str]:
    program_ids: list[str] = []

    try:
        msg = tx["transaction"]["message"]
        for ix in msg.get("instructions", []):
            pid = ix.get("programId") or ix.get("program")
            if pid:
                program_ids.append(pid)
            for inner in ix.get("innerInstructions", []):
                for iix in inner.get("instructions", []):
                    ipid = iix.get("programId") or iix.get("program")
                    if ipid:
                        program_ids.append(ipid)
    except (KeyError, TypeError):
        pass

    try:
        for key_info in tx["transaction"]["message"].get("accountKeys", []):
            if isinstance(key_info, dict):
                pk = key_info.get("pubkey", "")
            else:
                pk = str(key_info)
            if pk in DEX_PROGRAMS or pk in NFT_PROGRAMS or pk in STAKE_PROGRAMS or pk in DEFI_PROGRAMS:
                program_ids.append(pk)
    except (KeyError, TypeError):
        pass

    return list(set(program_ids))


def classify_type(tx: Dict[str, Any]) -> TransactionType:
    if tx.get("meta", {}).get("err") is not None:
        return TransactionType.unknown

    program_ids = _get_program_ids(tx)

    if any(pid in DEX_PROGRAMS for pid in program_ids):
        return TransactionType.swap

    if any(pid in NFT_PROGRAMS for pid in program_ids):
        return TransactionType.nft_trade

    if any(pid in STAKE_PROGRAMS for pid in program_ids):
        return TransactionType.stake

    if any(pid in DEFI_PROGRAMS for pid in program_ids):
        return TransactionType.defi_interaction

    TOKEN_PROGRAM   = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    TOKEN_2022      = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
    ASSOC_TOKEN     = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJe1bRS"
    SYSTEM_PROGRAM  = "11111111111111111111111111111111"

    has_token_program = any(pid in (TOKEN_PROGRAM, TOKEN_2022) for pid in program_ids)
    has_assoc_token   = any(pid == ASSOC_TOKEN for pid in program_ids)
    has_system        = any(pid == SYSTEM_PROGRAM for pid in program_ids)

    if has_token_program and has_assoc_token and not has_system:
        return TransactionType.token_mint

    if has_system or has_token_program:
        return TransactionType.transfer

    return TransactionType.unknown


def extract_addresses(tx: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    try:
        keys = tx["transaction"]["message"].get("accountKeys", [])
        if not keys:
            return None, None

        def _pubkey(k):
            return k["pubkey"] if isinstance(k, dict) else str(k)

        sender = None
        receiver = None

        for k in keys:
            info = k if isinstance(k, dict) else {}
            if info.get("signer") and info.get("writable"):
                sender = _pubkey(k)
                break
        if sender is None and keys:
            sender = _pubkey(keys[0])

        for k in keys:
            info = k if isinstance(k, dict) else {}
            if info.get("writable") and not info.get("signer"):
                receiver = _pubkey(k)
                break

        return sender, receiver

    except (KeyError, TypeError, IndexError):
        return None, None


_APPROX_USD: Dict[str, float] = {
    "SOL":  155.0,
    "BTC":  43000.0,
    "ETH":  2300.0,
    "USDC": 1.0,
    "USDT": 1.0,
    "BONK": 0.000012,
    "JTO":  3.5,
    "WIF":  0.45,
    "PYTH": 0.42,
    "JUP":  0.85,
}


def extract_amount_and_token(
    tx: Dict[str, Any],
    tx_type: "TransactionType",
) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    meta = tx.get("meta", {})

    pre_tok  = meta.get("preTokenBalances",  [])
    post_tok = meta.get("postTokenBalances", [])

    if pre_tok or post_tok:
        pre_map: Dict[str, Dict] = {}
        post_map: Dict[str, Dict] = {}
        for b in pre_tok:
            acct = b.get("accountIndex", b.get("mint", ""))
            pre_map[str(acct)] = b
        for b in post_tok:
            acct = b.get("accountIndex", b.get("mint", ""))
            post_map[str(acct)] = b

        best_amount: Optional[float] = None
        best_token:  Optional[str]   = None

        all_accts = set(pre_map) | set(post_map)
        for acct in all_accts:
            pre_ui  = float(pre_map.get(acct,  {}).get("uiTokenAmount", {}).get("uiAmount") or 0)
            post_ui = float(post_map.get(acct, {}).get("uiTokenAmount", {}).get("uiAmount") or 0)
            delta   = abs(post_ui - pre_ui)
            if delta > 0:
                if best_amount is None or delta > best_amount:
                    best_amount = delta
                    mint = (
                        post_map.get(acct, {}).get("mint")
                        or pre_map.get(acct, {}).get("mint")
                        or "UNKNOWN"
                    )
                    best_token = _mint_to_symbol(mint)

        if best_amount is not None and best_token is not None:
            usd = best_amount * _APPROX_USD.get(best_token, 0.0)
            return best_amount, best_token, usd if usd > 0 else None

    pre_bal  = meta.get("preBalances",  [])
    post_bal = meta.get("postBalances", [])
    fee      = meta.get("fee", 0)

    if pre_bal and post_bal:
        max_delta = 0.0
        for i, (pre, post) in enumerate(zip(pre_bal, post_bal)):
            delta = abs(post - pre)
            if i == 0:
                delta = abs((post + fee) - pre)
            if delta > max_delta:
                max_delta = delta

        if max_delta > 0:
            sol_amount = max_delta / 1_000_000_000
            usd = sol_amount * _APPROX_USD["SOL"]
            return sol_amount, "SOL", usd

    return None, None, None


_MINT_SYMBOLS: Dict[str, str] = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "So11111111111111111111111111111111111111112":   "SOL",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "jtojtomepa8bdiya1oye8qUkH4RvrmMiPX5iMEEkNya":  "JTO",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "WIF",
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3": "PYTH",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN":  "JUP",
}


def _mint_to_symbol(mint: str) -> str:
    return _MINT_SYMBOLS.get(mint, mint[:8] + "...")
