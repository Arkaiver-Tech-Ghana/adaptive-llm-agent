import pytest

from adaptive_agent.admin.auth import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from adaptive_agent.admin.base import AdminRole, AdminUser


@pytest.fixture(autouse=True)
def _admin_jwt_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")


def test_hash_password_then_verify_round_trips():
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", password_hash)


def test_verify_password_rejects_wrong_password():
    password_hash = hash_password("correct horse battery staple")
    assert not verify_password("wrong password", password_hash)


def test_create_then_decode_access_token_round_trips():
    user = AdminUser(
        email="owner@kampuscrave.test",
        password_hash="unused",
        role=AdminRole.OWNER,
        business_id="kampuscrave",
    )
    token = create_access_token(user)
    claims = decode_access_token(token)

    assert claims.email == "owner@kampuscrave.test"
    assert claims.role == AdminRole.OWNER
    assert claims.business_id == "kampuscrave"


def test_decode_access_token_rejects_expired_token():
    user = AdminUser(
        email="owner@kampuscrave.test", password_hash="unused", role=AdminRole.OWNER, business_id="kampuscrave"
    )
    already_expired = lambda: 0.0
    token = create_access_token(user, now_fn=already_expired)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_decode_access_token_rejects_tampered_token():
    user = AdminUser(
        email="owner@kampuscrave.test", password_hash="unused", role=AdminRole.OWNER, business_id="kampuscrave"
    )
    token = create_access_token(user)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)
