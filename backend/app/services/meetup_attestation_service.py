from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta
import uuid
import secrets
import math

from ..models.attestation import MeetupAttestation, AttestationStatus, AttestationMethod
from ..models.user import User
from ..schemas.attestation import AttestationInitiate, AttestationConfirm
from ..core.errors import AttestationError
from .social_reputation_service import SocialReputationService
from .hcs_anchoring_service import HCSAnchoringService


class MeetupAttestationService:
    def __init__(self, db: Session):
        self.db = db

    def initiate(self, user: User, payload: AttestationInitiate) -> MeetupAttestation:
        token = secrets.token_urlsafe(16) if payload.method in (
            AttestationMethod.QR_CODE, AttestationMethod.BLE_PROXIMITY, AttestationMethod.NFC_TAP
        ) else None

        attestation = MeetupAttestation(
            id=uuid.uuid4(),
            match_id=payload.match_id,
            initiator_user_id=user.id,
            method=payload.method,
            status=AttestationStatus.INITIATED,
            token=token,
            latitude=payload.latitude,
            longitude=payload.longitude,
            escrow_id=payload.escrow_id,
            expires_at=datetime.utcnow() + timedelta(hours=2),
        )
        self.db.add(attestation)
        self.db.commit()
        self.db.refresh(attestation)
        return attestation

    def confirm(self, user: User, attestation_id: UUID, payload: AttestationConfirm) -> MeetupAttestation:
        attestation = self._get_or_404(attestation_id)

        if attestation.status == AttestationStatus.EXPIRED:
            raise AttestationError("Attestation has expired")

        # Validate token if applicable
        if attestation.token and payload.token and attestation.token != payload.token:
            raise AttestationError("Invalid attestation token")

        # Validate proximity if GPS
        if attestation.method == AttestationMethod.GPS_CHECKIN:
            if payload.latitude and payload.longitude:
                dist = self._haversine(attestation.latitude, attestation.longitude, payload.latitude, payload.longitude)
                if dist > 0.1:  # 100m
                    raise AttestationError("Location too far — must be within 100m")

        # Record confirmation side
        if attestation.initiator_user_id == user.id:
            attestation.initiator_confirmed = True
        else:
            attestation.counterparty_user_id = user.id
            attestation.counterparty_confirmed = True

        # If both confirmed → complete
        if attestation.initiator_confirmed and attestation.counterparty_confirmed:
            attestation.status = AttestationStatus.CONFIRMED
            attestation.confirmed_at = datetime.utcnow()
            self._on_confirmed(attestation)

        else:
            attestation.status = AttestationStatus.PENDING_CONFIRM

        self.db.commit()
        self.db.refresh(attestation)
        return attestation

    def verify_proximity(self, user: User, payload: AttestationInitiate) -> MeetupAttestation:
        payload.method = AttestationMethod.GPS_CHECKIN
        return self.initiate(user, payload)

    def get_user_attestations(self, user_id: UUID) -> list[MeetupAttestation]:
        return self.db.query(MeetupAttestation).filter(
            (MeetupAttestation.initiator_user_id == user_id) |
            (MeetupAttestation.counterparty_user_id == user_id)
        ).all()

    def _on_confirmed(self, attestation: MeetupAttestation):
        """Release escrow and update reputation when meetup is confirmed."""
        if attestation.escrow_id:
            from ..models.escrow import Escrow, EscrowStatus
            escrow = self.db.query(Escrow).filter(Escrow.id == attestation.escrow_id).first()
            if escrow:
                escrow.status = EscrowStatus.CONFIRMED
                escrow.resolved_at = datetime.utcnow()

        # Update reputation for both parties
        rep_svc = SocialReputationService(self.db)
        if attestation.initiator_user_id:
            rep_svc.record_meetup_completed(attestation.initiator_user_id)
        if attestation.counterparty_user_id:
            rep_svc.record_meetup_completed(attestation.counterparty_user_id)

        # Anchor to Hedera HCS for immutable auditability
        hcs_msg_id = HCSAnchoringService().anchor_attestation(
            attestation_id=attestation.id,
            match_id=attestation.match_id,
            initiator_user_id=attestation.initiator_user_id,
            counterparty_user_id=attestation.counterparty_user_id,
            method=attestation.method.value if attestation.method else "unknown",
            gps_lat=attestation.latitude,
            gps_lng=attestation.longitude,
        )
        if hcs_msg_id:
            attestation.hcs_message_id = hcs_msg_id

    def _get_or_404(self, attestation_id: UUID) -> MeetupAttestation:
        a = self.db.query(MeetupAttestation).filter(MeetupAttestation.id == attestation_id).first()
        if not a:
            from fastapi import HTTPException
            raise HTTPException(404, "Attestation not found")
        return a

    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        if any(v is None for v in (lat1, lon1, lat2, lon2)):
            return 999
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
