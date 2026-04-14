from app.backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)


def test_password_hash_is_not_plaintext() -> None:
    password = "strong-password"

    hashed = get_password_hash(password)

    assert hashed != password
    assert "$" in hashed


def test_verify_password_succeeds_for_valid_password() -> None:
    hashed = get_password_hash("strong-password")

    assert verify_password("strong-password", hashed) is True


def test_verify_password_fails_for_wrong_password() -> None:
    hashed = get_password_hash("strong-password")

    assert verify_password("wrong-password", hashed) is False


def test_access_token_creation_and_decode() -> None:
    token = create_access_token("123")

    payload = decode_access_token(token)

    assert payload["sub"] == "123"
    assert payload["type"] == "access"
    assert payload["exp"] > payload["iat"]


def test_refresh_token_creation_and_decode() -> None:
    token = create_refresh_token("123", jti="refresh-jti")

    payload = decode_refresh_token(token)

    assert payload["sub"] == "123"
    assert payload["type"] == "refresh"
    assert payload["jti"] == "refresh-jti"


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token("123", expires_in_minutes=-1)

    try:
        decode_access_token(token)
    except ValueError as exc:
        assert str(exc) == "Token has expired."
    else:
        raise AssertionError("Expected expired token to be rejected.")
