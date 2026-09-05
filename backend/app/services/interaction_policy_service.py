"""
Centralised pre-send / pre-match interaction policy checks.

All business rules that guard whether two parties may message or match are
consolidated here so that MatchService and MessageService stay DRY.
"""
from sqlalchemy.orm import Session
from uuid import UUID

from ..models.match import Match, MatchStatus, ConsentState
from ..models.persona import Persona
from ..models.block import Block
from ..core.errors import (
    MessagingBlockedError,
    ConsentRequiredError,
    BlockedUserError,
    PersonaNotFoundError,
)


class InteractionPolicyService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_can_message(self, sender_user_id: UUID, match: Match) -> None:
        """Raise MessagingBlockedError (or sub-class) if the sender cannot
        send a message in this match.

        Checks (in order):
        1. Match must be ACCEPTED with consent GRANTED.
        2. Sender must be a participant in the match.
        3. Neither party may have blocked the other.
        """
        self.check_consent_granted(match)
        self._check_participant(sender_user_id, match)
        requester_user_id = self._user_id_for_persona(match.requester_persona_id)
        target_user_id = self._user_id_for_persona(match.target_persona_id)
        if requester_user_id and target_user_id:
            self.check_not_blocked(requester_user_id, target_user_id)

    def check_can_match(self, requester_user_id: UUID, target_persona_id: UUID) -> None:
        """Raise BlockedUserError if a block exists between the two users."""
        target_persona = self.db.query(Persona).filter(
            Persona.id == target_persona_id
        ).first()
        if not target_persona:
            raise PersonaNotFoundError()
        self.check_not_blocked(requester_user_id, target_persona.user_id)

    def check_persona_in_room(self, persona_id: UUID, room_id: UUID) -> bool:
        """Return True if the persona's room_id matches the given room_id."""
        persona = self.db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            return False
        return persona.room_id == room_id

    def check_consent_granted(self, match: Match) -> None:
        """Raise ConsentRequiredError or MessagingBlockedError if consent is
        not fully in place."""
        if match.consent_state != ConsentState.GRANTED:
            raise ConsentRequiredError()
        if match.status != MatchStatus.ACCEPTED:
            raise MessagingBlockedError("Match not accepted")

    def check_not_blocked(self, user_a_id: UUID, user_b_id: UUID) -> None:
        """Raise BlockedUserError if either user has blocked the other."""
        block = self.db.query(Block).filter(
            ((Block.blocker_id == user_a_id) & (Block.blocked_id == user_b_id))
            | ((Block.blocker_id == user_b_id) & (Block.blocked_id == user_a_id))
        ).first()
        if block:
            raise BlockedUserError()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _user_id_for_persona(self, persona_id: UUID):
        persona = self.db.query(Persona).filter(Persona.id == persona_id).first()
        return persona.user_id if persona else None

    def _check_participant(self, user_id: UUID, match: Match) -> None:
        """Ensure user_id owns at least one persona that is in the match."""
        persona_ids = [
            p.id
            for p in self.db.query(Persona.id)
            .filter(Persona.user_id == user_id)
            .all()
        ]
        if (
            match.requester_persona_id not in persona_ids
            and match.target_persona_id not in persona_ids
        ):
            raise MessagingBlockedError("Not a participant in this match")
