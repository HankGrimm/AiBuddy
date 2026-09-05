from sqlalchemy.orm import Session
from uuid import UUID
import uuid

from ..models.message import Message
from ..models.match import Match, MatchStatus, ConsentState
from ..models.persona import Persona
from ..models.stake import Stake, StakeStatus
from ..models.user import User
from ..schemas.message import MessageCreate, MessageThread
from ..core.errors import MessagingBlockedError, ConsentRequiredError
from .interaction_policy_service import InteractionPolicyService


class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.policy = InteractionPolicyService(db)

    def send(self, user: User, payload: MessageCreate) -> Message:
        match = self.db.query(Match).filter(Match.id == payload.match_id).first()
        if not match:
            raise MessagingBlockedError("Match not found")

        # Centralised pre-send checks (consent, participant, block)
        self.policy.check_can_message(user.id, match)

        # Stake validation (separate concern)
        self._check_stake_if_required(payload)

        msg = Message(
            id=uuid.uuid4(),
            match_id=payload.match_id,
            sender_persona_id=self._get_sender_persona_id(user, match),
            type=payload.type,
            content=payload.content,
            stake_id=payload.stake_id,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_thread(self, user: User, match_id: UUID, skip: int = 0, limit: int = 50) -> MessageThread:
        match = self.db.query(Match).filter(Match.id == match_id).first()
        if not match:
            raise MessagingBlockedError("Match not found")

        # Ensure user is a participant
        self.policy._check_participant(user.id, match)

        messages = (
            self.db.query(Message)
            .filter(Message.match_id == match_id)
            .order_by(Message.created_at.asc())
            .offset(skip).limit(limit).all()
        )
        return MessageThread(messages=messages, total=len(messages), match_id=match_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_stake_if_required(self, payload: MessageCreate):
        if payload.stake_id:
            stake = self.db.query(Stake).filter(Stake.id == payload.stake_id).first()
            if not stake or stake.status != StakeStatus.ACTIVE:
                raise MessagingBlockedError("Required stake is not active")

    def _get_sender_persona_id(self, user: User, match: Match):
        persona = self.db.query(Persona).filter(
            Persona.user_id == user.id,
            Persona.id.in_([match.requester_persona_id, match.target_persona_id])
        ).first()
        return persona.id if persona else None
