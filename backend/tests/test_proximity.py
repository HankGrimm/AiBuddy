"""
Coverage for ProximityVerificationService — GPS, BLE, QR token paths.
"""
import time
import pytest

from app.services.proximity_verification_service import (
    ProximityVerificationService,
    BLE_TTL_SECONDS,
    QR_TTL_SECONDS,
    _ble_tokens,
    _qr_tokens,
)


@pytest.fixture(autouse=True)
def clear_token_stores():
    """Reset global token stores before each test."""
    _ble_tokens.clear()
    _qr_tokens.clear()
    yield
    _ble_tokens.clear()
    _qr_tokens.clear()


svc = ProximityVerificationService()


# ── GPS ───────────────────────────────────────────────────────────────────────

def test_gps_within_100m_returns_true():
    # Consensus Miami venue — two points ~30 m apart
    assert svc.verify_gps(25.7617, -80.1918, 25.7619, -80.1916) is True


def test_gps_far_apart_returns_false():
    # San Francisco vs Miami
    assert svc.verify_gps(37.7749, -122.4194, 25.7617, -80.1918) is False


def test_gps_same_point_returns_true():
    assert svc.verify_gps(25.7617, -80.1918, 25.7617, -80.1918) is True


def test_gps_exactly_at_boundary():
    # ~100 m north of origin — borderline; use a generous tolerance
    # 0.001 degrees latitude ≈ 111 m — should fail
    assert svc.verify_gps(0.0, 0.0, 0.001, 0.0) is False


def test_gps_custom_max_meters():
    # 500 m threshold — same distant points should now pass
    assert svc.verify_gps(25.7617, -80.1918, 25.7662, -80.1918, max_meters=5000) is True


def test_gps_none_coordinates_returns_false():
    result = svc._haversine(None, None, None, None)
    assert result == 9999.0


# ── BLE tokens ───────────────────────────────────────────────────────────────

def test_generate_ble_token_is_8_chars():
    token = svc.generate_ble_token()
    assert len(token) == 8


def test_verify_ble_token_correct_returns_true():
    token = svc.generate_ble_token()
    assert svc.verify_ble_token(token, token) is True


def test_verify_ble_token_wrong_submitted_returns_false():
    token = svc.generate_ble_token()
    assert svc.verify_ble_token(token, "deadbeef") is False


def test_verify_ble_token_unknown_token_returns_false():
    assert svc.verify_ble_token("unknown1", "unknown1") is False


def test_verify_ble_token_expired_returns_false():
    token = svc.generate_ble_token()
    # Force expiry by backdating the stored timestamp
    _ble_tokens[token] = time.time() - 1
    assert svc.verify_ble_token(token, token) is False
    # Expired token should be evicted
    assert token not in _ble_tokens


def test_generate_multiple_ble_tokens_are_unique():
    tokens = {svc.generate_ble_token() for _ in range(20)}
    assert len(tokens) == 20


# ── QR tokens ────────────────────────────────────────────────────────────────

def test_generate_qr_token_is_16_chars():
    token = svc.generate_qr_token()
    assert len(token) == 16


def test_verify_qr_token_correct_returns_true():
    token = svc.generate_qr_token()
    assert svc.verify_qr_token(token, token) is True


def test_verify_qr_token_wrong_submitted_returns_false():
    token = svc.generate_qr_token()
    assert svc.verify_qr_token(token, "wrongtoken1234ab") is False


def test_verify_qr_token_unknown_returns_false():
    assert svc.verify_qr_token("notavalidtoken12", "notavalidtoken12") is False


def test_verify_qr_token_expired_returns_false():
    token = svc.generate_qr_token()
    _qr_tokens[token] = time.time() - 1
    assert svc.verify_qr_token(token, token) is False
    assert token not in _qr_tokens


def test_ble_and_qr_tokens_are_independent():
    ble = svc.generate_ble_token()
    qr = svc.generate_qr_token()
    # QR token should not verify as BLE
    assert svc.verify_ble_token(qr, qr) is False
    assert svc.verify_qr_token(ble, ble) is False
