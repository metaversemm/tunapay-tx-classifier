# TunaPay TX Classifier

> **中文简介**：TunaPay TX Classifier 是一个基于 MCP (Model Context Protocol) 的 Solana 链上交易分类微服务。
> 输入交易哈希，自动分析交易类型（转账、Swap、质押、NFT、DeFi 等），生成合规对账和税务分类草稿，
> 输出 CSV（兼容 TurboTax / CoinTracker）和 JSON 双格式。前 100 次免费，之后 $0.005 USDC/次（x402 协议，Base 链）。

---

A production-ready MCP microservice that classifies Solana on-chain transactions for **tax reporting and compliance**.
Feed it a transaction hash, get back a structured classification with tax category, compliance flags, and an exportable CSV report.

```
Input:  5wHu...3xKq  (Solana tx signature)
Output: { type: "swap", tax_category: "capital_gain", usd_value_estimate: 1243.50, ... }
        + CSV download (TurboTax / CoinTracker compatible)
```

## Features

- **7 transaction types**: `transfer`, `swap`, `stake`, `nft_trade`, `defi_interaction`, `token_mint`, `unknown`
- **7 tax categories**: `income`, `capital_gain`, `capital_loss`, `gift`, `self_transfer`, `fee`, `not_taxable`
- **IRS-aligned**: Notice 2014-21, Rev. Rul. 2023-14 (staking rewards)
- **Compliance flags**: large transfers (>$10k), DEX interactions, NFT trades, staking rewards, airdrops
- **CSV exports**: Full audit, CoinTracker format, TurboTax (Form 8949-compatible)
- **MCP-native**: JSON-RPC 2.0 over HTTP — works with Claude, GPT, Cursor, and any MCP client
- **Freemium**: First 100 calls free; paid via x402 (USDC on Base)
- **Demo fallback**: If RPC is unreachable, returns synthetic data clearly marked `demo_mode: true`

---

## Quick Start

### 1. MCP Configuration (Claude Desktop / Cursor)

```json
{
  "mcpServers": {
    "tunapay-tx-classifier": {
      "url": "https://tunapay-tx-classifier.fly.dev/mcp"
    }
  }
}
```

Then ask your AI assistant:
> "Classify Solana transaction 5wHuVGNbNEW9kSNYDhR9e5oU2F7CcgMH3eTJtpNR9oP"

### 2. REST API

```bash
curl -X POST https://tunapay-tx-classifier.fly.dev/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{"tx_hash": "5wHuVGNbNEW9kSNYDhR9e5oU2F7CcgMH3eTJtpNR9oP"}'
```

## Deployment

```bash
fly launch --name tunapay-tx-classifier --region sjc
fly secrets set WALLET_ADDRESS=0xYourBaseChainAddress
fly secrets set ADMIN_API_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
fly deploy
```

## License

MIT

*Built by [TaishanDigital](https://tunapay.ai) | Powered by [TunaPay](https://tunapay.ai)*
