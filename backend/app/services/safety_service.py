from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import uuid
import json

from ..models.report import Report, ReportStatus
from ..models.block import Block
from ..models.user import User
from ..schemas.safety import ReportCreate, ReportResolve


REPEAT_OFFENDER_THRESHOLD = 3


class SafetyService:
    def __init__(self, db: Session):
        self.db = db

    def file_report(self, reporter: User, payload: ReportCreate) -> Report:
        # Count prior reports against this user
        prior_count = self.db.query(Report).filter(
            Report.reported_user_id == payload.reported_user_id,
            Report.status != ReportStatus.DISMISSED,
        ).count()

        report = Report(
            id=uuid.uuid4(),
            reporter_id=reporter.id,
            reported_user_id=payload.reported_user_id,
            report_type=payload.report_type,
            description=payload.description,
            evidence_urls=json.dumps(payload.evidence_urls or []),
            is_repeat_offender=prior_count >= REPEAT_OFFENDER_THRESHOLD,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        # Auto-escalate repeat offenders
        if report.is_repeat_offender:
            self._escalate(report)

        return report

    def block_user(self, blocker: User, blocked_id: UUID) -> Block:
        existing = self.db.query(Block).filter(
            Block.blocker_id == blocker.id,
            Block.blocked_id == blocked_id,
        ).first()
        if existing:
            return existing

        block = Block(id=uuid.uuid4(), blocker_id=blocker.id, blocked_id=blocked_id)
        self.db.add(block)
        self.db.commit()
        self.db.refresh(block)
        return block

    def get_reports_for_user(self, user: User) -> list[Report]:
        return self.db.query(Report).filter(Report.reporter_id == user.id).all()

    def resolve_report(self, resolver: User, report_id: UUID, payload: ReportResolve) -> Report:
        report = self.db.query(Report).filter(Report.id == report_id).first()
        if not report:
            from fastapi import HTTPException
            raise HTTPException(404, "Report not found")

        report.status = ReportStatus.RESOLVED
        report.resolution_notes = payload.resolution_notes
        report.resolved_at = datetime.utcnow()

        # Update reputation
        from .social_reputation_service import SocialReputationService
        from ..models.reputation import ReputationEventType
        from ..schemas.reputation import FeedbackCreate
        rep_svc = SocialReputationService(self.db)
        rep_svc.record_feedback(
            resolver,
            FeedbackCreate(
                target_user_id=report.reported_user_id,
                reference_id=report.id,
                event_type=ReputationEventType.REPORT_RECEIVED,
            )
        )
        self.db.commit()
        self.db.refresh(report)
        return report

    def _escalate(self, report: Report):
        """Flag repeat offenders for moderation queue."""
        # TODO: push to moderation queue / webhook
        pass
