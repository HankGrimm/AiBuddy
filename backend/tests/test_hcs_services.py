"""
Tests for HCSAnchoringService.

Covers both stub mode (no credentials) and the live-API path via httpx mock.
"""
import uuid
from unittest.mock import patch, MagicMock


# ── HCSAnchoringService ──────────────────────────────────────────────────────

class TestHCSAnchoringServiceStubMode:
    """When Hedera credentials are absent, all anchors return None (no-op)."""

    def setup_method(self):
        import os
        os.environ.pop("HEDERA_ACCOUNT_ID", None)
        os.environ.pop("HEDERA_PRIVATE_KEY", None)
        os.environ.pop("HEDERA_TOPIC_ID", None)

    def test_anchor_stake_decision_stub(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_stake_decision(
            stake_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            decision="refunded",
            amount_mon=2.0,
        )
        assert result is None

    def test_anchor_safety_action_stub(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_safety_action(
            report_id=uuid.uuid4(),
            reporter_id=uuid.uuid4(),
            reported_user_id=uuid.uuid4(),
            action="suspended",
            category="harassment",
        )
        assert result is None

    def test_anchor_escrow_event_stub(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_escrow_event(
            escrow_id=uuid.uuid4(),
            event="opened",
            user_id=uuid.uuid4(),
            amount_mon=1.0,
        )
        assert result is None

    def test_anchor_attestation_stub(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        result = HCSAnchoringService().anchor_attestation(
            attestation_id=uuid.uuid4(),
            match_id=uuid.uuid4(),
            initiator_user_id=uuid.uuid4(),
            counterparty_user_id=uuid.uuid4(),
            method="gps",
        )
        assert result is None


class TestHCSAnchoringServiceWithCredentials:
    """When credentials are set, the service posts to the Hedera mirror node."""

    def setup_method(self):
        import os
        os.environ["HEDERA_ACCOUNT_ID"] = "0.0.456"
        os.environ["HEDERA_PRIVATE_KEY"] = "test-key"
        os.environ["HEDERA_TOPIC_ID"] = "0.0.123"

    def teardown_method(self):
        import os
        os.environ.pop("HEDERA_ACCOUNT_ID", None)
        os.environ.pop("HEDERA_PRIVATE_KEY", None)
        os.environ.pop("HEDERA_TOPIC_ID", None)

    def test_anchor_attestation_publishes_on_success(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = {"consensus_timestamp": "1712345678.000000001"}
        with patch("httpx.post", return_value=resp) as mock_post:
            result = HCSAnchoringService().anchor_attestation(
                attestation_id=uuid.uuid4(),
                match_id=uuid.uuid4(),
                initiator_user_id=uuid.uuid4(),
                counterparty_user_id=None,
                method="qr",
            )
        assert result == "1712345678.000000001"
        assert "0.0.123" in mock_post.call_args.args[0]

    def test_anchor_stake_decision_publishes_on_success(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"message_id": "abc-123"}
        with patch("httpx.post", return_value=resp):
            result = HCSAnchoringService().anchor_stake_decision(
                stake_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                decision="slashed",
                amount_mon=1.0,
                slash_reason="no_show",
            )
        assert result == "abc-123"

    def test_anchor_safety_action_publishes_on_success(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = {"consensus_timestamp": "1712345678.000000002"}
        with patch("httpx.post", return_value=resp):
            result = HCSAnchoringService().anchor_safety_action(
                report_id=uuid.uuid4(),
                reporter_id=uuid.uuid4(),
                reported_user_id=uuid.uuid4(),
                action="banned",
                category="fraud",
            )
        assert result == "1712345678.000000002"

    def test_anchor_returns_none_on_http_error(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "boom"
        with patch("httpx.post", return_value=resp):
            result = HCSAnchoringService().anchor_escrow_event(
                escrow_id=uuid.uuid4(),
                event="confirmed",
                user_id=uuid.uuid4(),
                amount_mon=1.0,
            )
        assert result is None

    def test_anchor_returns_none_on_exception(self):
        from app.services.hcs_anchoring_service import HCSAnchoringService
        with patch("httpx.post", side_effect=RuntimeError("network down")):
            result = HCSAnchoringService().anchor_attestation(
                attestation_id=uuid.uuid4(),
                match_id=uuid.uuid4(),
                initiator_user_id=uuid.uuid4(),
                counterparty_user_id=None,
                method="gps",
            )
        assert result is None

    def test_missing_topic_id_skips_publish(self):
        import os
        os.environ.pop("HEDERA_TOPIC_ID", None)
        from app.services.hcs_anchoring_service import HCSAnchoringService
        with patch("httpx.post") as mock_post:
            result = HCSAnchoringService().anchor_stake_decision(
                stake_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                decision="refunded",
                amount_mon=1.0,
            )
        assert result is None
        mock_post.assert_not_called()
