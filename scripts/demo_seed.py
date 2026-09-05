#!/usr/bin/env python3
"""
Monad Mate Hackathon Demo Seed Script
====================================
Seeds a running Monad Mate backend with:
  - 4 users (Alice, Bob, Carol, Dan)
  - Their Monad wallet identities (secp256k1 keypairs)
  - 3 rooms (Social Lounge, Crypto Devs, Speed Dating)
  - Personas for each user
  - Stake for Bob entering the Speed Dating room
  - A match between Alice and Bob
  - Messages in the match
  - A meetup attestation (both parties confirm)
  - Reputation scores
  - A moderation report (Dan harasses Carol → slash)

Usage:
    python3 scripts/demo_seed.py [--base-url http://localhost:8000]

Prerequisites:
    pip install requests eth-account
"""

import argparse
import json
import sys
import time
import uuid
from typing import Optional

import requests

# ── Optional Monad sig generation ──────────────────────────────────────────
try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    HAS_ETH_ACCOUNT = True
except ImportError:
    HAS_ETH_ACCOUNT = False
    print("[WARN] eth-account not installed — using mock signatures (dev mode only)")

# ── Config ───────────────────────────────────────────────────────────────────
COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}


def c(color: str, msg: str) -> str:
    return f"{COLORS[color]}{msg}{COLORS['reset']}"


def ok(msg: str):
    print(f"  {c('green', '✓')} {msg}")


def warn(msg: str):
    print(f"  {c('yellow', '!')} {msg}")


def err(msg: str):
    print(f"  {c('red', '✗')} {msg}")
    sys.exit(1)


def section(title: str):
    print(f"\n{c('bold', c('cyan', '─── ' + title + ' ───'))}")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

class APIClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()

    def get(self, path: str, token: str = None, **kwargs) -> requests.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.session.get(f"{self.base}{path}", headers=headers, **kwargs)

    def post(self, path: str, data: dict = None, token: str = None, **kwargs) -> requests.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.session.post(
            f"{self.base}{path}", json=data, headers=headers, **kwargs
        )

    def require(self, resp: requests.Response, expected: int = 200, label: str = "") -> dict:
        if resp.status_code != expected:
            err(f"{label} → HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def patch(self, path: str, data: dict = None, token: str = None) -> requests.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.session.patch(f"{self.base}{path}", json=data, headers=headers)


# ── Monad wallet helpers ──────────────────────────────────────────────────

def generate_wallet():
    if HAS_ETH_ACCOUNT:
        acct = Account.create()
        return acct.address, acct
    # Fallback: random 20-byte hex address (dev only)
    import os
    addr = "0x" + os.urandom(20).hex()
    return addr, None


def sign_nonce(account, nonce: str) -> str:
    """Sign the nonce message with the wallet key (EIP-191 personal_sign)."""
    if account is None:
        return "mock_signature_" + nonce[:16]
    signed = Account.sign_message(encode_defunct(text=nonce), account.key)
    return signed.signature.hex()


# ── Demo data ─────────────────────────────────────────────────────────────────

USERS = [
    {
        "name": "Alice",
        "interests": ["DeFi", "art", "yoga"],
        "intent": "social",
    },
    {
        "name": "Bob",
        "interests": ["DeFi", "gaming", "yoga"],
        "intent": "dating",
    },
    {
        "name": "Carol",
        "interests": ["NFTs", "music", "travel"],
        "intent": "networking",
    },
    {
        "name": "Dan",
        "interests": ["trading", "sports"],
        "intent": "social",
    },
]

ROOMS = [
    {
        "name": "Social Lounge",
        "description": "Chill vibes. Meet people from EasyA Hackathon.",
        "type": "lounge",
        "privacy_level": "public",
        "stake_required": 0.0,
        "intent_modes": ["social", "networking"],
        "latitude": 25.7617,
        "longitude": -80.1918,
    },
    {
        "name": "Crypto Devs",
        "description": "Builder chat for Consensus Miami 2026 hackers.",
        "type": "lounge",
        "privacy_level": "public",
        "stake_required": 0.0,
        "intent_modes": ["networking"],
        "latitude": 25.7750,
        "longitude": -80.2000,
    },
    {
        "name": "Speed Dating 💕",
        "description": "Stake-gated speed dating. Serious connections only.",
        "type": "event",
        "privacy_level": "public",
        "stake_required": 5.0,
        "intent_modes": ["dating"],
        "latitude": 25.7617,
        "longitude": -80.1918,
    },
]


# ── Main seed flow ────────────────────────────────────────────────────────────

def seed(api: APIClient):
    tokens = {}
    user_ids = {}
    persona_ids = {}
    wallets = {}
    room_ids = {}

    # ── 1. Register users ────────────────────────────────────────────────────
    section("1. Registering Users")
    for u in USERS:
        wallet_addr, keypair = generate_wallet()
        wallets[u["name"]] = (wallet_addr, keypair)

        # Get challenge nonce
        resp = api.post(f"/v1/users/challenge?wallet_address={wallet_addr}")
        data = api.require(resp, 200, f"challenge/{u['name']}")
        nonce = data["nonce"]

        # Sign and onboard
        sig = sign_nonce(keypair, nonce)
        resp = api.post("/v1/users/onboard", {
            "wallet_address": wallet_addr,
            "nonce": nonce,
            "signature": sig,
        })
        data = api.require(resp, 200, f"onboard/{u['name']}")
        tokens[u["name"]] = data["access_token"]
        user_ids[u["name"]] = data["user"]["id"]
        ok(f"{u['name']} registered — wallet {wallet_addr[:20]}...")

    # ── 2. Create personas ───────────────────────────────────────────────────
    section("2. Creating Personas")
    for u in USERS:
        token = tokens[u["name"]]
        resp = api.post("/v1/personas", {
            "display_name": u["name"],
            "intent_mode": u["intent"],
            "bio": f"Hey, I'm {u['name']}! Into {', '.join(u['interests'][:2])}.",
        }, token=token)
        data = api.require(resp, 201, f"persona/{u['name']}")
        persona_ids[u["name"]] = data["id"]
        ok(f"{u['name']} persona created (intent: {u['intent']})")

    # ── 3. Store AI preferences ──────────────────────────────────────────────
    section("3. Storing AI Match Preferences")
    for u in USERS:
        token = tokens[u["name"]]
        resp = api.post("/v1/ai/match-agent/preferences", {
            "intent_mode": u["intent"],
            "interests": u["interests"],
            "age_range_min": 21,
            "age_range_max": 35,
            "personality_traits": ["curious", "adventurous"],
        }, token=token)
        if resp.status_code == 200:
            ok(f"{u['name']} preferences saved")
        else:
            warn(f"{u['name']} preferences returned {resp.status_code}")

    # ── 4. Create rooms ──────────────────────────────────────────────────────
    section("4. Creating Rooms")
    alice_token = tokens["Alice"]
    for room in ROOMS:
        resp = api.post("/v1/rooms", room, token=alice_token)
        data = api.require(resp, 201, f"room/{room['name']}")
        room_ids[room["name"]] = data["id"]
        ok(f"Room created: {room['name']} (stake: {room['stake_required']} MON)")

    # ── 5. Join rooms ────────────────────────────────────────────────────────
    section("5. Joining Rooms")

    # Alice and Carol join Social Lounge (no stake)
    for name in ["Alice", "Carol"]:
        resp = api.post(
            f"/v1/rooms/{room_ids['Social Lounge']}/join",
            {"persona_id": persona_ids[name]},
            token=tokens[name],
        )
        if resp.status_code == 200:
            ok(f"{name} joined Social Lounge")
        else:
            warn(f"{name} join returned {resp.status_code}")

    # Bob joins Speed Dating with stake tx hash
    resp = api.post(
        f"/v1/rooms/{room_ids['Speed Dating 💕']}/join",
        {
            "persona_id": persona_ids["Bob"],
            "stake_tx_hash": "testnet_tx_" + uuid.uuid4().hex[:16],
        },
        token=tokens["Bob"],
    )
    if resp.status_code == 200:
        ok("Bob joined Speed Dating 💕 (stake recorded)")
    else:
        warn(f"Bob join Speed Dating returned {resp.status_code}: {resp.text[:100]}")

    # Alice also joins Speed Dating
    resp = api.post(
        f"/v1/rooms/{room_ids['Speed Dating 💕']}/join",
        {
            "persona_id": persona_ids["Alice"],
            "stake_tx_hash": "testnet_tx_" + uuid.uuid4().hex[:16],
        },
        token=tokens["Alice"],
    )
    if resp.status_code == 200:
        ok("Alice joined Speed Dating 💕 (stake recorded)")
    else:
        warn(f"Alice join Speed Dating returned {resp.status_code}: {resp.text[:100]}")

    # ── 6. Get AI suggestions for Bob ────────────────────────────────────────
    section("6. AI Match Suggestions (Bob)")
    resp = api.get(
        f"/v1/ai/match-agent/suggestions?room_id={room_ids['Speed Dating 💕']}",
        token=tokens["Bob"],
    )
    if resp.status_code == 200:
        suggestions = resp.json()
        ok(f"AI returned {len(suggestions)} suggestion(s) for Bob")
        for s in suggestions[:3]:
            print(f"     persona {s['persona_id'][:8]}… score={s['compatibility_score']:.2f}")
    else:
        warn(f"Suggestions returned {resp.status_code}")

    # ── 7. Create a match (Alice requests Bob) ───────────────────────────────
    section("7. Creating Match: Alice → Bob")
    resp = api.post("/v1/matches/request", {
        "initiator_persona_id": persona_ids["Alice"],
        "target_persona_id": persona_ids["Bob"],
        "room_id": room_ids["Speed Dating 💕"],
    }, token=tokens["Alice"])
    match_id = None
    if resp.status_code == 201:
        match_id = resp.json()["id"]
        ok(f"Match created: {match_id[:8]}…")
    else:
        warn(f"Match create returned {resp.status_code}: {resp.text[:100]}")

    # Bob accepts
    if match_id:
        resp = api.post(f"/v1/matches/{match_id}/accept", token=tokens["Bob"])
        if resp.status_code == 200:
            ok("Bob accepted the match")
        else:
            warn(f"Match accept returned {resp.status_code}: {resp.text[:100]}")

    # ── 8. Message exchange ──────────────────────────────────────────────────
    section("8. Messaging")
    if match_id:
        msgs = [
            ("Alice", "Hey Bob! Loved your DeFi talk earlier 👋"),
            ("Bob", "Alice! You were at the workshop? Small world! Let's grab coffee ☕"),
            ("Alice", "Absolutely. Café Versailles in 30?"),
            ("Bob", "I'll be there!"),
        ]
        for sender, text in msgs:
            resp = api.post("/v1/messages", {
                "match_id": match_id,
                "content": text,
            }, token=tokens[sender])
            if resp.status_code == 201:
                ok(f"{sender}: \"{text[:50]}\"")
            else:
                warn(f"Message from {sender} returned {resp.status_code}")

    # ── 9. Meetup attestation ────────────────────────────────────────────────
    section("9. Meetup Attestation")
    if match_id:
        # Alice attests
        resp = api.post("/v1/attestations/meetup/initiate", {
            "match_id": match_id,
            "method": "gps_checkin",
            "latitude": 25.7617,
            "longitude": -80.1918,
        }, token=tokens["Alice"])
        attestation_id = None
        if resp.status_code == 201:
            attestation_id = resp.json().get("id")
            ok("Alice attested meetup (GPS verified)")
        else:
            warn(f"Alice attestation returned {resp.status_code}: {resp.text[:100]}")

        # Bob attests
        resp = api.post("/v1/attestations/meetup/initiate", {
            "match_id": match_id,
            "method": "gps_checkin",
            "latitude": 25.7618,
            "longitude": -80.1917,
        }, token=tokens["Bob"])
        if resp.status_code == 201:
            ok("Bob attested meetup (GPS verified)")
            ok("Both parties confirmed → stakes refunded, reputation boosted")
        else:
            warn(f"Bob attestation returned {resp.status_code}: {resp.text[:100]}")

    # ── 10. Safety: Dan harasses Carol ───────────────────────────────────────
    section("10. Safety & Moderation (Dan → Carol report)")

    # Dan joins Social Lounge
    resp = api.post(
        f"/v1/rooms/{room_ids['Social Lounge']}/join",
        {"persona_id": persona_ids["Dan"]},
        token=tokens["Dan"],
    )
    if resp.status_code == 200:
        ok("Dan joined Social Lounge")

    # Carol files harassment report
    resp = api.post("/v1/safety/report", {
        "reported_user_id": user_ids["Dan"],
        "report_type": "harassment",
        "description": "Sent unsolicited messages after I said no. He persisted three times.",
    }, token=tokens["Carol"])
    if resp.status_code == 201:
        report_data = resp.json()
        ok(f"Carol filed harassment report → ID {report_data['id'][:8]}…")
        ok("Moderation queue updated, Dan's reputation flagged")
    else:
        warn(f"Report returned {resp.status_code}: {resp.text[:100]}")

    # ── 11. Check reputation scores ──────────────────────────────────────────
    section("11. Reputation Scores")
    for name in ["Alice", "Bob", "Carol"]:
        resp = api.get(f"/v1/reputation/persona/{persona_ids[name]}", token=tokens[name])
        if resp.status_code == 200:
            score = resp.json()
            total = score.get("trust_score", score.get("overall", "N/A"))
            ok(f"{name}: trust score = {total}")
        else:
            warn(f"Reputation for {name} returned {resp.status_code}")

    # ── 12. Room discovery ───────────────────────────────────────────────────
    section("12. Room Discovery (near Consensus Miami)")
    resp = api.get(
        "/v1/rooms/discover?lat=25.7617&lng=-80.1918&radius_km=10"
    )
    if resp.status_code == 200:
        nearby = resp.json()
        ok(f"Found {len(nearby)} room(s) within 10km of Bayside Marketplace")
        for r in nearby:
            print(f"     {r['name']} — stake: {r.get('stake_required', 0)} MON")
    else:
        warn(f"Room discover returned {resp.status_code}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{c('bold', c('green', '═══ Demo Seed Complete ═══'))}")
    print(f"  Users:     {', '.join(user_ids.keys())}")
    print(f"  Rooms:     {', '.join(room_ids.keys())}")
    print(f"  Match ID:  {match_id[:8] if match_id else 'N/A'}…")
    print(f"\n  {c('cyan', 'API Base:')} {api.base}")
    print(f"  {c('cyan', 'Docs:')}     {api.base}/docs")
    print()

    return {
        "users": user_ids,
        "personas": persona_ids,
        "rooms": room_ids,
        "tokens": tokens,
        "match_id": match_id,
    }


def main():
    parser = argparse.ArgumentParser(description="Monad Mate demo seed script")
    parser.add_argument(
        "--base-url",
        default="https://monad-mate-trust-api-production.up.railway.app",
        help="Monad Mate API base URL (default: live Railway deployment)",
    )
    parser.add_argument(
        "--output-json",
        help="Write seed results to a JSON file",
    )
    args = parser.parse_args()

    api = APIClient(args.base_url)

    # Health check
    print(c("bold", "\nMonad Mate — Hackathon Demo Seed"))
    print(f"Target: {c('cyan', args.base_url)}\n")

    resp = api.get("/health")
    if resp.status_code != 200:
        err(f"Backend not reachable at {args.base_url}/health (HTTP {resp.status_code})")
    ok("Backend healthy")

    result = seed(api)

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2, default=str)
        ok(f"Results written to {args.output_json}")


if __name__ == "__main__":
    main()
