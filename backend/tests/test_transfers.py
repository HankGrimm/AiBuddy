"""
Transfer endpoint and service tests — TDD for POST /v1/transfers.
Refs #16
"""
import uuid
import pytest

from app.models.user import User, VerificationLevel, PrivacyMode
from app.models.transfer import Transfer, TransferStatus
from app.schemas.transfer import TransferCreate
from app.services.transfer_service import TransferService
from app.core.auth import create_access_token


# ------------------------------------------------------------------ helpers

def make_user(db, wallet: str = None) -> User:
    u = User(
        id=uuid.uuid4(),
        wallet_address=wallet or f"wallet_{uuid.uuid4().hex[:8]}",
        verification_level=VerificationLevel.WALLET,
        privacy_mode=PrivacyMode.SEMI_PRIVATE,
    )
    db.add(u)
    db.commit()
    return u


def auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id), user.wallet_address)
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ service tests

class TestTransferServiceCreate:
    def test_create_success(self, db):
        sender = make_user(db)
        recipient = make_user(db, wallet="wallet_recipient_abc")
        svc = TransferService(db)
        payload = TransferCreate(recipient_wallet="wallet_recipient_abc", amount_mon=0.5)
        result = svc.create(sender, payload)

        assert result.sender_id == sender.id
        assert result.recipient_id == recipient.id
        assert float(result.amount_mon) == 0.5
        assert result.status == TransferStatus.PENDING
        assert result.tx_hash is None

    def test_create_with_message(self, db):
        sender = make_user(db)
        recipient = make_user(db, wallet="wallet_msg_test")
        svc = TransferService(db)
        payload = TransferCreate(
            recipient_wallet="wallet_msg_test",
            amount_mon=1.0,
            message="Thanks for the great time!",
        )
        result = svc.create(sender, payload)
        assert result.message == "Thanks for the great time!"

    def test_recipient_not_found_raises_404(self, db):
        from fastapi import HTTPException
        sender = make_user(db)
        svc = TransferService(db)
        payload = TransferCreate(recipient_wallet="nonexistent_wallet", amount_mon=0.1)
        with pytest.raises(HTTPException) as exc:
            svc.create(sender, payload)
        assert exc.value.status_code == 404

    def test_cannot_transfer_to_self(self, db):
        from fastapi import HTTPException
        sender = make_user(db, wallet="wallet_self_xyz")
        svc = TransferService(db)
        payload = TransferCreate(recipient_wallet="wallet_self_xyz", amount_mon=0.1)
        with pytest.raises(HTTPException) as exc:
            svc.create(sender, payload)
        assert exc.value.status_code == 400

    def test_amount_zero_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TransferCreate(recipient_wallet="some_wallet", amount_mon=0.0)

    def test_amount_negative_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TransferCreate(recipient_wallet="some_wallet", amount_mon=-1.0)

    def test_get_sent(self, db):
        sender = make_user(db)
        recipient = make_user(db, wallet="wallet_for_sent")
        svc = TransferService(db)
        svc.create(sender, TransferCreate(recipient_wallet="wallet_for_sent", amount_mon=0.1))
        svc.create(sender, TransferCreate(recipient_wallet="wallet_for_sent", amount_mon=0.2))
        results = svc.get_sent(sender.id)
        assert len(results) == 2

    def test_get_received(self, db):
        sender = make_user(db)
        recipient = make_user(db, wallet="wallet_for_recv")
        svc = TransferService(db)
        svc.create(sender, TransferCreate(recipient_wallet="wallet_for_recv", amount_mon=0.3))
        results = svc.get_received(recipient.id)
        assert len(results) == 1
        assert float(results[0].amount_mon) == 0.3


# ------------------------------------------------------------------ endpoint tests

class TestTransferEndpoint:
    def test_create_transfer_201(self, client, db):
        sender = make_user(db)
        make_user(db, wallet="wallet_recv_endpoint")
        resp = client.post(
            "/v1/transfers",
            json={"recipient_wallet": "wallet_recv_endpoint", "amount_mon": 0.5},
            headers=auth_headers(sender),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["amount_mon"] == 0.5
        assert data["tx_hash"] is None
        assert data["sender_id"] == str(sender.id)

    def test_recipient_not_found_404(self, client, db):
        sender = make_user(db)
        resp = client.post(
            "/v1/transfers",
            json={"recipient_wallet": "ghost_wallet", "amount_mon": 0.1},
            headers=auth_headers(sender),
        )
        assert resp.status_code == 404

    def test_self_transfer_400(self, client, db):
        sender = make_user(db, wallet="wallet_self_endpoint")
        resp = client.post(
            "/v1/transfers",
            json={"recipient_wallet": "wallet_self_endpoint", "amount_mon": 0.1},
            headers=auth_headers(sender),
        )
        assert resp.status_code == 400

    def test_unauthenticated_401(self, client, db):
        resp = client.post(
            "/v1/transfers",
            json={"recipient_wallet": "some_wallet", "amount_mon": 0.1},
        )
        assert resp.status_code == 401

    def test_zero_amount_422(self, client, db):
        sender = make_user(db)
        resp = client.post(
            "/v1/transfers",
            json={"recipient_wallet": "some_wallet", "amount_mon": 0.0},
            headers=auth_headers(sender),
        )
        assert resp.status_code == 422
