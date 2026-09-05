#!/usr/bin/env bash
# Deploy Monad Mate contracts to Monad testnet
set -euo pipefail

RPC_URL="${MONAD_RPC_URL:-https://testnet-rpc.monad.xyz}"

echo "=== Monad Mate — Testnet Deploy ==="
echo "RPC: $RPC_URL"

forge --version

if [[ -z "${MONAD_DEPLOYER_KEY:-}" ]]; then
  echo "MONAD_DEPLOYER_KEY is required (hex private key of the backend authority)" >&2
  exit 1
fi

cd "$(dirname "$0")/.."

echo ""
echo "Building..."
forge build

echo ""
echo "Deployer balance:"
cast balance "$(cast wallet address --private-key "$MONAD_DEPLOYER_KEY")" --rpc-url "$RPC_URL"

echo ""
echo "Deploying..."
forge script script/Deploy.s.sol:DeployMonadMate \
  --rpc-url "$RPC_URL" \
  --broadcast \
  -vvv

echo ""
echo "=== Deploy complete ==="
echo "Explorer: https://testnet.monadexplorer.com"
echo ""
echo "Copy the printed MONAD_* addresses into your backend .env, together with:"
echo "MONAD_RPC_URL=$RPC_URL"
echo "MONAD_CHAIN_ID=10143"
