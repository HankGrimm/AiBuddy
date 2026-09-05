"""
Business logic for Moment NFT minting and retrieval.
Refs #17
"""
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..models.moment_nft import MomentNFT, MomentNFTStatus
from ..models.attestation import MeetupAttestation, AttestationStatus
from ..models.user import User
from ..schemas.moment_nft import MintMomentRequest


class MomentNFTService:
    def __init__(self, db: Session):
        self.db = db

    def mint_moment(self, user: User, payload: MintMomentRequest) -> MomentNFT:
        """Create a pending Moment NFT for a confirmed attestation."""
        # Look up the attestation
        attestation = (
            self.db.query(MeetupAttestation)
            .filter(MeetupAttestation.id == payload.attestation_id)
            .first()
        )
        if not attestation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attestation not found",
            )

        # Verify the attestation is confirmed
        if attestation.status != AttestationStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Attestation is not confirmed",
            )

        # Verify the user is a party to the attestation
        if user.id not in (attestation.initiator_user_id, attestation.counterparty_user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are not a party to this attestation",
            )

        # Check for duplicate NFT on same attestation
        existing = (
            self.db.query(MomentNFT)
            .filter(MomentNFT.attestation_id == payload.attestation_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An NFT has already been minted for this attestation",
            )

        nft = MomentNFT(
            owner_id=user.id,
            attestation_id=payload.attestation_id,
            name=payload.name,
            description=payload.description,
            status=MomentNFTStatus.PENDING,
        )
        self.db.add(nft)
        self.db.commit()
        self.db.refresh(nft)
        return nft

    def list_user_moments(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> tuple[list[MomentNFT], int]:
        """Return paginated list of NFTs owned by user."""
        query = self.db.query(MomentNFT).filter(MomentNFT.owner_id == user_id)
        total = query.count()
        items = (
            query
            .order_by(MomentNFT.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total
