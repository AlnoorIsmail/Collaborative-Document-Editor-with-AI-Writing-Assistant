from datetime import datetime, timedelta, timezone

from app.backend.models.document_permission import DocumentPermission
from app.backend.models.share_link import ShareLink
from app.backend.tests.conftest import create_test_client
from app.backend.tests.test_documents import create_user_and_token


def _future_timestamp(days=5):
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_owner_can_create_share_link() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post(
        "/v1/share-links",
        json={
            "document_id": "doc_{id}".format(id=create_document.json()["document_id"]),
            "role": "viewer",
            "require_sign_in": False,
            "expires_at": _future_timestamp(),
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    assert response.status_code == 201
    assert response.json()["link_id"] == "link_1"
    assert response.json()["document_id"] == "doc_1"
    assert response.json()["role"] == "viewer"
    assert response.json()["require_sign_in"] is False
    assert response.json()["revoked"] is False
    assert response.json()["token"]


def test_non_owner_cannot_create_share_link() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(client, "stranger@example.com", "Stranger")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post(
        "/v1/share-links",
        json={
            "document_id": "doc_{id}".format(id=create_document.json()["document_id"]),
            "role": "viewer",
            "require_sign_in": False,
            "expires_at": _future_timestamp(),
        },
        headers={"Authorization": "Bearer {token}".format(token=stranger_token)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this document.",
        "retryable": False,
    }


def test_redeem_works_for_non_sign_in_link() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    create_link = client.post(
        "/v1/share-links",
        json={
            "document_id": "doc_{id}".format(id=create_document.json()["document_id"]),
            "role": "viewer",
            "require_sign_in": False,
            "expires_at": _future_timestamp(),
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post("/v1/share-links/{token}/redeem".format(token=create_link.json()["token"]))

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "doc_1",
        "role": "viewer",
        "access_granted": True,
    }


def test_redeem_requires_auth_when_require_sign_in_true() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    create_link = client.post(
        "/v1/share-links",
        json={
            "document_id": "doc_{id}".format(id=create_document.json()["document_id"]),
            "role": "viewer",
            "require_sign_in": True,
            "expires_at": _future_timestamp(),
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post("/v1/share-links/{token}/redeem".format(token=create_link.json()["token"]))

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "UNAUTHORIZED",
        "message": "Authentication is required to redeem this share link.",
        "retryable": False,
    }


def test_expired_link_is_rejected() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    create_link = client.post(
        "/v1/share-links",
        json={
            "document_id": "doc_{id}".format(id=create_document.json()["document_id"]),
            "role": "viewer",
            "require_sign_in": False,
            "expires_at": _future_timestamp(),
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    db = client.session_factory()
    try:
        share_link = db.query(ShareLink).filter(ShareLink.id == 1).first()
        share_link.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.add(share_link)
        db.commit()
    finally:
        db.close()

    response = client.post("/v1/share-links/{token}/redeem".format(token=create_link.json()["token"]))

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "SHARE_LINK_EXPIRED",
        "message": "Share link has expired.",
        "retryable": False,
    }


def test_revoked_link_is_rejected() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    create_link = client.post(
        "/v1/share-links",
        json={
            "document_id": "doc_{id}".format(id=create_document.json()["document_id"]),
            "role": "viewer",
            "require_sign_in": False,
            "expires_at": _future_timestamp(),
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    db = client.session_factory()
    try:
        share_link = db.query(ShareLink).filter(ShareLink.id == 1).first()
        share_link.revoked = True
        db.add(share_link)
        db.commit()
    finally:
        db.close()

    response = client.post("/v1/share-links/{token}/redeem".format(token=create_link.json()["token"]))

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "SHARE_LINK_REVOKED",
        "message": "Share link has been revoked.",
        "retryable": False,
    }


def test_authenticated_redeem_updates_or_creates_permission_when_require_sign_in_true() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    invited_user, invited_token = create_user_and_token(client, "viewer@example.com", "Viewer")
    create_document = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    create_link = client.post(
        "/v1/share-links",
        json={
            "document_id": "doc_{id}".format(id=create_document.json()["document_id"]),
            "role": "viewer",
            "require_sign_in": True,
            "expires_at": _future_timestamp(),
        },
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post(
        "/v1/share-links/{token}/redeem".format(token=create_link.json()["token"]),
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "doc_1",
        "role": "viewer",
        "access_granted": True,
    }

    db = client.session_factory()
    try:
        permission = (
            db.query(DocumentPermission)
            .filter(DocumentPermission.document_id == 1, DocumentPermission.user_id == invited_user["user_id"])
            .first()
        )
        assert permission is not None
        assert permission.role == "viewer"
        assert permission.ai_allowed is False
    finally:
        db.close()
