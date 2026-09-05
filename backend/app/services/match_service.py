from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta
import uuid

from ..models.match import Match, MatchStatus, ConsentState
from ..models.persona import Persona
from ..models.user import User
from ..schemas.match import MatchRequest, MatchList
from ..core.errors import MatchNotFoundError, MessagingBlockedError, BlockedUserError
from .persona_service import PersonaService
from .interaction_policy_service import InteractionPolicyService


class MatchService:
    def __init__(self, db: Session):
        self.db = db
        self.persona_svc = PersonaService(db)
        self.policy = InteractionPolicyService(db)

    def request_match(self, user: User, payload: MatchRequest) -> Match:
        # Get requester's active persona
        requester_persona = (
            self.db.query(Persona)
            .filter(Persona.user_id == user.id, Persona.is_active == True)
            .first()
        )
        if not requester_persona:
            from ..core.errors import PersonaNotFoundError
            raise PersonaNotFoundError()

        self.persona_svc.validate_active(requester_persona)

        # Check block status via policy (DRY)
        self.policy.check_can_match(user.id, payload.target_persona_id)

        match = Match(
            id=uuid.uuid4(),
            room_id=payload.room_id,
            requester_persona_id=requester_persona.id,
            target_persona_id=payload.target_persona_id,
            stake_id=payload.stake_id,
            status=MatchStatus.PENDING,
            consent_state=ConsentState.REQUESTED,
            intro_message=payload.intro_message,
            expires_at=datetime.utcnow() + timedelta(hours=48),
        )
        self.db.add(match)
        self.db.commit()
        self.db.refresh(match)
        return match

    def accept(self, user: User, match_id: UUID) -> Match:
        match = self._get_or_404(match_id)
        self._assert_target(user, match)
        match.status = MatchStatus.ACCEPTED
        match.consent_state = ConsentState.GRANTED
        match.responded_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(match)
        return match

    def reject(self, user: User, match_id: UUID) -> Match:
        match = self._get_or_404(match_id)
        self._assert_target(user, match)
        match.status = MatchStatus.REJECTED
        match.responded_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(match)
        return match

    def get_user_matches(self, user: User, skip: int = 0, limit: int = 20) -> MatchList:
        persona_ids = [p.id for p in self.db.query(Persona.id).filter(Persona.user_id == user.id).all()]
        matches = (
            self.db.query(Match)
            .filter(
                (Match.requester_persona_id.in_(persona_ids)) |
                (Match.target_persona_id.in_(persona_ids))
            )
            .offset(skip).limit(limit).all()
        )
        total = len(matches)
        return MatchList(matches=matches, total=total)

    def expire_stale_matches(self) -> int:
        """Set status=EXPIRED for all PENDING matches older than 48 hours.

        Returns the number of matches expired.
        """
        cutoff = datetime.utcnow() - timedelta(hours=48)
        stale = (
            self.db.query(Match)
            .filter(
                Match.status == MatchStatus.PENDING,
                Match.created_at <= cutoff,
            )
            .all()
        )
        for match in stale:
            match.status = MatchStatus.EXPIRED
        if stale:
            self.db.commit()
        return len(stale)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, match_id: UUID) -> Match:
        m = self.db.query(Match).filter(Match.id == match_id).first()
        if not m:
            raise MatchNotFoundError()
        return m

    def _assert_target(self, user: User, match: Match):
        persona = self.db.query(Persona).filter(
            Persona.id == match.target_persona_id,
            Persona.user_id == user.id,
        ).first()
        if not persona:
            from fastapi import HTTPException
            raise HTTPException(403, "Not authorized to respond to this match")
