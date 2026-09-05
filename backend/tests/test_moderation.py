import pytest
import uuid

from app.models.user import User
from app.models.report import ReportType
from app.services.report_service import ReportService
from app.services.moderation_queue_service import ModerationQueueService
from app.schemas.safety import ReportCreate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db, wallet: str = None) -> User:
    user = User(
        id=uuid.uuid4(),
        wallet_address=wallet or f"wallet_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _report_create(reported_user_id, report_type=ReportType.HARASSMENT) -> ReportCreate:
    return ReportCreate(
        reported_user_id=reported_user_id,
        report_type=report_type,
        description="This is a test report description that is long enough.",
        evidence_urls=None,
    )


# ---------------------------------------------------------------------------
# Moderation queue tests
# ---------------------------------------------------------------------------

def test_moderation_queue_enqueue_and_dequeue(db):
    ModerationQueueService.clear()
    mod_svc = ModerationQueueService()

    report_id = uuid.uuid4()
    item = mod_svc.enqueue(report_id, severity="MEDIUM", auto_action="review")

    assert item["id"] is not None
    assert item["report_id"] == str(report_id)
    assert item["severity"] == "MEDIUM"
    assert item["status"] == "pending"

    pending = mod_svc.get_pending()
    assert len(pending) == 1
    assert pending[0]["id"] == item["id"]


def test_moderation_queue_resolve_item(db):
    ModerationQueueService.clear()
    mod_svc = ModerationQueueService()

    report_id = uuid.uuid4()
    reviewer_id = uuid.uuid4()
    item = mod_svc.enqueue(report_id, severity="LOW")

    resolved = mod_svc.resolve_item(
        item_id=item["id"],
        reviewer_id=reviewer_id,
        notes="Reviewed and actioned.",
    )

    assert resolved["status"] == "resolved"
    assert resolved["reviewer_id"] == str(reviewer_id)
    assert resolved["review_notes"] == "Reviewed and actioned."
    assert resolved["resolved_at"] is not None

    # Should no longer appear in pending list
    pending = mod_svc.get_pending()
    assert all(p["id"] != item["id"] for p in pending)


def test_moderation_queue_get_pending_limit(db):
    ModerationQueueService.clear()
    mod_svc = ModerationQueueService()

    for _ in range(25):
        mod_svc.enqueue(uuid.uuid4(), severity="LOW")

    pending = mod_svc.get_pending(limit=10)
    assert len(pending) == 10


def test_scam_report_escalates_to_high_severity(db):
    ModerationQueueService.clear()
    reporter = _make_user(db)
    reported = _make_user(db)

    svc = ReportService(db)
    svc.create(reporter.id, _report_create(reported.id, ReportType.SCAM_ATTEMPT))

    mod_svc = ModerationQueueService()
    pending = mod_svc.get_pending()

    assert len(pending) >= 1
    high_items = [p for p in pending if p["severity"] == "HIGH"]
    assert len(high_items) >= 1


def test_repeat_offender_enqueues_moderation_item(db):
    ModerationQueueService.clear()
    from app.services.report_service import REPEAT_OFFENDER_THRESHOLD
    reported = _make_user(db)
    svc = ReportService(db)

    reporters = [_make_user(db) for _ in range(REPEAT_OFFENDER_THRESHOLD)]
    for reporter in reporters:
        svc.create(reporter.id, _report_create(reported.id))

    mod_svc = ModerationQueueService()
    pending = mod_svc.get_pending()
    # The 3rd report should have triggered a moderation enqueue
    assert len(pending) >= 1
