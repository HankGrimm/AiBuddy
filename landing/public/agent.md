# Monad Mate — Machine-Readable Agent Guide

## Overview

Monad Mate is a trust-based social dApp on Monad. Stake MON to DM, match, and meet. No-shows get slashed. AI matchmaking powered by AINative.

## Core APIs

**Authentication** — Wallet signature challenge flow → JWT bearer token

**Stakes** — Create MON stakes for DMs, room entry, or meetups

**Matching** — AI-powered match requests with generated intro messages

**Messaging** — Stake-gated DMs between matched users

**Attestations** — GPS-verified meetup confirmation

**Transfers** — Gift MON to another user

**Moment NFTs** — Mint commemorative NFTs for confirmed meetups

## API Base
```
https://monad-mate-trust-api-production.up.railway.app
```

## Authentication
JWT via wallet signature. Challenge-response flow.
Header: `Authorization: Bearer <token>`

## Key Endpoints
```
POST /api/v1/auth/wallet/connect   Wallet auth
GET  /api/v1/rooms                 Discover rooms
POST /api/v1/stakes                Create stake
POST /api/v1/matches               Request match
POST /api/v1/messages              Send message
POST /api/v1/attestations          Submit attestation
POST /api/v1/transfers             Gift MON
POST /api/v1/nfts/mint-moment      Mint Moment NFT
GET  /api/v1/nfts/moments          List Moment NFTs
```

## SDKs
```bash
pip install monadmate-stake-sdk
pip install monadmate-reputation
pip install monadmate-x402
```

## Full details: /llms-full.txt
