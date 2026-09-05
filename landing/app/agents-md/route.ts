const AGENTS_MD = `# Monad Mate — Agent Interaction Guide

## What Monad Mate Is

Monad Mate is a trust-based social dApp on Monad. Users stake MON to send DMs, enter rooms, and confirm meetups. No-shows are automatically slashed. AI matchmaking is powered by AINative embeddings and ZeroDB semantic search.

Built for the EasyA × Consensus Miami Hackathon 2026 by HankGrimm.

## API Base

\`\`\`
https://monad-mate-trust-api-production.up.railway.app
\`\`\`

Interactive docs: \`https://monad-mate-trust-api-production.up.railway.app/docs\`

## Authentication (for agents)

Monad Mate uses wallet-signature JWT authentication:

1. \`POST /api/v1/auth/wallet/connect\` with \`{ "wallet_address": "<address>" }\` → returns \`challenge\`
2. Sign the challenge with the wallet private key
3. \`POST /api/v1/auth/wallet/connect\` with \`{ "wallet_address", "signature", "challenge" }\` → returns \`access_token\`
4. Include \`Authorization: Bearer <access_token>\` on all subsequent requests

## Actions Available to Agents

| Action | Method | Path |
|--------|--------|------|
| Discover rooms | GET | /api/v1/rooms |
| Create a stake | POST | /api/v1/stakes |
| Request a match | POST | /api/v1/matches |
| Send a message | POST | /api/v1/messages |
| Submit meetup attestation | POST | /api/v1/attestations |
| Gift MON to a user | POST | /api/v1/transfers |
| Mint a Moment NFT | POST | /api/v1/nfts/mint-moment |
| List my Moment NFTs | GET | /api/v1/nfts/moments |

## Open Source SDKs

\`\`\`bash
pip install monadmate-stake-sdk    # StakeGate, SlashingPolicy
pip install monadmate-reputation   # ReputationEngine, Hedera HCS anchoring
pip install monadmate-x402         # Coinbase x402 MON payment middleware
\`\`\`

## Full Reference

- Full API manifest: /llms-full.txt
- OpenAPI spec: /openapi.json
- SDK details: /sdks.txt
`

export async function GET() {
  return new Response(AGENTS_MD, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  })
}
