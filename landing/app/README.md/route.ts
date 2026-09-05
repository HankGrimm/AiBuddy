const README = `# Monad Mate

Stake MON to DM, match, and meet. No-shows get slashed on Monad.

Built for the **EasyA × Consensus Miami Hackathon 2026** by HankGrimm.

## How It Works

1. Connect your MetaMask or Rabby wallet
2. Stake MON to send a DM, enter a room, or propose a meetup
3. Both parties confirm via GPS attestation
4. No-show → stake slashed. Show up → stake returned + reputation boost
5. After a confirmed meetup, mint a Moment NFT

## API

Base URL: https://monad-mate-trust-api-production.up.railway.app
Docs: https://monad-mate-trust-api-production.up.railway.app/docs

## Open Source

- \`pip install monadmate-stake-sdk\` — StakeGate, SlashingPolicy
- \`pip install monadmate-reputation\` — ReputationEngine, Hedera HCS
- \`pip install monadmate-x402\` — Coinbase x402 USDC payments

## Agent Discovery

- /llms.txt — LLM summary
- /llms-full.txt — Full manifest
- /agents.md — Agent guide
- /agent.json — Machine-readable capabilities
- /openapi.json — OpenAPI spec
`

export async function GET() {
  return new Response(README, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  })
}
