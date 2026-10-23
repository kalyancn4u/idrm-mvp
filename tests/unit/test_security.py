"""Password hashing + JWT round-trip."""

from __future__ import annotations

import pytest


def test_password_hash_roundtrip():
    from shared.security import hash_password, verify_password

    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong", h)


def test_password_hash_is_bcrypt_cost_12():
    from shared.security import hash_password
    assert hash_password("x").startswith("$2b$12$")


def test_jwt_roundtrip(tmp_path, monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (tmp_path / "priv.pem").write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    (tmp_path / "pub.pem").write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(tmp_path / "priv.pem"))
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(tmp_path / "pub.pem"))

    from shared.config import get_settings
    get_settings.cache_clear()

    from shared.security import create_access_token, decode_token

    token, expires_in = create_access_token("u-123", "citizen", "sess-1", 1)
    claims = decode_token(token, expected_typ="access")
    assert claims["sub"] == "u-123"
    assert claims["sid"] == "sess-1"
    assert claims["ver"] == 1
    assert expires_in > 0


def test_refresh_token_cannot_be_used_as_access(tmp_path, monkeypatch):
    import jwt as pyjwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (tmp_path / "priv.pem").write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    (tmp_path / "pub.pem").write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(tmp_path / "priv.pem"))
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(tmp_path / "pub.pem"))

    from shared.config import get_settings
    get_settings.cache_clear()

    from shared.security import create_refresh_token, decode_token

    refresh, _ = create_refresh_token("u-123", "citizen", "sess-1", "fam-1")
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(refresh, expected_typ="access")


def test_jitter_spreads_expiries(tmp_path, monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (tmp_path / "priv.pem").write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    (tmp_path / "pub.pem").write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(tmp_path / "priv.pem"))
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(tmp_path / "pub.pem"))

    from shared.config import get_settings
    get_settings.cache_clear()

    from shared.security import create_access_token

    exps = {create_access_token("u", "citizen", "s", 1)[1] for _ in range(20)}
    # With ±20 min jitter on 120 min base, we expect multiple distinct values
    assert len(exps) > 5

