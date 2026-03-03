"""
IRS-aligned tax classification rules for Solana transactions.

References:
  - IRS Notice 2014-21  (crypto as property)
  - Rev. Rul. 2023-14   (staking rewards as ordinary income)
  - IRS Publication 550 (investment income)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.models import TaxCategory, TransactionType

LARGE_TRANSFER_USD = 10_000.0


def classify_tax(
    tx_type:    TransactionType,
    tx:         Dict[str, Any],
    amount:     Optional[float],
    token:      Optional[str],
    usd:        Optional[float],
    from_addr:  Optional[str],
    to_addr:    Optional[str],
) -> Tuple[TaxCategory, str, List[str]]:
    flags: List[str] = []
    usd_str = f"${usd:,.2f}" if usd else "unknown USD value"
    amt_str = f"{amount:.4f} {token}" if amount and token else "unknown amount"

    if usd and usd >= LARGE_TRANSFER_USD:
        flags.append("large_transfer")

    if tx_type == TransactionType.swap:
        flags.append("dex_interaction")
        notes = (
            f"DEX swap involving {amt_str} (est. {usd_str}). "
            "Swapping one cryptocurrency for another is a taxable disposal "
            "under IRS Notice 2014-21. The gain or loss is measured as the "
            "difference between the fair market value of the asset received "
            "and your cost basis in the asset disposed of. "
            "Report on Form 8949 / Schedule D."
        )
        return TaxCategory.capital_gain, notes, flags

    if tx_type == TransactionType.stake:
        flags.append("staking_reward")
        notes = (
            f"Staking transaction involving {amt_str} (est. {usd_str}). "
            "Under Rev. Rul. 2023-14, staking rewards are ordinary income "
            "taxable at fair market value on the date received. "
            "Report as 'Other Income' on Schedule 1 (Form 1040)."
        )
        return TaxCategory.income, notes, flags

    if tx_type == TransactionType.nft_trade:
        flags.append("nft_purchase")
        notes = (
            f"NFT marketplace transaction involving {amt_str} (est. {usd_str}). "
            "NFT sales/purchases are taxable events under IRS Notice 2014-21. "
            "NFTs may qualify as collectibles (28% maximum rate). "
            "Report on Form 8949 / Schedule D."
        )
        return TaxCategory.capital_gain, notes, flags

    if tx_type == TransactionType.defi_interaction:
        flags.append("defi_protocol")
        notes = (
            f"DeFi protocol interaction involving {amt_str} (est. {usd_str}). "
            "DeFi interactions may generate ordinary income (yield farming, "
            "liquidity rewards) or capital gains (token swaps, withdrawals). "
            "Detailed analysis required — report on Schedule 1 or Form 8949 "
            "as appropriate."
        )
        return TaxCategory.income, notes, flags

    if tx_type == TransactionType.token_mint:
        flags.append("airdrop")
        notes = (
            f"Token mint/airdrop: {amt_str} (est. {usd_str}). "
            "Airdrops and token mints are ordinary income at fair market "
            "value on the date of receipt (IRS Notice 2014-21). "
            "Report as 'Other Income' on Schedule 1."
        )
        return TaxCategory.income, notes, flags

    if tx_type == TransactionType.transfer:
        if from_addr and to_addr and from_addr[:8] == to_addr[:8]:
            notes = (
                f"Possible self-transfer of {amt_str} (est. {usd_str}) "
                "between addresses with similar prefixes. "
                "Transfers between your own wallets are not taxable events. "
                "Verify that both addresses belong to you."
            )
            return TaxCategory.self_transfer, notes, flags

        notes = (
            f"SOL/SPL token transfer of {amt_str} (est. {usd_str}). "
            "Sending cryptocurrency is a taxable disposal if you receive "
            "something of value in return, or may be a gift (see Form 709 "
            "if value exceeds annual exclusion). If this is a sale/payment, "
            "report on Form 8949 / Schedule D."
        )
        return TaxCategory.capital_gain, notes, flags

    flags.append("smart_contract")
    notes = (
        "Unrecognised transaction type. This may involve a custom smart "
        "contract or a program not yet in the classifier's database. "
        "Manual review recommended. Consult a tax professional."
    )
    return TaxCategory.not_taxable, notes, flags
