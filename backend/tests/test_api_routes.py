"""
HTTP-layer tests for all under-covered API route handlers.
Covers: stakes, escrow, matches, messages, safety, attestations, reputation.
Uses the `client` fixture from conftest.py (FastAPI TestClient + SQLite).
"""
import uuid
import pytest

from app.core.auth import create_access_token
from app.models.user import User
from app.models.persona import Persona, IntentMode
from app.models.room import Room, RoomType, RoomPrivacyLevel
from app.models.stake import Stake, StakeStatus, StakeType
from app.models.match import Match, MatchStatus, ConsentState
from app.models.attestation import MeetupAttestation, AttestationMethod, AttestationStatus
from app.models.reputation import ReputationScore


# ── helpers ───────────────────────────────────────────────────────────────────

def _user(db) -> User:
    u = User(id=uuid.uuid4(), wallet_address=f"w_{uuid.uuid4().hex[:8]}", is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user: User) -> dict:
    token = create_access_token(str(user.id), user.wallet_address)
    return {"Authorization": f"Bearer {token}"}


def _persona(db, user: User, room: Room = None) -> Persona:
    p = Persona(
        id=uuid.uuid4(), user_id=user.id, display_name="P",
        intent_mode=IntentMode.SOCIAL, is_active=True,
        room_id=room.id if room else None,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _room(db) -> Room:
    r = Room(
        id=uuid.uuid4(), name="R", type=RoomType.LOUNGE,
        privacy_level=RoomPrivacyLevel.PUBLIC, stake_required=0.0,
        intent_modes=[], is_active=True,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _stake(db, user: User, **kwargs) -> Stake:
    s = Stake(
        id=uuid.uuid4(), user_id=user.id,
        stake_type=StakeType.JOIN_ROOM, amount_mon=2.0,
        status=StakeStatus.ACTIVE, **kwargs
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _match(db, persona_a: Persona, persona_b: Persona) -> Match:
    m = Match(
        id=uuid.uuid4(),
        requester_persona_id=persona_a.id,
        target_persona_id=persona_b.id,
        status=MatchStatus.ACCEPTED,
        consent_state=ConsentState.GRANTED,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ── Stakes ────────────────────────────────────────────────────────────────────

class TestStakesAPI:
    def test_create_stake_requires_auth(self, client):
        resp = client.post("/v1/stakes", json={
            "stake_type": "join_room", "amount_mon": 2.0,
        })
        assert resp.status_code in (401, 403)

    def test_create_stake_success(self, client, db):
        user = _user(db)
        resp = client.post("/v1/stakes", json={
            "stake_type": "join_room",
            "amount_mon": 2.0,
            "tx_hash": "testnet_tx_abc",
        }, headers=_auth(user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount_mon"] == 2.0
        assert data["status"] == "active"

    def test_list_my_stakes_empty(self, client, db):
        user = _user(db)
        resp = client.get("/v1/stakes/me", headers=_auth(user))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_my_stakes_returns_own(self, client, db):
        user = _user(db)
        _stake(db, user)
        resp = client.get("/v1/stakes/me", headers=_auth(user))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_refund_stake(self, client, db):
        user = _user(db)
        stake = _stake(db, user)
        resp = client.post(f"/v1/stakes/{stake.id}/refund", headers=_auth(user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "refunded"

    def test_refund_stake_not_found(self, client, db):
        user = _user(db)
        resp = client.post(f"/v1/stakes/{uuid.uuid4()}/refund", headers=_auth(user))
        assert resp.status_code == 404

    def test_slash_stake(self, client, db):
        user = _user(db)
        stake = _stake(db, user)
        resp = client.post(f"/v1/stakes/{stake.id}/slash", json={
            "reason": "no_show_after_confirmation"
        }, headers=_auth(user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "slashed"

    def test_slash_requires_auth(self, client, db):
        user = _user(db)
        stake = _stake(db, user)
        resp = client.post(f"/v1/stakes/{stake.id}/slash", json={"reason": "fraud"})
        assert resp.status_code in (401, 403)


# ── Escrow ────────────────────────────────────────────────────────────────────

class TestEscrowAPI:
    def test_create_meetup_escrow(self, client, db):
        user = _user(db)
        other = _user(db)
        resp = client.post("/v1/escrow/meetup", json={
            "type": "meetup",
            "counterparty_user_id": str(other.id),
            "amount_mon": 5.0,
        }, headers=_auth(user))
        assert resp.status_code == 201
        assert resp.json()["amount_mon"] == 5.0

    def test_create_escrow_requires_auth(self, client):
        resp = client.post("/v1/escrow/meetup", json={
            "counterparty_user_id": str(uuid.uuid4()),
            "amount_mon": 5.0,
        })
        assert resp.status_code in (401, 403)

    def test_confirm_escrow(self, client, db):
        from app.models.escrow import Escrow, EscrowStatus, EscrowType
        user = _user(db)
        other = _user(db)
        escrow = Escrow(
            id=uuid.uuid4(), initiator_user_id=user.id, type=EscrowType.MEETUP,
            counterparty_user_id=other.id, amount_mon=5.0,
            status=EscrowStatus.OPEN,
        )
        db.add(escrow)
        db.commit()
        resp = client.post(f"/v1/escrow/{escrow.id}/confirm", headers=_auth(user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

    def test_dispute_escrow(self, client, db):
        from app.models.escrow import Escrow, EscrowStatus, EscrowType
        user = _user(db)
        other = _user(db)
        escrow = Escrow(
            id=uuid.uuid4(), initiator_user_id=user.id, type=EscrowType.MEETUP,
            counterparty_user_id=other.id, amount_mon=5.0,
            status=EscrowStatus.OPEN,
        )
        db.add(escrow)
        db.commit()
        resp = client.post(f"/v1/escrow/{escrow.id}/dispute",
                           json={"reason": "other party did not show up at the agreed location"},
                           headers=_auth(user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "disputed"


# ── Matches ───────────────────────────────────────────────────────────────────

class TestMatchesAPI:
    def test_request_match_requires_auth(self, client):
        resp = client.post("/v1/matches/request", json={
            "target_persona_id": str(uuid.uuid4()),
        })
        assert resp.status_code in (401, 403)

    def test_request_match_success(self, client, db):
        user_a = _user(db)
        user_b = _user(db)
        room = _room(db)
        persona_a = _persona(db, user_a, room)
        persona_b = _persona(db, user_b, room)

        resp = client.post("/v1/matches/request", json={
            "target_persona_id": str(persona_b.id),
            "room_id": str(room.id),
        }, headers=_auth(user_a))
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_accept_match(self, client, db):
        user_a = _user(db)
        user_b = _user(db)
        persona_a = _persona(db, user_a)
        persona_b = _persona(db, user_b)
        match = Match(
            id=uuid.uuid4(),
            requester_persona_id=persona_a.id,
            target_persona_id=persona_b.id,
            status=MatchStatus.PENDING,
            consent_state=ConsentState.REQUESTED,
        )
        db.add(match)
        db.commit()

        resp = client.post(f"/v1/matches/{match.id}/accept", headers=_auth(user_b))
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_reject_match(self, client, db):
        user_a = _user(db)
        user_b = _user(db)
        persona_a = _persona(db, user_a)
        persona_b = _persona(db, user_b)
        match = Match(
            id=uuid.uuid4(),
            requester_persona_id=persona_a.id,
            target_persona_id=persona_b.id,
            status=MatchStatus.PENDING,
            consent_state=ConsentState.REQUESTED,
        )
        db.add(match)
        db.commit()

        resp = client.post(f"/v1/matches/{match.id}/reject", headers=_auth(user_b))
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_my_matches_empty(self, client, db):
        user = _user(db)
        resp = client.get("/v1/matches/me", headers=_auth(user))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_my_matches_returns_own(self, client, db):
        user_a = _user(db)
        user_b = _user(db)
        persona_a = _persona(db, user_a)
        persona_b = _persona(db, user_b)
        _match(db, persona_a, persona_b)

        resp = client.get("/v1/matches/me", headers=_auth(user_a))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# ── Messages ──────────────────────────────────────────────────────────────────

class TestMessagesAPI:
    def test_send_message_requires_auth(self, client):
        resp = client.post("/v1/messages", json={
            "match_id": str(uuid.uuid4()),
            "sender_persona_id": str(uuid.uuid4()),
            "content": "hello",
        })
        assert resp.status_code in (401, 403)

    def test_send_and_retrieve_messages(self, client, db):
        user_a = _user(db)
        user_b = _user(db)
        persona_a = _persona(db, user_a)
        persona_b = _persona(db, user_b)
        match = _match(db, persona_a, persona_b)

        resp = client.post("/v1/messages", json={
            "match_id": str(match.id),
            "sender_persona_id": str(persona_a.id),
            "content": "Hey!",
        }, headers=_auth(user_a))
        assert resp.status_code == 201
        assert resp.json()["content"] == "Hey!"

        resp2 = client.get(f"/v1/messages/{match.id}", headers=_auth(user_a))
        assert resp2.status_code == 200
        assert resp2.json()["total"] >= 1

    def test_get_messages_requires_auth(self, client):
        resp = client.get(f"/v1/messages/{uuid.uuid4()}")
        assert resp.status_code in (401, 403)


# ── Safety ────────────────────────────────────────────────────────────────────

class TestSafetyAPI:
    def test_file_report_requires_auth(self, client):
        resp = client.post("/v1/safety/report", json={
            "reported_user_id": str(uuid.uuid4()),
            "report_type": "harassment",
            "description": "This is a long enough description for validation.",
        })
        assert resp.status_code in (401, 403)

    def test_file_report_success(self, client, db):
        reporter = _user(db)
        reported = _user(db)
        resp = client.post("/v1/safety/report", json={
            "reported_user_id": str(reported.id),
            "report_type": "harassment",
            "description": "Sent repeated unwanted messages after I said no.",
        }, headers=_auth(reporter))
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_block_user_success(self, client, db):
        blocker = _user(db)
        blocked = _user(db)
        resp = client.post("/v1/safety/block", json={
            "blocked_user_id": str(blocked.id),
        }, headers=_auth(blocker))
        assert resp.status_code == 201
        assert resp.json()["blocker_id"] == str(blocker.id)

    def test_get_reports_empty(self, client, db):
        user = _user(db)
        resp = client.get("/v1/safety/reports", headers=_auth(user))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_resolve_report(self, client, db):
        reporter = _user(db)
        reported = _user(db)
        resolver = _user(db)

        # File first
        r = client.post("/v1/safety/report", json={
            "reported_user_id": str(reported.id),
            "report_type": "spam",
            "description": "This user is spamming everyone in the room.",
        }, headers=_auth(reporter))
        report_id = r.json()["id"]

        # Resolve
        resp = client.post(f"/v1/safety/reports/{report_id}/resolve", json={
            "resolution_notes": "User has been warned.",
            "action_taken": "warned",
        }, headers=_auth(resolver))
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"


# ── Attestations ──────────────────────────────────────────────────────────────

class TestAttestationsAPI:
    def _make_match(self, db):
        user_a = _user(db)
        user_b = _user(db)
        persona_a = _persona(db, user_a)
        persona_b = _persona(db, user_b)
        match = _match(db, persona_a, persona_b)
        return user_a, user_b, match

    def test_initiate_attestation_requires_auth(self, client, db):
        _, _, match = self._make_match(db)
        resp = client.post("/v1/attestations/meetup/initiate", json={
            "match_id": str(match.id),
            "method": "mutual_confirmation",
        })
        assert resp.status_code in (401, 403)

    def test_initiate_attestation_success(self, client, db):
        user_a, _, match = self._make_match(db)
        resp = client.post("/v1/attestations/meetup/initiate", json={
            "match_id": str(match.id),
            "method": "mutual_confirmation",
        }, headers=_auth(user_a))
        assert resp.status_code == 201
        assert resp.json()["status"] == "initiated"

    def test_confirm_attestation(self, client, db):
        user_a, user_b, match = self._make_match(db)

        # Initiate
        r = client.post("/v1/attestations/meetup/initiate", json={
            "match_id": str(match.id),
            "method": "mutual_confirmation",
        }, headers=_auth(user_a))
        att_id = r.json()["id"]

        # Counterparty confirms
        resp = client.post(f"/v1/attestations/meetup/{att_id}/confirm",
                           json={}, headers=_auth(user_b))
        assert resp.status_code == 200

    def test_proximity_verify(self, client, db):
        user_a, _, match = self._make_match(db)
        resp = client.post("/v1/attestations/proximity", json={
            "match_id": str(match.id),
            "method": "gps_checkin",
            "latitude": 25.7617,
            "longitude": -80.1918,
        }, headers=_auth(user_a))
        assert resp.status_code == 200

    def test_my_attestations(self, client, db):
        user_a, _, match = self._make_match(db)
        client.post("/v1/attestations/meetup/initiate", json={
            "match_id": str(match.id),
            "method": "mutual_confirmation",
        }, headers=_auth(user_a))

        resp = client.get("/v1/attestations/me", headers=_auth(user_a))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ── Reputation ────────────────────────────────────────────────────────────────

class TestReputationAPI:
    def test_my_reputation_requires_auth(self, client):
        resp = client.get("/v1/reputation/me")
        assert resp.status_code in (401, 403)

    def test_my_reputation_creates_and_returns(self, client, db):
        user = _user(db)
        resp = client.get("/v1/reputation/me", headers=_auth(user))
        assert resp.status_code == 200
        data = resp.json()
        assert "composite_score" in data or "reliability_score" in data

    def test_persona_reputation(self, client, db):
        user = _user(db)
        persona = _persona(db, user)
        resp = client.get(f"/v1/reputation/persona/{persona.id}")
        assert resp.status_code == 200

    def test_persona_reputation_not_found(self, client):
        resp = client.get(f"/v1/reputation/persona/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_submit_feedback(self, client, db):
        reporter = _user(db)
        target = _user(db)
        resp = client.post("/v1/reputation/feedback", json={
            "target_user_id": str(target.id),
            "reference_id": str(uuid.uuid4()),
            "event_type": "positive_feedback",
        }, headers=_auth(reporter))
        assert resp.status_code == 201

    def test_attestation_score_update(self, client, db):
        user_a = _user(db)
        user_b = _user(db)
        persona_a = _persona(db, user_a)
        persona_b = _persona(db, user_b)
        match = _match(db, persona_a, persona_b)
        att = MeetupAttestation(
            id=uuid.uuid4(), match_id=match.id,
            initiator_user_id=user_a.id, counterparty_user_id=user_b.id,
            method=AttestationMethod.GPS_CHECKIN,
            status=AttestationStatus.CONFIRMED,
        )
        db.add(att)
        db.commit()

        resp = client.post(f"/v1/reputation/attestation-score",
                           params={"attestation_id": str(att.id)},
                           headers=_auth(user_a))
        assert resp.status_code == 200
