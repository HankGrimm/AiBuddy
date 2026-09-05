"""
Moment NFT endpoint and service tests — TDD for mint-moment + list-moments.
Refs #17
"""
import uuid
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from app.models.user import User, VerificationLevel, PrivacyMode
from app.models.attestation import MeetupAttestation, AttestationStatus, AttestationMethod
from app.models.moment_nft import MomentNFT, MomentNFTStatus
from app.models.match import Match, MatchStatus, ConsentState
from app.models.persona import Persona
from app.schemas.moment_nft import MintMomentRequest
from app.services.moment_nft_service import MomentNFTService
from app.core.auth import create_access_token


# ------------------------------------------------------------------ helpers

def make_user(db) -> User:
    u = User(
        id=uuid.uuid4(),
        wallet_address=f"wallet_{uuid.uuid4().hex[:8]}",
        verification_level=VerificationLevel.WALLET,
        privacy_mode=PrivacyMode.SEMI_PRIVATE,
    )
    db.add(u)
    db.commit()
    return u


def make_persona(db, user: User) -> Persona:
    p = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Tester",
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(p)
    db.commit()
    return p


def make_match(db, persona_a: Persona, persona_b: Persona) -> Match:
    m = Match(
        id=uuid.uuid4(),
        requester_persona_id=persona_a.id,
        target_persona_id=persona_b.id,
        status=MatchStatus.ACCEPTED,
        consent_state=ConsentState.GRANTED,
    )
    db.add(m)
    db.commit()
    return m


def make_confirmed_attestation(db, user_a: User, user_b: User, match: Match) -> MeetupAttestation:
    a = MeetupAttestation(
        id=uuid.uuid4(),
        match_id=match.id,
        initiator_user_id=user_a.id,
        counterparty_user_id=user_b.id,
        method=AttestationMethod.QR_CODE,
        status=AttestationStatus.CONFIRMED,
        initiator_confirmed=True,
        counterparty_confirmed=True,
        confirmed_at=datetime.utcnow(),
    )
    db.add(a)
    db.commit()
    return a


def auth_header(user: User) -> dict:
    token = create_access_token(str(user.id), user.wallet_address)
    return {"Authorization": f"Bearer {token}"}


# ================================================================== SERVICE TESTS


