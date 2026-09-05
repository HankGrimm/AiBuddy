"""
Tests for messaging layer — Sprint 3.

Covers:
- test_send_message_requires_accepted_match
- test_send_message_blocked_when_no_consent
- test_send_message_blocked_when_user_blocked
- test_get_message_thread
"""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.persona import Persona
from app.models.match import Match, MatchStatus, ConsentState
from app.models.block import Block
from app.services.message_service import MessageService
from app.schemas.message import MessageCreate, MessageType
from app.core.errors import MessagingBlockedError, ConsentRequiredError, BlockedUserError


# ---------------------------------------------------------------------------
# Helpers (duplicated minimally; shared fixture module is a future refactor)
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


def make_persona(db: Session, user: User) -> Persona:
    persona = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name=f"persona_{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


def make_match(
    db: Session,
    requester_persona: Persona,
    target_persona: Persona,
    status: MatchStatus = MatchStatus.ACCEPTED,
    consent_state: ConsentState = ConsentState.GRANTED,
) -> Match:
    match = Match(
        id=uuid.uuid4(),
        requester_persona_id=requester_persona.id,
        target_persona_id=target_persona.id,
        status=status,
        consent_state=consent_state,
        expires_at=datetime.utcnow() + timedelta(hours=48),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def _msg_payload(match_id) -> MessageCreate:
    return MessageCreate(match_id=match_id, content="Hello!")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_send_message_requires_accepted_match(db: Session):
    """Cannot send a message when match is still PENDING (not accepted)."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    match = make_match(
        db,
        requester_persona,
        target_persona,
        status=MatchStatus.PENDING,
        consent_state=ConsentState.REQUESTED,
    )

    svc = MessageService(db)
    with pytest.raises((ConsentRequiredError, MessagingBlockedError)):
        svc.send(requester, _msg_payload(match.id))


def test_send_message_blocked_when_no_consent(db: Session):
    """Sending a message when consent is REQUESTED (not GRANTED) raises ConsentRequiredError."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    # status ACCEPTED but consent still REQUESTED — edge case
    match = make_match(
        db,
        requester_persona,
        target_persona,
        status=MatchStatus.ACCEPTED,
        consent_state=ConsentState.REQUESTED,
    )

    svc = MessageService(db)
    with pytest.raises(ConsentRequiredError):
        svc.send(requester, _msg_payload(match.id))


def test_send_message_blocked_when_user_blocked(db: Session):
    """Sending a message is blocked when either user has blocked the other."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    match = make_match(db, requester_persona, target_persona)

    # target blocks requester after the match was already accepted
    block = Block(
        id=uuid.uuid4(),
        blocker_id=target.id,
        blocked_id=requester.id,
    )
    db.add(block)
    db.commit()

    svc = MessageService(db)
    with pytest.raises(BlockedUserError):
        svc.send(requester, _msg_payload(match.id))


def test_send_message_success(db: Session):
    """Happy-path: sending a message in an accepted, consented, unblocked match."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    match = make_match(db, requester_persona, target_persona)

    svc = MessageService(db)
    msg = svc.send(requester, _msg_payload(match.id))

    assert msg.match_id == match.id
    assert msg.content == "Hello!"
    assert msg.sender_persona_id == requester_persona.id


def test_get_message_thread(db: Session):
    """get_thread returns messages in chronological order."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)

    match = make_match(db, requester_persona, target_persona)

    svc = MessageService(db)

    # Send two messages from each side
    svc.send(requester, MessageCreate(match_id=match.id, content="Hi!"))
    svc.send(target, MessageCreate(match_id=match.id, content="Hey there!"))
    svc.send(requester, MessageCreate(match_id=match.id, content="How are you?"))

    thread = svc.get_thread(requester, match.id)

    assert thread.total == 3
    assert thread.match_id == match.id
    contents = [m.content for m in thread.messages]
    assert contents == ["Hi!", "Hey there!", "How are you?"]


def test_get_message_thread_non_participant(db: Session):
    """A user who is not part of the match cannot read the thread."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)
    bystander = make_user(db)

    match = make_match(db, requester_persona, target_persona)

    svc = MessageService(db)
    with pytest.raises(MessagingBlockedError):
        svc.get_thread(bystander, match.id)


def test_send_message_non_participant_blocked(db: Session):
    """A user who is not part of the match cannot send a message."""
    requester = make_user(db)
    requester_persona = make_persona(db, requester)
    target = make_user(db)
    target_persona = make_persona(db, target)
    outsider = make_user(db)

    match = make_match(db, requester_persona, target_persona)

    svc = MessageService(db)
    with pytest.raises(MessagingBlockedError):
        svc.send(outsider, _msg_payload(match.id))
