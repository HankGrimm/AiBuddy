import pytest
import uuid

from app.models.user import User
from app.models.report import Report, ReportStatus, ReportType
from app.models.block import Block
from app.services.report_service import ReportService, REPEAT_OFFENDER_THRESHOLD
from app.services.block_service import BlockService
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
# Report service tests
# ---------------------------------------------------------------------------

def test_file_report_creates_record(db):
    ModerationQueueService.clear()
    reporter = _make_user(db)
    reported = _make_user(db)

    svc = ReportService(db)
    report = svc.create(reporter.id, _report_create(reported.id))

    assert report.id is not None
    assert report.reporter_id == reporter.id
    assert report.reported_user_id == reported.id
    assert report.status == ReportStatus.PENDING

    # Confirm persisted
    fetched = svc.get_by_id(report.id)
    assert fetched is not None
    assert fetched.id == report.id


def test_repeat_offender_flagged_at_3_reports(db):
    ModerationQueueService.clear()
    svc = ReportService(db)
    reported = _make_user(db)

    # File REPEAT_OFFENDER_THRESHOLD reports from different reporters
    for _ in range(REPEAT_OFFENDER_THRESHOLD):
        reporter = _make_user(db)
        svc.create(reporter.id, _report_create(reported.id))

    assert svc.is_repeat_offender(reported.id) is True


def test_get_reports_for_user(db):
    ModerationQueueService.clear()
    reporter = _make_user(db)
    svc = ReportService(db)

    for _ in range(3):
        target = _make_user(db)
        svc.create(reporter.id, _report_create(target.id))

    reports = svc.get_for_user(reporter.id)
    assert len(reports) == 3


def test_resolve_report_updates_reputation(db):
    ModerationQueueService.clear()
    reporter = _make_user(db)
    reported = _make_user(db)
    resolver = _make_user(db)

    svc = ReportService(db)
    report = svc.create(reporter.id, _report_create(reported.id))

    resolved = svc.resolve(
        report_id=report.id,
        resolver_id=resolver.id,
        notes="Confirmed harassment, user warned.",
        action="warned",
    )

    assert resolved.status == ReportStatus.RESOLVED
    assert resolved.resolution_notes == "Confirmed harassment, user warned."
    assert resolved.resolved_at is not None


def test_underage_report_deactivates_account(db):
    ModerationQueueService.clear()
    reporter = _make_user(db)
    reported = _make_user(db)
    assert reported.is_active is True

    svc = ReportService(db)
    svc.create(reporter.id, _report_create(reported.id, ReportType.UNDERAGE_USER))

    db.refresh(reported)
    assert reported.is_active is False

    # Moderation queue should have a HIGH severity item
    mod_svc = ModerationQueueService()
    pending = mod_svc.get_pending()
    assert any(item["severity"] == "HIGH" for item in pending)


# ---------------------------------------------------------------------------
# Block service tests
# ---------------------------------------------------------------------------

def test_block_user(db):
    blocker = _make_user(db)
    blocked = _make_user(db)

    svc = BlockService(db)
    block = svc.block(blocker.id, blocked.id)

    assert block.id is not None
    assert block.blocker_id == blocker.id
    assert block.blocked_id == blocked.id


def test_block_is_bidirectional(db):
    user_a = _make_user(db)
    user_b = _make_user(db)

    svc = BlockService(db)
    # Only A blocks B
    svc.block(user_a.id, user_b.id)

    # Both directions should return True
    assert svc.is_blocked(user_a.id, user_b.id) is True
    assert svc.is_blocked(user_b.id, user_a.id) is True


def test_unblock_user(db):
    blocker = _make_user(db)
    blocked = _make_user(db)

    svc = BlockService(db)
    svc.block(blocker.id, blocked.id)
    assert svc.is_blocked(blocker.id, blocked.id) is True

    svc.unblock(blocker.id, blocked.id)
    assert svc.is_blocked(blocker.id, blocked.id) is False


def test_get_blocked_ids(db):
    blocker = _make_user(db)
    targets = [_make_user(db) for _ in range(3)]

    svc = BlockService(db)
    for t in targets:
        svc.block(blocker.id, t.id)

    blocked_ids = svc.get_blocked_ids(blocker.id)
    assert set(blocked_ids) == {t.id for t in targets}
