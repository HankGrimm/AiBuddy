"""Tests for the Monad chain layer: MonadService + EIP-191 wallet verification."""
from unittest.mock import patch

from eth_account import Account
from eth_account.messages import encode_defunct

from app.services.monad_service import MonadService, _to_bytes32
from app.services.user_identity_service import _verify_monad_signature


# ---------------------------------------------------------------------------
# EIP-191 signature verification
# ---------------------------------------------------------------------------

def test_verify_signature_accepts_valid_personal_sign():
    acct = Account.create()
    nonce = "a" * 64
    sig = Account.sign_message(encode_defunct(text=nonce), acct.key).signature.hex()
    assert _verify_monad_signature(acct.address, nonce, sig) is True


def test_verify_signature_accepts_unprefixed_hex():
    acct = Account.create()
    nonce = "b" * 64
    sig = Account.sign_message(encode_defunct(text=nonce), acct.key).signature.hex()
    assert _verify_monad_signature(acct.address, nonce, sig.removeprefix("0x")) is True


def test_verify_signature_is_case_insensitive_on_address():
    acct = Account.create()
    nonce = "c" * 64
    sig = Account.sign_message(encode_defunct(text=nonce), acct.key).signature.hex()
    assert _verify_monad_signature(acct.address.lower(), nonce, sig) is True


def test_verify_signature_rejects_other_wallet():
    signer = Account.create()
    other = Account.create()
    nonce = "d" * 64
    sig = Account.sign_message(encode_defunct(text=nonce), signer.key).signature.hex()
    assert _verify_monad_signature(other.address, nonce, sig) is False


def test_verify_signature_rejects_wrong_nonce():
    acct = Account.create()
    sig = Account.sign_message(encode_defunct(text="e" * 64), acct.key).signature.hex()
    assert _verify_monad_signature(acct.address, "f" * 64, sig) is False


def test_verify_signature_rejects_garbage():
    acct = Account.create()
    assert _verify_monad_signature(acct.address, "a" * 64, "not-a-signature") is False
    assert _verify_monad_signature(acct.address, "a" * 64, "0xdeadbeef") is False


# ---------------------------------------------------------------------------
# MonadService — graceful degradation
# ---------------------------------------------------------------------------

def test_bytes32_tag_is_right_padded():
    assert _to_bytes32("stake") == b"stake" + b"\x00" * 27
    assert len(_to_bytes32("x" * 64)) == 32


def test_stake_record_returns_none_without_key():
    with patch("app.services.monad_service._load_private_key", return_value=None):
        result = MonadService().submit_stake_record(
            stake_id="abc", user_wallet="0xabc", amount_mon=1.0, stake_type="dm"
        )
    assert result is None


def test_refund_record_returns_none_on_rpc_failure():
    """Any RPC error must degrade to None rather than raising."""
    acct = Account.create()
    with patch(
        "app.services.monad_service._load_private_key",
        return_value=acct.key.hex(),
    ), patch("web3.Web3.HTTPProvider", side_effect=RuntimeError("boom")):
        result = MonadService().submit_refund_record(
            stake_id="abc", user_wallet=acct.address, amount_mon=1.0
        )
    assert result is None


def test_slash_record_returns_none_on_rpc_failure():
    acct = Account.create()
    with patch(
        "app.services.monad_service._load_private_key",
        return_value=acct.key.hex(),
    ), patch("web3.Web3.HTTPProvider", side_effect=RuntimeError("boom")):
        result = MonadService().submit_slash_record(
            stake_id="abc", user_wallet=acct.address, amount_mon=1.0, reason="no_show"
        )
    assert result is None
