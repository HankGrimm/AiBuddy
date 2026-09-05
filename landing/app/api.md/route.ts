const API_MD = `# Monad Mate API Reference

Base URL: \`https://monad-mate-trust-api-production.up.railway.app\`

Full interactive docs: \`https://monad-mate-trust-api-production.up.railway.app/docs\`

## Authentication

Wallet signature challenge flow → JWT bearer token.

\`\`\`
POST /api/v1/auth/wallet/connect
Body: { "wallet_address": "string" }
Response: { "challenge": "string", "expires_at": "iso8601" }

POST /api/v1/auth/wallet/connect
Body: { "wallet_address": "string", "signature": "string", "challenge": "string" }
Response: { "access_token": "string", "token_type": "bearer" }
\`\`\`

## Rooms

\`\`\`
GET /api/v1/rooms?limit=20&offset=0
Response: { "items": [...], "total": int }
\`\`\`

## Stakes

\`\`\`
POST /api/v1/stakes
Body: { "stake_type": "dm|room|meetup", "target_id": "uuid", "amount_mon": float }
Response: { "id": "uuid", "tx_hash": "string", "status": "pending|confirmed" }
\`\`\`

## Matches

\`\`\`
POST /api/v1/matches
Body: { "target_user_id": "uuid" }
Response: { "id": "uuid", "status": "pending|matched|rejected", "intro_message": "string" }
\`\`\`

## Messages

\`\`\`
POST /api/v1/messages
Body: { "match_id": "uuid", "content": "string" }
Response: { "id": "uuid", "created_at": "iso8601" }
\`\`\`

## Attestations

\`\`\`
POST /api/v1/attestations
Body: { "meetup_id": "uuid", "gps_lat": float, "gps_lng": float, "confirmed": bool }
Response: { "id": "uuid", "status": "pending|approved|rejected" }
\`\`\`

## Transfers

\`\`\`
POST /api/v1/transfers
Body: { "recipient_wallet": "string", "amount_mon": float, "message": "string (optional)" }
Response: { "id": "uuid", "status": "pending", "tx_hash": null }
\`\`\`

## Moment NFTs

\`\`\`
POST /api/v1/nfts/mint-moment
Body: { "attestation_id": "uuid", "name": "string", "description": "string (optional)" }
Response: { "id": "uuid", "status": "pending", "mint_address": null }

GET /api/v1/nfts/moments?limit=20&offset=0
Response: { "items": [...], "total": int }
\`\`\`
`

export async function GET() {
  return new Response(API_MD, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  })
}
