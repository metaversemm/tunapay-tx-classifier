#!/bin/bash
# TunaPay TX Classifier - 一键部署脚本
set -e

echo "=== TunaPay TX Classifier 部署 ==="

if ! command -v fly &> /dev/null; then
    echo "[1/5] 安装 Fly.io CLI..."
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
else
    echo "[1/5] Fly.io CLI 已安装 ✓"
fi

echo "[2/5] 登录 Fly.io..."
fly auth login

echo "[3/5] 创建应用..."
fly launch --copy-config --no-deploy --name tunapay-tx-classifier

echo "[4/5] 设置环境变量..."
fly secrets set \
    WALLET_ADDRESS=0xYourBaseChainAddress \
    ADMIN_API_KEY=your-secret-here

echo "[5/5] 部署中..."
fly deploy

echo "服务地址: https://tunapay-tx-classifier.fly.dev"
