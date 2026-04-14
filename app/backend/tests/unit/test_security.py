from app.backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    generate_refresh_token_id,
    get_password_hash,
    verify_password,
)


def test_password_hash_is_not_plaintext() -> None:
    password = "strong-password"

    hashed_password = get_password_hash(password)

    assert hashed_password != password
    assert "$" in hashed_password


def test_password_verify_succeeds_for_valid_password() -> None:
    hashed_password = get_password_hash("strong-password")

    assert verify_password("strong-password", hashed_password) is True


def test_password_verify_fails_for_wrong_password() -> None:
    hashed_password = get_password_hash("strong-password")

    assert verify_password("wrong-password", hashed_password) is False


def test_access_token_creation_and_decode() -> None:
    token = create_access_token("42")

    payload = decode_access_token(token)

    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert payload["exp"] > payload["iat"]


def test_refresh_token_creation_and_decode() -> None:
    token_id = generate_refresh_token_id()
    token = create_refresh_token("42", token_id=token_id)

    payload = decode_refresh_token(token)

    assert payload["sub"] == "42"
    assert payload["type"] == "refresh"
    assert payload["jti"] == token_id


def test_expired_access_token_is_rejected() -> None:
    token = create_access_token("42", expires_in_minutes=-1)

    try:
        decode_access_token(token)
    except ValueError as exc:
        assert str(exc) == "Token has expired."
    else:
        raise AssertionError("Expected expired access token to be rejected.")


def test_expired_refresh_token_is_rejected() -> None:
    token = create_refresh_token(
        "42", token_id=generate_refresh_token_id(), expires_in_days=-1
    )

    try:
        decode_refresh_token(token)
    except ValueError as exc:
        assert str(exc) == "Token has expired."
    else:
        raise AssertionError("Expected expired refresh token to be rejected.")
