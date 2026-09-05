# Monad Mate Trust API — Developer Guide

**Base URL:** `https://monad-mate-trust-api-production.up.railway.app`  
**API Version:** v1  
**Auth:** JWT Bearer tokens (wallet-signed)  
**Protocol:** HTTPS/REST + JSON

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Users & Personas](#users--personas)
4. [Rooms](#rooms)
5. [Stakes & Escrow](#stakes--escrow)
6. [Matches & Messages](#matches--messages)
7. [Attestations](#attestations)
8. [Reputation](#reputation)
9. [Safety](#safety)
10. [AI Matchmaking](#ai-matchmaking)
11. [Moment NFTs](#moment-nfts)
12. [MON Transfers](#mon-transfers)
13. [Error Codes](#error-codes)
14. [Rate Limits](#rate-limits)

---

## Overview

Monad Mate is a stake-gated social dApp on Monad. Users stake MON to DM, match, and meet. No-shows get slashed. All social interactions require economic accountability.

**Key design principles:**
- All sensitive actions require an active stake
- Reputation is multi-dimensional (5 axes) with time decay
- Meetup attestation is GPS-verified by both parties
- Safety events are anchored on Hedera HCS for immutability

**Tech stack:**
- Monad (EIP-191 wallet auth, EventLog, Solidity escrow)
- FastAPI + SQLAlchemy 2.0 + PostgreSQL
- ZeroDB (768-dim BAAI/bge-base-en-v1.5 vectors)
- llama-3.3-70b via AINative (intro generation)
- Hedera HCS (immutable audit log)
- Coinbase x402 (HTTP-native MON payments)

---

## Authentication

Monad Mate uses a **challenge-response wallet authentication** flow. No passwords — only cryptographic proof of wallet ownership.

### Step 1: Request a Nonce Challenge

```http
POST /v1/users/challenge
Content-Type: application/json

{
  "wallet_address": "0x9C8fF314C9Bc7F6e59A9d9225Fb22946427eDC03"
}
```

**Response:**
```json
{
  "nonce": "abc123def456",
  "expires_at": "2026-05-06T12:05:00Z"
}
```

The nonce expires in 5 minutes. Sign it with your wallet.

---

### Step 2: Onboard / Login

Submit the signed nonce to authenticate and receive a JWT:

```http
POST /v1/users/onboard
Content-Type: application/json

{
  "wallet_address": "0x9C8fF314C9Bc7F6e59A9d9225Fb22946427eDC03",
  "signature": "<0x-prefixed-65-byte-eip191-signature>",
  "nonce": "abc123def456",
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "wallet_address": "0x9C8fF314C9Bc7F6e59A9d9225Fb22946427eDC03",
    "did": "did:pkh:eip155:10143:0x9C8f...",
    "age_verified": false,
    "verification_level": "basic",
    "privacy_mode": false,
    "created_at": "2026-05-06T12:00:00Z"
  }
}
```

---

### Using the Token

Include the JWT on all authenticated requests:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Users & Personas

### Get Current User

```http
GET /v1/users/me
Authorization: Bearer <token>
```

**Response:** `UserResponse` — id, wallet_address, did, age_verified, verification_level, privacy_mode, created_at

---

### Update User Profile

```http
PATCH /v1/users/me
Authorization: Bearer <token>
Content-Type: application/json

{
  "email": "new@example.com",
  "privacy_mode": true
}
```

---

### Personas

A user can have multiple personas — each with different visibility, intent, and expiry. This enables context-specific identities (e.g., one for networking events, another for dating).

#### Create Persona

```http
POST /v1/personas
Authorization: Bearer <token>
Content-Type: application/json

{
  "display_name": "Alex",
  "avatar_url": "https://cdn.example.com/avatar.jpg",
  "bio": "Coffee addict, builder, Monad maxi.",
  "intent_mode": "social",
  "visibility_scope": "room",
  "expires_at": "2026-06-01T00:00:00Z"
}
```

**`intent_mode` values:** `social`, `dating`, `networking`, `professional`  
**`visibility_scope` values:** `public`, `room`, `match`

**Response:** `PersonaResponse` — id, user_id, display_name, avatar_url, bio, intent_mode, visibility_scope, is_active, expires_at, created_at

---

#### List My Personas

```http
GET /v1/personas/me
Authorization: Bearer <token>
```

---

#### Deactivate Persona

```http
DELETE /v1/personas/{persona_id}
Authorization: Bearer <token>
```

Returns `204 No Content`.

---

## Rooms

Rooms are geo-located social spaces. Joining requires a stake. Discovery is proximity-based.

### Create Room

```http
POST /v1/rooms
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Consensus Miami 2026 — Builder Lounge",
  "description": "Monad builders only. No VCs.",
  "type": "event",
  "location": "Brickell City Centre, Miami, FL",
  "latitude": 25.7617,
  "longitude": -80.1918,
  "geofence_radius_meters": 200,
  "starts_at": "2026-05-29T10:00:00Z",
  "ends_at": "2026-05-29T22:00:00Z",
  "privacy_level": "invite",
  "stake_required": true,
  "intent_modes": ["networking", "social"],
  "max_members": 50
}
```

**`type` values:** `event`, `venue`, `virtual`, `popup`  
**`privacy_level` values:** `public`, `invite`, `private`

---

### List Rooms

```http
GET /v1/rooms?type=event&latitude=25.7617&longitude=-80.1918&radius_km=5&skip=0&limit=20
Authorization: Bearer <token>
```

---

### Discover Nearby Rooms

```http
GET /v1/rooms/discover?lat=25.7617&lng=-80.1918&radius_km=10&intent_mode=networking
Authorization: Bearer <token>
```

Returns rooms sorted by proximity within the radius.

---

### Get Room

```http
GET /v1/rooms/{room_id}
Authorization: Bearer <token>
```

---

### Join Room

```http
POST /v1/rooms/{room_id}/join
Authorization: Bearer <token>
Content-Type: application/json

{
  "persona_id": "uuid",
  "stake_tx_hash": "0x4f3a91c7..."
}
```

Requires an active stake transaction on Monad. The `stake_tx_hash` is verified on-chain.

---

### Leave Room

```http
POST /v1/rooms/{room_id}/leave?persona_id={persona_id}
Authorization: Bearer <token>
```

---

### Get Room Members

```http
GET /v1/rooms/{room_id}/members
Authorization: Bearer <token>
```

Returns `List[PersonaResponse]` for all active members.

---

## Stakes & Escrow

Stakes are MON locked on Monad before any high-trust interaction. No stake = no action.

### Stake Types

| Type | Required For | Default Amount |
|------|-------------|----------------|
| `dm` | Sending first DM | 0.50 MON |
| `room_entry` | Joining a room | 1.00 MON |
| `meetup` | Proposing a meetup | 5.00 MON |

### Create Stake

```http
POST /v1/stakes
Authorization: Bearer <token>
Content-Type: application/json

{
  "stake_type": "dm",
  "amount_mon": 0.50,
  "room_id": "uuid",
  "target_user_id": "uuid",
  "tx_hash": "0x4f3a91c7..."
}
```

**Note:** For DM stakes with x402 enabled, an `X-Payment` header with a valid Coinbase x402 MON proof is also required.

**Response:** `StakeResponse`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "stake_type": "dm",
  "status": "active",
  "amount_mon": 0.50,
  "currency": "MON",
  "tx_hash": "0x4f3a91c7...",
  "escrow_id": "uuid",
  "expires_at": "2026-05-07T12:00:00Z",
  "created_at": "2026-05-06T12:00:00Z",
  "resolved_at": null,
  "explorer_url": "https://testnet.monadexplorer.com/tx/0x4f3a91c7..."
}
```

---

### List My Stakes

```http
GET /v1/stakes/me
Authorization: Bearer <token>
```

---

### Refund Stake

Refunds an active stake if the interaction completed without violation.

```http
POST /v1/stakes/{stake_id}/refund
Authorization: Bearer <token>
```

---

### Slash Stake

Slashes a stake for a policy violation.

```http
POST /v1/stakes/{stake_id}/slash
Authorization: Bearer <token>
Content-Type: application/json

{
  "reason": "User did not show up to confirmed meetup at 25.761, -80.191"
}
```

`reason` must be at least 10 characters. Slash amounts:
- First offense: 50% of stake
- Each subsequent offense: +0.5x multiplier (capped at 3x)
- Harassment / fake profile: 100% slash

---

### Meetup Escrow

#### Create Escrow

```http
POST /v1/escrow/meetup
Authorization: Bearer <token>
Content-Type: application/json

{
  "type": "meetup",
  "counterparty_user_id": "uuid",
  "amount_mon": 5.00,
  "confirm_deadline": "2026-05-07T18:00:00Z"
}
```

**Response:** `EscrowResponse` — id, type, initiator_id, counterparty_id, amount_mon, status, confirm_deadline, created_at

---

#### Confirm Escrow

Both parties must confirm for escrow to release.

```http
POST /v1/escrow/{escrow_id}/confirm
Authorization: Bearer <token>
```

---

#### Dispute Escrow

```http
POST /v1/escrow/{escrow_id}/dispute
Authorization: Bearer <token>
Content-Type: application/json

{
  "reason": "Counterparty arrived 2 hours late and was verbally abusive. Evidence: screenshot attached."
}
```

`reason` must be at least 20 characters.

---

## Matches & Messages

### Request a Match

```http
POST /v1/matches/request
Authorization: Bearer <token>
Content-Type: application/json

{
  "target_persona_id": "uuid",
  "room_id": "uuid",
  "intro_message": "Hey! I noticed we're both building on Monad. Would love to connect.",
  "stake_id": "uuid"
}
```

**Response:** `MatchResponse`
```json
{
  "id": "uuid",
  "room_id": "uuid",
  "requester_persona_id": "uuid",
  "target_persona_id": "uuid",
  "stake_id": "uuid",
  "status": "pending",
  "consent_state": "awaiting",
  "compatibility_score": 0.87,
  "expires_at": "2026-05-07T12:00:00Z",
  "created_at": "2026-05-06T12:00:00Z",
  "responded_at": null
}
```

---

### Accept Match

```http
POST /v1/matches/{match_id}/accept
Authorization: Bearer <token>
```

---

### Reject Match

```http
POST /v1/matches/{match_id}/reject
Authorization: Bearer <token>
```

---

### List My Matches

```http
GET /v1/matches/me?skip=0&limit=20
Authorization: Bearer <token>
```

**Response:** `MatchList` — matches (array), total

---

### Send Message

Requires an active DM stake.

```http
POST /v1/messages
Authorization: Bearer <token>
Content-Type: application/json

{
  "match_id": "uuid",
  "content": "Great to connect! When are you free?",
  "type": "text",
  "stake_id": "uuid"
}
```

**`type` values:** `text`, `image`, `link`

**Response:** `MessageResponse` — id, match_id, sender_id, content, type, stake_id, created_at

---

### Get Message Thread

```http
GET /v1/messages/{match_id}?skip=0&limit=50
Authorization: Bearer <token>
```

**Response:** `MessageThread` — messages (array), total, match_id

---

## Attestations

Attestations are cryptographic proofs that two people physically met. Both parties must confirm.

### Initiate Meetup Attestation

```http
POST /v1/attestations/meetup/initiate
Authorization: Bearer <token>
Content-Type: application/json

{
  "match_id": "uuid",
  "method": "gps",
  "latitude": 25.7617,
  "longitude": -80.1918,
  "escrow_id": "uuid"
}
```

**`method` values:** `gps`, `qr_code`, `nfc`

**Response:** `AttestationResponse`
```json
{
  "id": "uuid",
  "match_id": "uuid",
  "method": "gps",
  "status": "pending",
  "token": "ATT-abc123",
  "initiator_confirmed": true,
  "counterparty_confirmed": false,
  "hcs_message_id": null,
  "expires_at": "2026-05-06T14:00:00Z",
  "created_at": "2026-05-06T12:00:00Z",
  "confirmed_at": null
}
```

---

### Confirm Meetup Attestation

The counterparty confirms using the token from the initiator.

```http
POST /v1/attestations/meetup/{attestation_id}/confirm
Authorization: Bearer <token>
Content-Type: application/json

{
  "token": "ATT-abc123",
  "latitude": 25.7617,
  "longitude": -80.1918
}
```

Once both parties confirm, `status` becomes `confirmed` and the HCS message ID is populated (Hedera audit log entry created).

---

### Verify Proximity

```http
POST /v1/attestations/proximity
Authorization: Bearer <token>
Content-Type: application/json

{
  "match_id": "uuid",
  "method": "gps",
  "latitude": 25.7617,
  "longitude": -80.1918,
  "escrow_id": "uuid"
}
```

Returns whether two users are within the required geofence radius.

---

### List My Attestations

```http
GET /v1/attestations/me
Authorization: Bearer <token>
```

---

## Reputation

Reputation is a 5-dimension score that decays over time. All dimensions are independently tracked.

### Dimensions

| Dimension | Description |
|-----------|-------------|
| `reliability_score` | Shows up when they say they will |
| `safety_score` | No reports, no violations |
| `response_score` | Responds to matches and messages |
| `meetup_completion_score` | Completes confirmed meetups |
| `consent_confirmation_score` | Always gets proper consent |

`composite_score` = weighted average of all five dimensions.

---

### Get My Reputation

```http
GET /v1/reputation/me
Authorization: Bearer <token>
```

**Response:** `ReputationResponse`
```json
{
  "user_id": "uuid",
  "reliability_score": 0.92,
  "safety_score": 1.0,
  "response_score": 0.85,
  "meetup_completion_score": 0.88,
  "consent_confirmation_score": 0.97,
  "composite_score": 0.92,
  "no_show_rate": 0.05,
  "total_meetups": 12,
  "total_messages": 47,
  "reports_received": 0,
  "stakes_slashed": 0,
  "updated_at": "2026-05-06T12:00:00Z"
}
```

---

### Get Persona Reputation

```http
GET /v1/reputation/persona/{persona_id}
Authorization: Bearer <token>
```

---

### Submit Feedback

```http
POST /v1/reputation/feedback
Authorization: Bearer <token>
Content-Type: application/json

{
  "target_user_id": "uuid",
  "reference_id": "uuid",
  "event_type": "meetup_completed",
  "notes": "Showed up on time, great conversation."
}
```

**`event_type` values:** `meetup_completed`, `no_show`, `harassment`, `fake_profile`, `great_interaction`, `late_response`

---

### Update Reputation from Attestation

Called automatically after attestation confirmation but can be triggered manually:

```http
POST /v1/reputation/attestation-score?attestation_id={uuid}
Authorization: Bearer <token>
```

---

## Safety

### File a Safety Report

```http
POST /v1/safety/report
Authorization: Bearer <token>
Content-Type: application/json

{
  "reported_user_id": "uuid",
  "report_type": "harassment",
  "description": "Sent unsolicited explicit content after I rejected their match request.",
  "evidence_urls": ["https://storage.example.com/screenshot1.jpg"]
}
```

**`report_type` values:** `harassment`, `fake_profile`, `no_show`, `inappropriate_content`, `scam`, `other`

**Response:** `ReportResponse` — id, reporter_id, reported_user_id, report_type, status, is_repeat_offender, created_at, resolved_at

Repeat offenders (3+ reports) are flagged automatically and face escalated slash amounts.

---

### Block a User

```http
POST /v1/safety/block
Authorization: Bearer <token>
Content-Type: application/json

{
  "blocked_user_id": "uuid"
}
```

Blocked users cannot see your persona or send you match requests.

---

### Get Reports Against Me

```http
GET /v1/safety/reports
Authorization: Bearer <token>
```

---

### Resolve a Report

```http
POST /v1/safety/reports/{report_id}/resolve
Authorization: Bearer <token>
Content-Type: application/json

{
  "resolution_notes": "Verified report. User warned. Stake slashed 50%.",
  "action_taken": "stake_slashed"
}
```

---

## AI Matchmaking

AI matchmaking uses 768-dimensional BAAI/bge-base-en-v1.5 embeddings stored in ZeroDB for cosine similarity matching. Intros are generated by llama-3.3-70b.

### Update Preferences

```http
POST /v1/ai/match-agent/preferences
Authorization: Bearer <token>
Content-Type: application/json

{
  "intent_mode": "networking",
  "age_range": [25, 40],
  "interests": ["monad", "defi", "zk-proofs", "rust"],
  "dealbreakers": ["no-shows", "passive investors"],
  "location_range_km": 25,
  "personality_traits": ["builder", "introvert", "night-owl"],
  "extra": {
    "open_to_remote": true,
    "preferred_meetup_type": "coffee"
  }
}
```

Preferences are embedded and stored in ZeroDB. Updated on every call.

---

### Get Match Suggestions

```http
GET /v1/ai/match-agent/suggestions?room_id={uuid}&limit=10
Authorization: Bearer <token>
```

**Response:** `List[MatchSuggestion]`
```json
[
  {
    "persona_id": "uuid",
    "compatibility_score": 0.93,
    "intro_suggestion": "You both care deeply about Monad DeFi and zero-knowledge proofs. They've built 3 dApps in the last year.",
    "shared_interests": ["monad", "defi", "zk-proofs"],
    "room_context": "Both attending Consensus Miami 2026 Builder Lounge"
  }
]
```

---

### Generate Intro Message

Generates a personalized intro using llama-3.3-70b based on both users' profiles.

```http
POST /v1/ai/match-agent/intro
Authorization: Bearer <token>
Content-Type: application/json

{
  "target_persona_id": "uuid",
  "context": "We're both at the Consensus Miami 2026 Builder Lounge."
}
```

**Response:** Plain text intro message.

---

### Apply Vibe Filter

Filter the suggestion pool by reputation and intent:

```http
POST /v1/ai/match-agent/filter
Authorization: Bearer <token>
Content-Type: application/json

{
  "min_reputation_score": 0.75,
  "required_intent_mode": "networking",
  "max_no_show_rate": 0.10
}
```

---

## Moment NFTs

After a confirmed meetup (both parties GPS-verified), either party can mint a Moment NFT on Monad as a commemorative proof of connection.

### Mint a Moment NFT

```http
POST /v1/nfts/mint-moment
Authorization: Bearer <token>
Content-Type: application/json

{
  "attestation_id": "uuid",
  "name": "Coffee at Consensus Miami 2026",
  "description": "Met at the Builder Lounge. Built something together."
}
```

Requires `attestation_id` to reference a `confirmed` attestation. Non-confirmed attestations will return `422`.

**Response:** `MomentNFTResponse`
```json
{
  "id": "uuid",
  "owner_id": "uuid",
  "attestation_id": "uuid",
  "mint_address": "4xKXtg...",
  "metadata_uri": "https://arweave.net/...",
  "name": "Coffee at Consensus Miami 2026",
  "description": "Met at the Builder Lounge. Built something together.",
  "status": "minted",
  "created_at": "2026-05-06T12:00:00Z",
  "updated_at": "2026-05-06T12:01:00Z"
}
```

---

### List My Moment NFTs

```http
GET /v1/nfts/moments?limit=20&offset=0
Authorization: Bearer <token>
```

**Response:** `MomentNFTListResponse` — items, total, limit, offset

---

## MON Transfers

Send MON directly to any user as a gift or tip.

### Create Transfer

```http
POST /v1/transfers
Authorization: Bearer <token>
Content-Type: application/json

{
  "recipient_wallet": "0x9C8fF314C9Bc7F6e59A9d9225Fb22946427eDC03",
  "amount_mon": 0.01,
  "message": "Thanks for the alpha!"
}
```

**Response:** `TransferResponse`
```json
{
  "id": "uuid",
  "sender_id": "uuid",
  "recipient_id": "uuid",
  "amount_mon": 0.01,
  "tx_hash": "0x4f3a91c7...",
  "message": "Thanks for the alpha!",
  "status": "confirmed",
  "created_at": "2026-05-06T12:00:00Z"
}
```

---

## Error Codes

| HTTP | Code | Description |
|------|------|-------------|
| 400 | `INVALID_SIGNATURE` | Wallet signature verification failed |
| 400 | `NONCE_EXPIRED` | Challenge nonce expired (>5 min) |
| 400 | `INSUFFICIENT_STAKE` | Stake amount below required minimum |
| 400 | `STAKE_INACTIVE` | Referenced stake is not in `active` status |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| 403 | `FORBIDDEN` | Token valid but not authorized for this resource |
| 404 | `NOT_FOUND` | Resource does not exist |
| 409 | `DUPLICATE_MATCH` | Match request already exists for this pair |
| 409 | `ALREADY_MEMBER` | Persona is already a member of this room |
| 422 | `ATTESTATION_NOT_CONFIRMED` | NFT mint requires a confirmed attestation |
| 422 | `VALIDATION_ERROR` | Request body failed schema validation |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error — contact support |

All error responses follow this schema:
```json
{
  "detail": {
    "code": "INVALID_SIGNATURE",
    "message": "EIP-191 signature verification failed for wallet 0x9C8f..."
  }
}
```

---

## Rate Limits

| Tier | Requests/min | Burst |
|------|-------------|-------|
| Unauthenticated | 20 | 5 |
| Authenticated | 120 | 30 |
| AI endpoints (`/v1/ai/*`) | 30 | 10 |

Rate limit headers are returned on every response:
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 117
X-RateLimit-Reset: 1746532860
```

---

## SDK

The Monad Mate primitives are available as standalone open-source Python packages:

```bash
pip install monadmate-stake-sdk    # Stake-gated access control
pip install monadmate-reputation   # 5-dim reputation engine + HCS anchoring
pip install monadmate-x402         # FastAPI x402 MON payment middleware
```

GitHub: https://github.com/HankGrimm/monad-mate-trust-api  
License: MIT
