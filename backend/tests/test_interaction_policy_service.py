"""
Tests for InteractionPolicyService covering uncovered lines:
- check_can_match: PersonaNotFoundError (line 51)
- check_persona_in_room: persona not found → False (lines 56-58), match (line 59)
- check_consent_granted: status != ACCEPTED → MessagingBlockedError (line 67)
"""
import uuid
import pytest

from app.models.user import User
from app.models.persona import Persona, IntentMode
from app.models.match import Match, MatchStatus, ConsentState
from app.models.block import Block
from app.services.interaction_policy_service import InteractionPolicyService
from app.core.errors import (
    MessagingBlockedError,
    ConsentRequiredError,
    BlockedUserError,
    PersonaNotFoundError,
)


def make_user(db):
    u = User(id=uuid.uuid4(), wallet_address=f"w_{uuid.uuid4().hex[:8]}", is_active=True)
    db.add(u)
    db.commit()
    return u


def make_persona(db, user, room_id=None):
    p = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name=f"p_{uuid.uuid4().hex[:6]}",
        intent_mode=IntentMode.SOCIAL,
        is_active=True,
        room_id=room_id,
    )
    db.add(p)
    db.commit()
    return p


def make_match(db, persona_a, persona_b, status=MatchStatus.ACCEPTED, consent=ConsentState.GRANTED):
    m = Match(
        id=uuid.uuid4(),
        requester_persona_id=persona_a.id,
        target_persona_id=persona_b.id,
        status=status,
        consent_state=consent,
    )
    db.add(m)
    db.commit()
    return m


class TestCheckCanMatch:
    """check_can_match: raises PersonaNotFoundError when target persona missing (line 51)."""

    def test_missing_target_persona_raises_not_found(self, db):
        user = make_user(db)
        svc = InteractionPolicyService(db)
        with pytest.raises(PersonaNotFoundError):
            svc.check_can_match(user.id, uuid.uuid4())

    def test_blocked_target_raises_blocked_error(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        persona_b = make_persona(db, user_b)
        block = Block(id=uuid.uuid4(), blocker_id=user_a.id, blocked_id=user_b.id)
        db.add(block)
        db.commit()
        svc = InteractionPolicyService(db)
        with pytest.raises(BlockedUserError):
            svc.check_can_match(user_a.id, persona_b.id)

    def test_no_block_does_not_raise(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        persona_b = make_persona(db, user_b)
        svc = InteractionPolicyService(db)
        # Should not raise
        svc.check_can_match(user_a.id, persona_b.id)


class TestCheckPersonaInRoom:
    """check_persona_in_room: missing persona → False (lines 56-58), match (line 59)."""

    def test_unknown_persona_returns_false(self, db):
        svc = InteractionPolicyService(db)
        assert svc.check_persona_in_room(uuid.uuid4(), uuid.uuid4()) is False

    def test_persona_in_correct_room_returns_true(self, db):
        user = make_user(db)
        room_id = uuid.uuid4()
        persona = make_persona(db, user, room_id=room_id)
        svc = InteractionPolicyService(db)
        assert svc.check_persona_in_room(persona.id, room_id) is True

    def test_persona_in_different_room_returns_false(self, db):
        user = make_user(db)
        room_id = uuid.uuid4()
        persona = make_persona(db, user, room_id=room_id)
        svc = InteractionPolicyService(db)
        assert svc.check_persona_in_room(persona.id, uuid.uuid4()) is False

    def test_persona_no_room_returns_false(self, db):
        user = make_user(db)
        persona = make_persona(db, user, room_id=None)
        svc = InteractionPolicyService(db)
        assert svc.check_persona_in_room(persona.id, uuid.uuid4()) is False


class TestCheckConsentGranted:
    """check_consent_granted: ACCEPTED+GRANTED passes; non-ACCEPTED raises MessagingBlockedError (line 67)."""

    def test_accepted_granted_does_not_raise(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa = make_persona(db, user_a)
        pb = make_persona(db, user_b)
        match = make_match(db, pa, pb, status=MatchStatus.ACCEPTED, consent=ConsentState.GRANTED)
        svc = InteractionPolicyService(db)
        svc.check_consent_granted(match)  # no raise

    def test_consent_not_granted_raises_consent_required(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa = make_persona(db, user_a)
        pb = make_persona(db, user_b)
        match = make_match(db, pa, pb, status=MatchStatus.ACCEPTED, consent=ConsentState.REQUESTED)
        svc = InteractionPolicyService(db)
        with pytest.raises(ConsentRequiredError):
            svc.check_consent_granted(match)

    def test_match_not_accepted_raises_messaging_blocked(self, db):
        """Covers line 67: consent=GRANTED but status != ACCEPTED."""
        user_a = make_user(db)
        user_b = make_user(db)
        pa = make_persona(db, user_a)
        pb = make_persona(db, user_b)
        match = make_match(db, pa, pb, status=MatchStatus.PENDING, consent=ConsentState.GRANTED)
        svc = InteractionPolicyService(db)
        with pytest.raises(MessagingBlockedError):
            svc.check_consent_granted(match)

    def test_expired_match_raises_messaging_blocked(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa = make_persona(db, user_a)
        pb = make_persona(db, user_b)
        match = make_match(db, pa, pb, status=MatchStatus.EXPIRED, consent=ConsentState.GRANTED)
        svc = InteractionPolicyService(db)
        with pytest.raises(MessagingBlockedError):
            svc.check_consent_granted(match)


class TestCheckCanMessage:
    """Full check_can_message flow."""

    def test_non_participant_raises_messaging_blocked(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        user_c = make_user(db)
        pa = make_persona(db, user_a)
        pb = make_persona(db, user_b)
        match = make_match(db, pa, pb)
        svc = InteractionPolicyService(db)
        with pytest.raises(MessagingBlockedError):
            svc.check_can_message(user_c.id, match)

    def test_participant_can_message(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa = make_persona(db, user_a)
        pb = make_persona(db, user_b)
        match = make_match(db, pa, pb)
        svc = InteractionPolicyService(db)
        svc.check_can_message(user_a.id, match)  # no raise

    def test_blocked_participant_raises(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        pa = make_persona(db, user_a)
        pb = make_persona(db, user_b)
        match = make_match(db, pa, pb)
        block = Block(id=uuid.uuid4(), blocker_id=user_a.id, blocked_id=user_b.id)
        db.add(block)
        db.commit()
        svc = InteractionPolicyService(db)
        with pytest.raises(BlockedUserError):
            svc.check_can_message(user_a.id, match)


class TestCheckNotBlocked:
    """check_not_blocked: bilateral block detection."""

    def test_no_block_passes(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        svc = InteractionPolicyService(db)
        svc.check_not_blocked(user_a.id, user_b.id)  # no raise

    def test_a_blocks_b_raises(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        db.add(Block(id=uuid.uuid4(), blocker_id=user_a.id, blocked_id=user_b.id))
        db.commit()
        svc = InteractionPolicyService(db)
        with pytest.raises(BlockedUserError):
            svc.check_not_blocked(user_a.id, user_b.id)

    def test_b_blocks_a_also_raises(self, db):
        user_a = make_user(db)
        user_b = make_user(db)
        db.add(Block(id=uuid.uuid4(), blocker_id=user_b.id, blocked_id=user_a.id))
        db.commit()
        svc = InteractionPolicyService(db)
        with pytest.raises(BlockedUserError):
            svc.check_not_blocked(user_a.id, user_b.id)
