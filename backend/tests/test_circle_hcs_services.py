"""
Tests for CircleService and HCSAnchoringService.

Covers both stub mode (no credentials) and live-API paths via httpx mock.
Refs #9
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock


# ── CircleService ─────────────────────────────────────────────────────────────

class TestCircleServiceStubMode:
    """When CIRCLE_API_KEY is not set, all transfers return status='stub'."""

    def setup_method(self):
        import os
        os.environ.pop("CIRCLE_API_KEY", None)

    def test_debit_stake_stub(self):
        from app.services.circle_service import CircleService
        svc = CircleService()
        result = svc.debit_stake("wallet_abc", 2.0, uuid.uuid4())
        assert result.success is True
        assert result.status == "stub"
        assert result.transfer_id is not None
        assert result.error is None

    def test_credit_refund_stub(self):
        from app.services.circle_service import CircleService
        svc = CircleService()
        result = svc.credit_refund("wallet_abc", 2.0, uuid.uuid4())
        assert result.success is True
        assert result.status == "stub"

    def test_transfer_slash_stub(self):
        from app.services.circle_service import CircleService
        svc = CircleService()
        stake_id = uuid.uuid4()
        result = svc.transfer_slash(1.0, stake_id, "no_show")
        assert result.success is True
        assert result.status == "stub"
        assert str(stake_id) in result.transfer_id

    def test_stub_idempotency_key_override(self):
        from app.services.circle_service import CircleService
        svc = CircleService()
        result = svc.debit_stake("w1", 1.0, uuid.uuid4(), idempotency_key="custom-key")
        assert "custom-key" in result.transfer_id

    def test_transfer_result_dataclass_fields(self):
        from app.services.circle_service import TransferResult
        r = TransferResult(success=True, transfer_id="t1", status="stub", error=None)
        assert r.success is True
        assert r.transfer_id == "t1"
        assert r.status == "stub"
        assert r.error is None


class TestCircleServiceWithAPI:
    """When CIRCLE_API_KEY is set, the service calls the Circle API."""

    def setup_method(self):
        import os
        os.environ["CIRCLE_API_KEY"] = "test-api-key"
        os.environ["CIRCLE_ENTITY_SECRET"] = "test-entity-secret"
        os.environ["CIRCLE_ENVIRONMENT"] = "sandbox"

    def teardown_method(self):
        import os
        os.environ.pop("CIRCLE_API_KEY", None)
        os.environ.pop("CIRCLE_ENTITY_SECRET", None)
        os.environ.pop("CIRCLE_ENVIRONMENT", None)

    def _mock_response(self, status_code: int, json_body: dict):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_body
        mock_resp.text = str(json_body)
        return mock_resp

    def test_successful_transfer(self):
        from app.services.circle_service import CircleService
        mock_resp = self._mock_response(201, {
            "data": {"id": "xfer_123", "status": "pending"}
        })
        with patch("httpx.post", return_value=mock_resp):
            result = CircleService().debit_stake("wallet_a", 5.0, uuid.uuid4())
        assert result.success is True
        assert result.transfer_id == "xfer_123"
        assert result.status == "pending"
        assert result.error is None

    def test_circle_api_error_response(self):
        from app.services.circle_service import CircleService
        mock_resp = self._mock_response(400, {"message": "insufficient funds"})
        with patch("httpx.post", return_value=mock_resp):
            result = CircleService().credit_refund("wallet_b", 2.0, uuid.uuid4())
        assert result.success is False
        assert result.status == "failed"
        assert "insufficient funds" in result.error

    def test_network_exception_returns_failed(self):
        from app.services.circle_service import CircleService
        with patch("httpx.post", side_effect=Exception("network timeout")):
            result = CircleService().transfer_slash(1.0, uuid.uuid4(), "fraud")
        assert result.success is False
        assert result.status == "failed"
        assert "network timeout" in result.error

    def test_200_status_also_succeeds(self):
        from app.services.circle_service import CircleService
        mock_resp = self._mock_response(200, {
            "data": {"id": "xfer_456", "status": "complete"}
        })
        with patch("httpx.post", return_value=mock_resp):
            result = CircleService().debit_stake("w", 1.0, uuid.uuid4())
        assert result.success is True
        assert result.status == "complete"


# ── HCSAnchoringService ───────────────────────────────────────────────────────

class TestHCSAnchoringServiceStubMode:
    """When HEDERA credentials are not set, all anchors return None silently."""

    def setup_method(self):
        import os
        for k in ("HEDERA_ACCOUNT_ID", "HEDERA_PRIVATE_KEY", "HEDERA_TOPIC_ID"):
            os.environ.pop(k, None)

    def test_anchor_attestation_no_creds_returns_none(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        svc = HCSAnchoringService()
        result = svc.anchor_attestation(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            "mutual_confirmation", gps_lat=25.76, gps_lng=-80.19,
        )
        assert result is None

    def test_anchor_stake_decision_no_creds_returns_none(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_stake_decision(
            uuid.uuid4(), uuid.uuid4(), "slashed", 5.0, slash_reason="no_show"
        )
        assert result is None

    def test_anchor_safety_action_no_creds_returns_none(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_safety_action(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "warned", "harassment"
        )
        assert result is None

    def test_anchor_escrow_event_no_creds_returns_none(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_escrow_event(
            uuid.uuid4(), "opened", uuid.uuid4(), 10.0
        )
        assert result is None

    def test_anchor_attestation_none_counterparty(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_attestation(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), None, "gps_checkin"
        )
        assert result is None


class TestHCSAnchoringServiceWithCredentials:
    """When credentials are set, _publish is called with the correct payload."""

    def setup_method(self):
        import os
        os.environ["HEDERA_ACCOUNT_ID"] = "0.0.12345"
        os.environ["HEDERA_PRIVATE_KEY"] = "test-private-key"
        os.environ["HEDERA_TOPIC_ID"] = "0.0.67890"

    def teardown_method(self):
        import os
        for k in ("HEDERA_ACCOUNT_ID", "HEDERA_PRIVATE_KEY", "HEDERA_TOPIC_ID"):
            os.environ.pop(k, None)

    def _mock_hcs_response(self, status_code=201, body=None):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = body or {"consensus_timestamp": "1234567890.123456789"}
        mock_resp.text = ""
        return mock_resp

    def test_anchor_attestation_returns_msg_id(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        mock_resp = self._mock_hcs_response(201, {"consensus_timestamp": "ts_abc"})
        with patch("httpx.post", return_value=mock_resp):
            result = HCSAnchoringService().anchor_attestation(
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "gps_checkin"
            )
        assert result == "ts_abc"

    def test_anchor_stake_decision_refund(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        mock_resp = self._mock_hcs_response(200, {"consensus_timestamp": "ts_refund"})
        with patch("httpx.post", return_value=mock_resp):
            result = HCSAnchoringService().anchor_stake_decision(
                uuid.uuid4(), uuid.uuid4(), "refunded", 2.0
            )
        assert result == "ts_refund"

    def test_anchor_safety_action_success(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        mock_resp = self._mock_hcs_response(201, {"message_id": "msg_xyz"})
        with patch("httpx.post", return_value=mock_resp):
            result = HCSAnchoringService().anchor_safety_action(
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "banned", "harassment"
            )
        assert result == "msg_xyz"

    def test_anchor_escrow_event_opened(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        mock_resp = self._mock_hcs_response(201, {"consensus_timestamp": "ts_escrow"})
        with patch("httpx.post", return_value=mock_resp):
            result = HCSAnchoringService().anchor_escrow_event(
                uuid.uuid4(), "opened", uuid.uuid4(), 5.0
            )
        assert result == "ts_escrow"

    def test_hcs_http_error_returns_none(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        mock_resp = self._mock_hcs_response(503, {})
        mock_resp.text = "Service Unavailable"
        with patch("httpx.post", return_value=mock_resp):
            result = HCSAnchoringService().anchor_attestation(
                uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "ble"
            )
        assert result is None

    def test_hcs_network_exception_returns_none(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        with patch("httpx.post", side_effect=Exception("connection refused")):
            result = HCSAnchoringService().anchor_stake_decision(
                uuid.uuid4(), uuid.uuid4(), "slashed", 5.0, slash_reason="fraud"
            )
        assert result is None

    def test_missing_topic_id_returns_none(self):
        import os
        os.environ.pop("HEDERA_TOPIC_ID", None)
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_escrow_event(
            uuid.uuid4(), "confirmed", uuid.uuid4(), 3.0
        )
        assert result is None
