# Monad Mate — Trust-Based Social App on Monad

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-324%20passing-brightgreen)](backend/tests/)
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen)](backend/)
[![Deployed](https://img.shields.io/badge/API-live%20on%20Railway-blue)](https://monad-mate-trust-api-production.up.railway.app/health)

> **Submission description (≤300 chars):** Monad Mate — stake MON to DM, match, and meet. No-shows and harassment get slashed on Monad. AI matchmaking, GPS attestation, HCS audit trail, and Coinbase x402 payments. Skin in the game replaces swipe culture.

**Monad Mate is a stake-to-interact social app where skin-in-the-game replaces swipe culture.**

Users stake MON to enter rooms, request matches, and unlock DMs. Genuine meetups release the stake back. No-shows and harassment get slashed. An AI match agent surfaces compatible people. Every safety decision is anchored on Hedera HCS for immutable auditability.


---

## The Problem

Dating and social apps have zero cost for bad behavior — ghosting, harassment, and fake profiles are free. Reputation scores are siloed and forgettable. There's no skin in the game.

## The Solution

Monad Mate introduces **economic accountability** into social interactions:

- **Stake to interact** — put up MON to enter a room or DM someone. It comes back if you show up.
- **Slash bad actors** — no-shows lose 50%, harassment loses 100% of their stake.
- **AI matchmaking** — vector-based compatibility scoring finds real chemistry, not just swipes.
- **Meetup attestation** — both parties confirm the meeting via GPS or QR code, triggering stake release and reputation boost.
- **Immutable audit trail** — every safety action is anchored on Hedera HCS.

---

## Features

### Wallet Identity
- Monad EIP-191 wallet auth — challenge/nonce → signature verification (supports MetaMask, Rabby)
- JWT session tokens
- Verification levels: wallet → phone → ID → full KYC
- Privacy modes: public / semi-private / private

### Personas
- Multiple personas per wallet (anonymous or named)
- Intent modes: `social`, `dating`, `networking`, `friendship`
- Room-scoped — persona is attached to a specific room

### Rooms
- Types: `lounge`, `topic`, `event`, `private`
- Stake-gated entry: rooms can require MON stake to join
- Location-aware: GPS coordinates + haversine distance discovery
- Intent-mode filtering: only see rooms that match your vibe

### Stake-to-Interact
- Stake MON on-chain (Monad Solidity contract) to enter a room or initiate a match
- Escrow held in a contract-held vault keyed by `(staker, room_id)`
- Three stake types: `room_entry`, `match_request`, `dm_unlock`
- Auto-slash: Celery worker evaluates no-shows hourly

### Safety Escrow (Slashing Policy)
| Violation | Slash % |
|-----------|---------|
| No-show (1st) | 50% |
| No-show (repeat) | 100% |
| Harassment confirmed | 100% |
| False report filed | 25% (reporter slashed) |

- Repeat no-shows (3+) → DM sending suspended
- Stake multiplier: each no-show increases required stake by 0.5×, max 3×

### AI Match Agent (Powered by AINative Studio)

Monad Mate uses [AINative Studio's](https://ainative.studio) hosted LLM and vector API — no separate OpenAI or Anthropic accounts needed. The `AINATIVE_API_KEY` env var unlocks real AI; everything gracefully falls back to pure-Python when unset.

| Capability | AINative Endpoint | Fallback |
|-----------|------------------|---------|
| 768-dim preference embeddings | `POST /zerodb/embed` (BAAI/bge, 16ms) | Bag-of-words (45-term vocab, L2-norm) |
| Semantic profile search | `POST /zerodb/vectors/search` | In-memory cosine similarity |
| Personalized match intros | Chat completions (`claude-sonnet-4-5`) | Template string |
| Message moderation | Chat completions (`llama-3.3-8b-instruct`) | Always `{"safe": true}` |

- **5-dimension compatibility scoring:**

| Dimension | Weight |
|-----------|--------|
| Preference similarity | 35% |
| Intent mode match | 20% |
| Reputation trust score | 20% |
| Room context match | 15% |
| Behavioral safety score | 10% |

- **Vibe filter** — exclude reported users, filter by intent mode
- **AI intro generator** — LLM-generated personalized opening message based on shared interests and intent mode
- **Content moderation** — every outgoing DM scored before delivery; flagged messages blocked pre-send

### Meetup Attestations
- Both parties submit GPS coordinates after meeting
- Proximity verified within 100m (haversine)
- Alternative: BLE token (2-min TTL) or QR code (5-min TTL)
- Confirmed attestation → stake refunded + reputation boosted
- Anchored on Hedera HCS for immutable proof

### Reputation Engine
- 5 dimensions: reliability, safety, response rate, meetup completion, consent confirmation
- Composite score with weighted formula
- Time-based decay: −1 pt/week per dimension for inactivity
- Event-driven updates: meetup completed (+5), no-show (−15), report received (−10), stake slashed (−20)

### Safety & Moderation
- Report categories: harassment, fake profile, underage, spam, no-show, scam
- Auto-actions: underage reports → immediate account deactivation
- Repeat offender detection (3+ reports)
- Bidirectional block system
- Moderation queue with severity levels
- All resolved reports update the offender's reputation

### Matching & Messaging
- Consent-gated: both parties must accept before messages flow
- Stake-gated: DM channel requires active stake
- Match states: `pending` → `accepted` → `active` → `completed` / `expired`
- Interaction policy enforcement: block checks, persona-in-room checks

---

## Architecture

```
backend/app/
  api/          ← FastAPI route handlers (rooms, matches, stakes, safety, reputation…)
  models/       ← SQLAlchemy ORM (User, Persona, Room, Stake, Match, Message, Attestation…)
  schemas/      ← Pydantic v2 request/response schemas
  services/     ← Business logic (27 service classes)
  core/         ← Config, JWT auth, DB pool, domain errors
  tasks/        ← Celery workers (escrow auto-slash, match expiry, reputation decay)

contracts/
  src/MonadMateEscrow.sol     ← Escrow contract (stake/refund/slash)
  src/MonadMateEventLog.sol   ← On-chain stake/refund/slash record log
  test/                       ← Foundry (Solidity) tests
  scripts/deploy_testnet.sh   ← One-command Monad testnet deploy
```

**Infrastructure primitives** (via Agent-402):
- **Monad escrow** — on-chain stake funding and release (native MON)
- **Hedera HCS** — immutable audit log for attestations and safety decisions
- **ZeroDB** — vector memory for AI preference matching
- **X402** — HTTP payment protocol for stake transactions

### Celery Background Workers

Three worker queues run independently of the API process:

| Task file | Schedule | What it does |
|-----------|----------|-------------|
| `tasks/escrow_tasks.py` | Every 1 hour | Evaluates pending stakes: refund confirmed meetups, slash no-shows (50% first, 100% repeat), update reputation |
| `tasks/match_tasks.py` | Every 15 min | Expires unaccepted match requests after TTL, sends AI-generated intro for new matches |
| `tasks/reputation_tasks.py` | Every 24 hours | Applies time-decay: −1pt/week per dimension for inactive users |

Start the worker + beat scheduler:
```bash
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info
```

### Escrow Contract Architecture

`MonadMateEscrow` stores stake funds in a vault mapping keyed by:

```
Vault key: keccak256("stake_vault", staker, roomId)
```

This means each (user, room) pair has its own on-chain vault. The contract exposes three entry points:

| Function | Authority | Effect |
|-------------|-----------|--------|
| `stake()` | Staker | Send native MON into the escrow vault (`payable`) |
| `refund()` | `admin` (API) | Release full stake back to staker |
| `slash()` | `admin` (API) | Transfer slash % to safety fund, remainder to staker |

Alongside it, `MonadMateEventLog` records every stake/refund/slash decision as an
indexed event. The API writes to it from `monad_service.py` via web3.py, so each
call produces an explorer-visible transaction hash.

### Preference Embedding Algorithm

The AI match agent uses a pure-Python bag-of-words embedding (zero numpy dependency):

1. **Vocabulary**: 45 curated terms across interest categories (tech, arts, sports, lifestyle, values)
2. **Encoding**: Each preference list → binary vector of length 45
3. **Normalisation**: L2-norm (unit vector) to eliminate length bias
4. **Similarity**: Dot product of two unit vectors = cosine similarity
5. **Score range**: 0.0–1.0, where 1.0 = identical preferences

This runs in microseconds with no external dependencies and no model download required. See `services/preference_memory_service.py`.

### Persona Visibility Scopes

Each persona has a `visibility` field controlling discoverability:

| Scope | Discoverability | Use Case |
|-------|----------------|----------|
| `public` | Visible in room lists and match recommendations globally | Default for networking/social |
| `semi_private` | Visible only within the room they're attached to | Default for dating |
| `private` | Never appears in recommendations; only direct-link access | High-privacy mode |

Persona visibility is enforced at the query layer in `room_discovery_service.py` and `matchmaking_service.py`.

### Block System

`sm_blocks` table stores bidirectional block relationships. Enforcement happens at multiple layers:

- **Room discovery**: blocked users never appear in room listings
- **Match requests**: blocked users cannot initiate or receive match requests
- **Messaging**: messages from blocked users are rejected at the API layer
- **Match agent**: vibe filter excludes blocked users from all recommendations

The `interaction_policy_service.py` centralises these checks so each endpoint doesn't need to reimplement block logic.

---

## Landing Page

The `landing/` directory contains a Next.js landing page with:
- Hero section with animated phone mockup
- How-it-works 6-step flow
- Feature grid (8 capabilities)
- Tech stack overview
- Web dApp / PWA download CTAs
- Open source section with planned packages

```bash
cd landing
npm install
npm run dev   # http://localhost:3000
npm run build # static export to landing/out/
```

PWA manifest at `landing/public/manifest.json` — Monad Mate is installable as an app via "Add to Home Screen" on any mobile browser.

For distribution steps (PWA install + APK sideload), see `docs/deployment/DISTRIBUTION.md`.

---

## Quick Start

```bash
# Clone and configure
git clone https://github.com/HankGrimm/monad-mate-trust-api
cd monad-mate-trust-api
cp .env.example .env  # fill in DATABASE_URL, SECRET_KEY, MONAD_RPC_URL

# Install and run
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# → API docs at http://localhost:8000/docs
```

### Docker (full stack)

```bash
cd backend
docker-compose up
# Starts: API, Postgres, Redis, Celery worker, Celery beat
```

### Run Demo Seed

```bash
python3 scripts/demo_seed.py --base-url http://localhost:8000
# Seeds 4 users, 3 rooms, a match, messages, attestation, and a harassment report
```

---

## Monad Contracts — Not Yet Deployed

The escrow and event-log contracts live in `contracts/` and are ready to deploy to
Monad testnet (chain id `10143`). No address is published yet — deploy them and copy
the printed addresses into `.env`:

```bash
cd contracts
forge install foundry-rs/forge-std
forge test
export MONAD_RPC_URL=https://testnet-rpc.monad.xyz
export MONAD_DEPLOYER_KEY=0x...
bash scripts/deploy_testnet.sh
```

Once `MONAD_EVENT_LOG_ADDRESS` is set, every stake, refund, and slash from the API
submits a transaction and returns a hash viewable on https://testnet.monadexplorer.com.

---

## What We Built vs. What We Built On

### Built on Agent402 / infrastructure primitives

Monad Mate integrates several infrastructure layers through the Agent402 / AINative ecosystem rather than rebuilding them:

| Primitive | Provider | How we use it |
|-----------|---------|--------------|
| On-chain stake escrow | **MonadMateEscrow** (native MON) | Fund, hold, release, and slash stakes on Monad |
| Immutable audit trail | **Hedera HCS** (via Agent402) | Anchor every attestation and safety decision on-chain |
| LLM inference | **AINative Studio API** | `claude-sonnet-4-5` intro generation, `llama-3.3-8b` message moderation |
| Vector embeddings | **AINative ZeroDB** | 768-dim BAAI/bge embeddings at 16ms; semantic cross-user search |
| On-chain payments | **Coinbase x402** (Base) | HTTP 402 payment gate for DM unlock staking |

### Built uniquely for Monad Mate

Everything below was designed and built from scratch for this project:

| Component | Location | What's unique |
|-----------|---------|--------------|
| **Stake-to-interact protocol** | `backend/app/services/stake_service.py` | 5 stake types, no-show multiplier (0.5× per offense, 3× cap), automated Celery slash evaluation |
| **Solidity escrow contract** | `contracts/src/MonadMateEscrow.sol` | mapping-keyed vault per `(staker, room_id)`, slash splits to safety fund |
| **5-dimension reputation engine** | `backend/app/services/social_reputation_service.py` | Weighted composite (reliability 30%, safety 30%, response 15%, meetup 15%, consent 10%), event-driven updates |
| **Proximity attestation** | `backend/app/services/attestation_service.py` | GPS haversine (100m threshold) + BLE token + QR fallback; both parties must confirm |
| **Intent-mode room scoping** | `backend/app/services/room_discovery_service.py` | Rooms and personas scope-matched by intent (social / dating / networking / friendship) |
| **Persona system** | `backend/app/models/persona.py` | Multiple personas per wallet, visibility scopes (public / semi-private / private), room-scoped personas |
| **Consent-gated messaging** | `backend/app/services/match_service.py` + `message_service.py` | Both parties must accept before any messages flow; stake must be active |
| **AI matchmaking service** | `backend/app/services/ainative_service.py` | AINative gateway integration with graceful bag-of-words fallback; ZeroDB vector sync |
| **Repeat-offender detection** | `backend/app/services/safety_service.py` | 3+ reports → automatic suspension, stake multiplier escalation, HCS anchor |

---

## Open Source Strategy — Three Packages, Live Now

Monad Mate's three core primitives have been extracted as standalone, dependency-injection-friendly PyPI packages. Each works without any external service configured (graceful no-ops throughout).

| Package | Install | What it does |
|---------|---------|-------------|
| **[`monadmate-stake-sdk`](packages/monadmate-stake-sdk/)** | `pip install monadmate-stake-sdk` | Stake-gated access control — `StakeGate`, `StakeRecord`, `SlashingPolicy`. Any Monad dApp can require MON before a DM, room entry, or action. No-show multiplier built in. |
| **[`monadmate-reputation`](packages/monadmate-reputation/)** | `pip install monadmate-reputation` | 5-dimension portable reputation scoring with time-based decay and Hedera HCS anchoring. Framework-agnostic — bring your own storage. |
| **[`x402-monad`](packages/x402-monad/)** | `pip install x402-monad` | FastAPI middleware for Coinbase x402 HTTP payments on Base. Drop-in `require_x402_payment()` dependency for any endpoint. |

All three are MIT licensed and located in `packages/`. They don't depend on each other — use one, two, or all three.

```bash
# Quick example: add stake-gating to your app in 5 lines
from monadmate_stake_sdk import StakeGate, StakeType

gate = StakeGate()
ok, error = gate.validate(StakeType.DM, amount_mon=0.50, no_show_count=0)
record = gate.create_stake(user_id="0xABC", stake_type=StakeType.DM, amount_mon=0.50)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved.

---

## Tests

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

**324 tests, 94% coverage.**

| Area | Tests | Coverage |
|------|-------|----------|
| Models & Schemas | — | 100% |
| User / Wallet Auth | 25 | 81% |
| Rooms | 9 | 97% |
| Stakes & Escrow | 19 | 93% |
| Matching & Messaging | 15 | 85% |
| Attestations & Reputation | 10 | 85% |
| AI Match Agent | 8 | 91% |
| Safety & Moderation | 23 | 100% |
| Proximity Verification | 16 | 100% |
| Room Discovery | 14 | 97% |
| Preference Memory | 16 | 97% |
| Reputation Decay | 14 | 100% |
| Infra / Health | 11 | 96% |

---

## Integrations

### Coinbase x402 — HTTP Payment Protocol (Base)

Monad Mate implements the [x402 HTTP payment protocol](https://x402.org) on Base mainnet for DM unlock staking.

**How it works:**

```
Client → POST /api/v1/stakes (stake_type=dm, no payment)
Server → 402 Payment Required + payment requirements (Base MON)
Client → pays 0.5 USDC on Base via Coinbase facilitator
Client → POST /api/v1/stakes (X-Payment: <proof>)
Server → verifies proof via https://x402.org/facilitator/verify
Server → 201 Created (stake unlocked)
```

**Payment details:**
- Network: Base mainnet
- Asset: MON (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- Amount: 0.5 USDC (500,000 micro-units, 6 decimals)
- Facilitator: Coinbase public facilitator (`https://x402.org/facilitator`)

**Enable in `.env`:**

```env
X402_ENABLED=true
COINBASE_PAYMENT_ADDRESS=0xYourBaseWalletAddress
```

**Disabled by default** — all existing tests pass without any x402 configuration. When the facilitator is unreachable, requests are allowed through (graceful degradation).

**Implementation:**
- Middleware: `backend/app/middleware/x402_payment.py`
- Dependency: `require_x402_payment` (called inline for `stake_type=dm` only)
- Package: `x402[fastapi]==2.9.0`

---

## Running Locally — API Keys Setup

Monad Mate is designed to run without external API keys in development. All third-party integrations (Hedera, ZeroDB) **gracefully no-op** when credentials are missing — the API still starts and all tests pass.

### Minimum setup (no external services)

```bash
cp .env.example .env
```

Edit `.env` with just these two required values:

```env
# Required — always
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/monadmate
SECRET_KEY=any-random-string-at-least-32-chars

# Optional — app starts fine without these
```

That's it. Wallet auth, rooms, matching, AI scoring, and all 198 tests work without any third-party keys.

---

### Optional integrations

Each integration below adds a real capability. Skip any you don't need.

#### Monad (on-chain stake/escrow)
Add Monad testnet to your wallet and fund it from the faucet: https://faucet.monad.xyz

```env
MONAD_RPC_URL=https://testnet-rpc.monad.xyz
MONAD_CHAIN_ID=10143
MONAD_ESCROW_ADDRESS=<from: cd contracts && bash scripts/deploy_testnet.sh>
MONAD_EVENT_LOG_ADDRESS=<from the same deploy output>
MONAD_PRIVATE_KEY=<backend authority key — only this key can refund/slash>
```

#### Hedera HCS (immutable audit trail)
Sign up at https://portal.hedera.com — testnet accounts are free.

```env
HEDERA_ACCOUNT_ID=0.0.XXXXXX
HEDERA_PRIVATE_KEY=302e...               # ED25519 private key from portal
HEDERA_TOPIC_ID=0.0.XXXXXX              # create via: hedera topic create
HEDERA_NETWORK=testnet                  # or "mainnet"
```

> Without these, attestation anchoring and safety audit calls are silently skipped. The `hcs_message_id` field stays null on attestations.

#### ZeroDB (vector memory for AI matching)
Get a free API key at https://ainative.studio

```env
ZERODB_API_KEY=<your-key>
ZERODB_PROJECT_ID=<your-project-id>
ZERODB_API_URL=https://api.ainative.studio  # default
```

> Without these, preference embeddings are stored only in Postgres (the built-in bag-of-words scoring still works). Semantic search across all users won't be available.

#### OpenAI (enhanced intro generation)
```env
OPENAI_API_KEY=sk-...
```

> Without this, the AI intro generator uses the built-in template engine.

---

### Full `.env` reference

```env
# ── Required ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/monadmate
SECRET_KEY=change-me-to-a-long-random-secret

# ── Monad ────────────────────────────────────────────────────────────────────
MONAD_RPC_URL=https://testnet-rpc.monad.xyz
MONAD_CHAIN_ID=10143
MONAD_ESCROW_ADDRESS=
MONAD_EVENT_LOG_ADDRESS=
MONAD_PRIVATE_KEY=

# ── Hedera HCS ────────────────────────────────────────────────────────────────
HEDERA_ACCOUNT_ID=
HEDERA_PRIVATE_KEY=
HEDERA_TOPIC_ID=
HEDERA_NETWORK=testnet

# ── ZeroDB ────────────────────────────────────────────────────────────────────
ZERODB_API_KEY=
ZERODB_PROJECT_ID=
ZERODB_API_URL=https://api.ainative.studio

# ── OpenAI (optional) ─────────────────────────────────────────────────────────
OPENAI_API_KEY=

# ── Stake thresholds (MON) ───────────────────────────────────────────────────
MIN_STAKE_ROOM_MON=1.0
MIN_STAKE_MEETUP_MON=2.0
MIN_STAKE_DM_MON=0.5

# ── Celery / Redis (for background workers) ───────────────────────────────────
REDIS_URL=redis://localhost:6379/0
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | **Yes** | Postgres connection string |
| `SECRET_KEY` | **Yes** | JWT signing secret (32+ chars) |
| `MONAD_RPC_URL` | No | Monad RPC endpoint (default: `https://testnet-rpc.monad.xyz`) |
| `MONAD_CHAIN_ID` | No | Monad chain id (default: `10143`, testnet) |
| `MONAD_ESCROW_ADDRESS` | No | Deployed `MonadMateEscrow` address |
| `MONAD_EVENT_LOG_ADDRESS` | No | Deployed `MonadMateEventLog` address |
| `MONAD_PRIVATE_KEY` | No | Backend authority key for refund/slash and event-log writes |
| `HEDERA_ACCOUNT_ID` | No | Hedera operator account (e.g. `0.0.12345`) |
| `HEDERA_PRIVATE_KEY` | No | Hedera ED25519 private key |
| `HEDERA_TOPIC_ID` | No | HCS topic ID for audit logs |
| `HEDERA_NETWORK` | No | `testnet` or `mainnet` (default: testnet) |
| `ZERODB_API_KEY` | No | ZeroDB vector memory API key |
| `ZERODB_PROJECT_ID` | No | ZeroDB project identifier |
| `ZERODB_API_URL` | No | ZeroDB base URL (default: `https://api.ainative.studio`) |
| `OPENAI_API_KEY` | No | OpenAI key for enhanced intro generation |
| `REDIS_URL` | No | Redis URL for Celery workers (default: `redis://localhost:6379/0`) |
| `MIN_STAKE_ROOM_MON` | No | Min MON stake for room entry (default: 1.0) |
| `MIN_STAKE_MEETUP_MON` | No | Min MON stake for meetup request (default: 2.0) |
| `MIN_STAKE_DM_MON` | No | Min MON stake to unlock DMs (default: 0.5) |
| `X402_ENABLED` | No | Enable Coinbase x402 payment gate on DM unlock (default: false) |
| `COINBASE_PAYMENT_ADDRESS` | No | Base wallet address to receive x402 USDC payments |

