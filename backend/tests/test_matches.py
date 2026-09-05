"""
Tests for matching layer — Sprint 3.

Covers:
- test_request_match_requires_active_persona
- test_request_match_blocked_user_rejected
- test_accept_match_grants_consent
- test_reject_match
- test_match_expires_after_48h
"""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.persona import Persona
from app.models.match import Match, MatchStatus, ConsentState
from app.models.block import Block
from app.services.match_service import MatchService
from app.schemas.match import MatchRequest
from app.core.errors import PersonaNotFoundError, BlockedUserError, MatchNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(db: Session, wallet: str = None) -> User:
    user = User(
        id=uuid.uuid4(),
        wallet_address=wallet or f"wallet_{uuid.uuid4().hex[:8]}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_persona(db: Session, user: User, active: bool = True, room_id=None) -> Persona:
    persona = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name=f"persona_{uuid.uuid4().hex[:6]}",
        is_active=active,
        room_id=room_id,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


def make_match(
    db: Session,
    requester_persona: Persona,
    target_persona: Persona,
    status: MatchStatus = MatchStatus.PENDING,
    consent_state: ConsentState = ConsentState.REQUESTED,
    created_at: datetime = None,
) -> Match:
    match = Match(
        id=uuid.uuid4(),
        requester_persona_id=requester_persona.id,
        target_persona_id=target_persona.id,
        status=status,
        consent_state=consent_state,
        expires_at=datetime.utcnow() + timedelta(hours=48),
        created_at=created_at or datetime.utcnow(),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_request_match_requires_active_persona(db: Session):
    """Requesting a match without an active persona raises PersonaNotFoundError."""
    requester = make_user(db)
    target = make_user(db)
    target_persona = make_persona(db, target)

    svc = MatchService(db)
    with pytest.raises(PersonaNotFoundError):
        svc.request_match(
            requester,
            MatchRequest(target_persona_id=target_persona.id),
        )


def test_request_match_requires_active_persona_not_inactive(db: Session):
    """An inactive persona also raises PersonaNotFoundError (query filters is_active=True)."""
    requester = make_user(db)
    make_persona(db, requester, active=False)  # inactive — should be ignored
    target = make_user(db)
    target_persona = make_persona(db, target)

    svc = MatchService(db)
    with pytest.raises(PersonaNotFoundError):
        svc.request_match(
            requester,
            MatchRequest(target_persona_id=target_persona.id),
        )


def test_request_match_blocked_user_rejected(db: Session):
    """A match request is rejected when the target user has blocked the requester."""
    requester = make_user(db)
    make_persona(db, requester)
    target = make_user(db)
    make_persona(db, target)

    # target blocks requester
    block = Block(
        id=uuid.uuid4(),
        blocker_id=target.id,
        blocked_id=requester.id,
    )
    db.add(block)
    db.commit()

    target_persona = make_persona(db, target)

    svc = MatchService(db)
    with pytest.raises(BlockedUserError):
        svc.request_match(
            requester,
            MatchRequest(target_persona_id=target_persona.id),
        )


def test_accept_match_grants_consent(db: Session):
    """Accepting a match sets status=ACCEPTED and consent_state=GRANTED."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    match = make_match(db, requester_persona, target_persona)
    assert match.status == MatchStatus.PENDING
    assert match.consent_state == ConsentState.REQUESTED

    svc = MatchService(db)
    updated = svc.accept(target, match.id)

    assert updated.status == MatchStatus.ACCEPTED
    assert updated.consent_state == ConsentState.GRANTED
    assert updated.responded_at is not None


def test_reject_match(db: Session):
    """Rejecting a match sets status=REJECTED."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    match = make_match(db, requester_persona, target_persona)

    svc = MatchService(db)
    updated = svc.reject(target, match.id)

    assert updated.status == MatchStatus.REJECTED
    assert updated.responded_at is not None


def test_reject_match_wrong_user(db: Session):
    """A non-target user cannot reject a match (raises 403)."""
    from fastapi import HTTPException

    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)
    bystander = make_user(db)

    match = make_match(db, requester_persona, target_persona)

    svc = MatchService(db)
    with pytest.raises(HTTPException) as exc_info:
        svc.reject(bystander, match.id)
    assert exc_info.value.status_code == 403


def test_match_expires_after_48h(db: Session):
    """expire_stale_matches() marks PENDING matches older than 48 h as EXPIRED."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    # Create a match with created_at > 48 h ago
    old_time = datetime.utcnow() - timedelta(hours=49)
    stale_match = make_match(
        db, requester_persona, target_persona, created_at=old_time
    )

    # Fresh match (should NOT be expired)
    target2 = make_user(db)
    target_persona2 = make_persona(db, target2)
    fresh_match = make_match(db, requester_persona, target_persona2)

    svc = MatchService(db)
    count = svc.expire_stale_matches()

    db.refresh(stale_match)
    db.refresh(fresh_match)

    assert count == 1
    assert stale_match.status == MatchStatus.EXPIRED
    assert fresh_match.status == MatchStatus.PENDING


def test_match_expiry_skips_accepted(db: Session):
    """expire_stale_matches() does not touch already-ACCEPTED matches."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    old_time = datetime.utcnow() - timedelta(hours=49)
    accepted_match = make_match(
        db,
        requester_persona,
        target_persona,
        status=MatchStatus.ACCEPTED,
        consent_state=ConsentState.GRANTED,
        created_at=old_time,
    )

    svc = MatchService(db)
    count = svc.expire_stale_matches()

    db.refresh(accepted_match)
    assert count == 0
    assert accepted_match.status == MatchStatus.ACCEPTED
