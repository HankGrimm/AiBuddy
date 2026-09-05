from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import uuid
import json

from ..models.report import Report, ReportStatus, ReportType
from ..models.user import User
from ..schemas.safety import ReportCreate, ReportResolve


REPEAT_OFFENDER_THRESHOLD = 3


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, reporter_id: UUID, payload: ReportCreate) -> Report:
        prior_count = self.count_against_user(payload.reported_user_id)

        report = Report(
            id=uuid.uuid4(),
            reporter_id=reporter_id,
            reported_user_id=payload.reported_user_id,
            report_type=payload.report_type,
            description=payload.description,
            evidence_urls=json.dumps(payload.evidence_urls or []),
            is_repeat_offender=(prior_count + 1) >= REPEAT_OFFENDER_THRESHOLD,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        self._handle_auto_actions(report)

        return report

    def get_by_id(self, report_id: UUID) -> Report:
        return self.db.query(Report).filter(Report.id == report_id).first()

    def get_for_user(self, user_id: UUID) -> list[Report]:
        return self.db.query(Report).filter(Report.reporter_id == user_id).all()

    def resolve(self, report_id: UUID, resolver_id: UUID, notes: str, action: str) -> Report:
        report = self.get_by_id(report_id)
        if not report:
            from fastapi import HTTPException
            raise HTTPException(404, "Report not found")

        report.status = ReportStatus.RESOLVED
        report.resolution_notes = notes
        report.resolved_at = datetime.utcnow()

        # Update reputation score for reported user
        resolver = self.db.query(User).filter(User.id == resolver_id).first()
        if resolver:
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

    def count_against_user(self, user_id: UUID) -> int:
        return self.db.query(Report).filter(
            Report.reported_user_id == user_id,
            Report.status != ReportStatus.DISMISSED,
        ).count()

    def is_repeat_offender(self, user_id: UUID) -> bool:
        """Returns True if the user has 3 or more unresolved (pending/under_review) reports."""
        count = self.db.query(Report).filter(
            Report.reported_user_id == user_id,
            Report.status.in_([ReportStatus.PENDING, ReportStatus.UNDER_REVIEW]),
        ).count()
        return count >= REPEAT_OFFENDER_THRESHOLD

    def _handle_auto_actions(self, report: Report) -> None:
        from .block_service import BlockService
        from .moderation_queue_service import ModerationQueueService

        mod_svc = ModerationQueueService()
        block_svc = BlockService(self.db)

        if report.report_type == ReportType.UNDERAGE_USER:
            # Immediately deactivate the reported user
            user = self.db.query(User).filter(User.id == report.reported_user_id).first()
            if user:
                user.is_active = False
                self.db.commit()
            mod_svc.enqueue(report.id, severity="HIGH", auto_action="deactivate")

        elif report.report_type == ReportType.SCAM_ATTEMPT:
            mod_svc.enqueue(report.id, severity="HIGH", auto_action="review")

        elif report.is_repeat_offender:
            # Restrict DM by blocking from reporter side, then enqueue for moderation
            if report.reporter_id:
                block_svc.block(report.reporter_id, report.reported_user_id)
            mod_svc.enqueue(report.id, severity="MEDIUM", auto_action="dm_restricted")