class TestMomentNFTServiceMint:
    """Unit tests for MomentNFTService.mint_moment"""

    def test_mint_success(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        svc = MomentNFTService(db)
        nft = svc.mint_moment(user_a, MintMomentRequest(
            attestation_id=att.id,
            name="Monad Mate Moment #1",
        ))

        assert nft.owner_id == user_a.id
        assert nft.attestation_id == att.id
        assert nft.status == MomentNFTStatus.PENDING
        assert nft.name == "Monad Mate Moment #1"
        assert nft.mint_address is None

    def test_mint_with_description(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        svc = MomentNFTService(db)
        nft = svc.mint_moment(user_a, MintMomentRequest(
            attestation_id=att.id,
            name="Test Moment",
            description="Met at the coffee shop",
        ))

        assert nft.description == "Met at the coffee shop"

    def test_mint_attestation_not_found(self, db):
        user = make_user(db)
        svc = MomentNFTService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.mint_moment(user, MintMomentRequest(
                attestation_id=uuid.uuid4(),
                name="Ghost Moment",
            ))
        assert exc_info.value.status_code == 404

    def test_mint_attestation_not_confirmed(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)

        att = MeetupAttestation(
            id=uuid.uuid4(),
            match_id=match.id,
            initiator_user_id=user_a.id,
            counterparty_user_id=user_b.id,
            method=AttestationMethod.QR_CODE,
            status=AttestationStatus.INITIATED,
        )
        db.add(att)
        db.commit()

        svc = MomentNFTService(db)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.mint_moment(user_a, MintMomentRequest(
                attestation_id=att.id,
                name="Too Early",
            ))
        assert exc_info.value.status_code == 400
        assert "not confirmed" in exc_info.value.detail.lower()

    def test_mint_user_not_party(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        outsider = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        svc = MomentNFTService(db)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.mint_moment(outsider, MintMomentRequest(
                attestation_id=att.id,
                name="Not My Moment",
            ))
        assert exc_info.value.status_code == 400
        assert "not a party" in exc_info.value.detail.lower()

    def test_mint_duplicate_blocked(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        svc = MomentNFTService(db)
        svc.mint_moment(user_a, MintMomentRequest(
            attestation_id=att.id,
            name="First",
        ))

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.mint_moment(user_b, MintMomentRequest(
                attestation_id=att.id,
                name="Second Try",
            ))
        assert exc_info.value.status_code == 409


class TestMomentNFTServiceList:
    """Unit tests for MomentNFTService.list_user_moments"""

    def test_list_empty(self, db):
        user = make_user(db)
        svc = MomentNFTService(db)
        items, total = svc.list_user_moments(user.id)
        assert items == []
        assert total == 0

    def test_list_returns_own_nfts_only(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        svc = MomentNFTService(db)
        svc.mint_moment(user_a, MintMomentRequest(
            attestation_id=att.id,
            name="A's Moment",
        ))

        items_a, total_a = svc.list_user_moments(user_a.id)
        items_b, total_b = svc.list_user_moments(user_b.id)

        assert total_a == 1
        assert total_b == 0

    def test_list_pagination(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)

        # Create 3 NFTs for user_a
        for i in range(3):
            match = make_match(db, pa, pb)
            att = make_confirmed_attestation(db, user_a, user_b, match)
            nft = MomentNFT(
                owner_id=user_a.id,
                attestation_id=att.id,
                name=f"Moment #{i}",
                status=MomentNFTStatus.PENDING,
            )
            db.add(nft)
        db.commit()

        svc = MomentNFTService(db)
        items, total = svc.list_user_moments(user_a.id, limit=2, offset=0)
        assert len(items) == 2
        assert total == 3

        items2, total2 = svc.list_user_moments(user_a.id, limit=2, offset=2)
        assert len(items2) == 1
        assert total2 == 3


# ================================================================== ENDPOINT TESTS


class TestMintMomentEndpoint:
    """Integration tests for POST /v1/nfts/mint-moment"""

    def test_mint_success_201(self, client, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        resp = client.post(
            "/v1/nfts/mint-moment",
            json={
                "attestation_id": str(att.id),
                "name": "Monad Mate Moment #1",
            },
            headers=auth_header(user_a),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["owner_id"] == str(user_a.id)
        assert data["attestation_id"] == str(att.id)
        assert data["status"] == "pending"
        assert data["mint_address"] is None
        assert data["name"] == "Monad Mate Moment #1"

    def test_mint_attestation_not_found_404(self, client, db):
        user = make_user(db)
        resp = client.post(
            "/v1/nfts/mint-moment",
            json={
                "attestation_id": str(uuid.uuid4()),
                "name": "Ghost",
            },
            headers=auth_header(user),
        )
        assert resp.status_code == 404

    def test_mint_not_confirmed_400(self, client, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)

        att = MeetupAttestation(
            id=uuid.uuid4(),
            match_id=match.id,
            initiator_user_id=user_a.id,
            counterparty_user_id=user_b.id,
            method=AttestationMethod.QR_CODE,
            status=AttestationStatus.PENDING_CONFIRM,
        )
        db.add(att)
        db.commit()

        resp = client.post(
            "/v1/nfts/mint-moment",
            json={"attestation_id": str(att.id), "name": "Nope"},
            headers=auth_header(user_a),
        )
        assert resp.status_code == 400

    def test_mint_wrong_user_400(self, client, db):
        user_a = make_user(db)
        user_b = make_user(db)
        outsider = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        resp = client.post(
            "/v1/nfts/mint-moment",
            json={"attestation_id": str(att.id), "name": "Not mine"},
            headers=auth_header(outsider),
        )
        assert resp.status_code == 400

    def test_mint_duplicate_409(self, client, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        resp1 = client.post(
            "/v1/nfts/mint-moment",
            json={"attestation_id": str(att.id), "name": "First"},
            headers=auth_header(user_a),
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/v1/nfts/mint-moment",
            json={"attestation_id": str(att.id), "name": "Dup"},
            headers=auth_header(user_b),
        )
        assert resp2.status_code == 409

    def test_mint_unauthenticated_401(self, client, db):
        resp = client.post(
            "/v1/nfts/mint-moment",
            json={"attestation_id": str(uuid.uuid4()), "name": "No Auth"},
        )
        assert resp.status_code in (401, 403)


class TestListMomentsEndpoint:
    """Integration tests for GET /v1/nfts/moments"""

    def test_list_empty(self, client, db):
        user = make_user(db)
        resp = client.get("/v1/nfts/moments", headers=auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_list_returns_own_nfts(self, client, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa, pb = make_persona(db, user_a), make_persona(db, user_b)
        match = make_match(db, pa, pb)
        att = make_confirmed_attestation(db, user_a, user_b, match)

        # Mint as user_a
        client.post(
            "/v1/nfts/mint-moment",
            json={"attestation_id": str(att.id), "name": "Mine"},
            headers=auth_header(user_a),
        )

        resp_a = client.get("/v1/nfts/moments", headers=auth_header(user_a))
        resp_b = client.get("/v1/nfts/moments", headers=auth_header(user_b))

        assert resp_a.json()["total"] == 1
        assert resp_b.json()["total"] == 0

    def test_list_pagination_params(self, client, db):
        user = make_user(db)
        resp = client.get(
            "/v1/nfts/moments?limit=5&offset=10",
            headers=auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 10

    def test_list_limit_max_100(self, client, db):
        user = make_user(db)
        resp = client.get(
            "/v1/nfts/moments?limit=200",
            headers=auth_header(user),
        )
        assert resp.status_code == 422  # validation error

    def test_list_unauthenticated_401(self, client, db):
        resp = client.get("/v1/nfts/moments")
        assert resp.status_code in (401, 403)
