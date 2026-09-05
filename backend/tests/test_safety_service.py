"""
Coverage boost for SafetyService — targets the file_report/block/resolve paths
that were missed in test_safety.py (which tests ReportService, not SafetyService).
"""
import uuid
import pytest

from app.models.user import User
from app.models.report import ReportType, ReportStatus
from app.services.safety_service import SafetyService
from app.schemas.safety import ReportCreate, ReportResolve


def _make_user(db) -> User:
    u = User(id=uuid.uuid4(), wallet_address=f"w_{uuid.uuid4().hex[:8]}", is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _report_payload(reported_id, report_type=ReportType.HARASSMENT):
    return ReportCreate(
        reported_user_id=reported_id,
        report_type=report_type,
        description="Test report description long enough to pass validation.",
        evidence_urls=[],
    )


# ── file_report ──────────────────────────────────────────────────────────────

def test_file_report_creates_record(db):
    reporter = _make_user(db)
    reported = _make_user(db)
    svc = SafetyService(db)

    report = svc.file_report(reporter, _report_payload(reported.id))

    assert report.id is not None
    assert report.reporter_id == reporter.id
    assert report.reported_user_id == reported.id
    assert report.status == ReportStatus.PENDING
    assert report.is_repeat_offender is False


def test_file_report_marks_repeat_offender(db):
    """After 3 prior reports against the same user, is_repeat_offender = True."""
    svc = SafetyService(db)
    reported = _make_user(db)

    # File 3 reports from different reporters
    for _ in range(3):
        reporter = _make_user(db)
        svc.file_report(reporter, _report_payload(reported.id))

    # 4th report should be flagged
    new_reporter = _make_user(db)
    report = svc.file_report(new_reporter, _report_payload(reported.id))
    assert report.is_repeat_offender is True


def test_file_report_stores_evidence_urls(db):
    reporter = _make_user(db)
    reported = _make_user(db)
    svc = SafetyService(db)

    payload = ReportCreate(
        reported_user_id=reported.id,
        report_type=ReportType.SPAM,
        description="Spam evidence attached.",
        evidence_urls=["https://example.com/evidence1.png"],
    )
    report = svc.file_report(reporter, payload)
    assert report.id is not None
    # evidence_urls stored as JSON string
    assert "evidence1" in (report.evidence_urls or "")


# ── block_user ───────────────────────────────────────────────────────────────

def test_block_user_creates_block(db):
    blocker = _make_user(db)
    blocked = _make_user(db)
    svc = SafetyService(db)

    block = svc.block_user(blocker, blocked.id)

    assert block.id is not None
    assert block.blocker_id == blocker.id
    assert block.blocked_id == blocked.id


def test_block_user_idempotent(db):
    """Blocking the same user twice returns existing block without duplicating."""
    blocker = _make_user(db)
    blocked = _make_user(db)
    svc = SafetyService(db)

    b1 = svc.block_user(blocker, blocked.id)
    b2 = svc.block_user(blocker, blocked.id)

    assert b1.id == b2.id


# ── get_reports_for_user ──────────────────────────────────────────────────────

def test_get_reports_for_user(db):
    reporter = _make_user(db)
    svc = SafetyService(db)

    for _ in range(3):
        target = _make_user(db)
        svc.file_report(reporter, _report_payload(target.id))

    reports = svc.get_reports_for_user(reporter)
    assert len(reports) == 3


def test_get_reports_for_user_empty(db):
    reporter = _make_user(db)
    svc = SafetyService(db)
    assert svc.get_reports_for_user(reporter) == []


# ── resolve_report ────────────────────────────────────────────────────────────

def test_resolve_report_sets_status_resolved(db):
    reporter = _make_user(db)
    reported = _make_user(db)
    resolver = _make_user(db)
    svc = SafetyService(db)

    report = svc.file_report(reporter, _report_payload(reported.id))
    resolved = svc.resolve_report(
        resolver,
        report.id,
        ReportResolve(resolution_notes="Warned user.", action_taken="warned"),
    )

    assert resolved.status == ReportStatus.RESOLVED
    assert resolved.resolution_notes == "Warned user."
    assert resolved.resolved_at is not None


def test_resolve_report_not_found_raises_404(db):
    resolver = _make_user(db)
    svc = SafetyService(db)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        svc.resolve_report(resolver, uuid.uuid4(), ReportResolve(resolution_notes="not found test", action_taken="dismissed"))
    assert exc.value.status_code == 404
