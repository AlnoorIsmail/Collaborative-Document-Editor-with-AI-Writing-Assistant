from datetime import datetime, timedelta

from apps.backend.models.document_permission import DocumentPermission
from apps.backend.models.invitation import Invitation
from apps.backend.tests.conftest import create_test_client
from apps.backend.tests.test_documents import create_user_and_token


def test_owner_can_send_invitation() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invited_email": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    assert response.status_code == 201
    assert response.json()["invitation_id"] == "inv_1"
    assert response.json()["document_id"] == "doc_{id}".format(id=document_id)
    assert response.json()["invited_email"] == "editor@example.com"
    assert response.json()["role"] == "commenter"
    assert response.json()["status"] == "pending"
    assert response.json()["expires_at"]


def test_non_owner_cannot_send_invitation() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(client, "stranger@example.com", "Stranger")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invited_email": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=stranger_token)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this document.",
        "retryable": False,
    }


def test_invited_user_with_matching_email_can_accept() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    invited_user, invited_token = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    invitation_response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invited_email": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post(
        "/v1/invitations/{invitation_id}/accept".format(
            invitation_id=invitation_response.json()["invitation_id"],
        ),
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "invitation_id": invitation_response.json()["invitation_id"],
        "status": "accepted",
        "document_id": "doc_{id}".format(id=document_id),
        "role": "commenter",
    }

    db = client.session_factory()
    try:
        permission = (
            db.query(DocumentPermission)
            .filter(DocumentPermission.document_id == document_id, DocumentPermission.user_id == invited_user["user_id"])
            .first()
        )
        assert permission is not None
        assert permission.role == "commenter"
        assert permission.ai_allowed is False
    finally:
        db.close()


def test_wrong_user_cannot_accept() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(client, "stranger@example.com", "Stranger")
    create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    invitation_response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invited_email": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post(
        "/v1/invitations/{invitation_id}/accept".format(
            invitation_id=invitation_response.json()["invitation_id"],
        ),
        headers={"Authorization": "Bearer {token}".format(token=stranger_token)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "FORBIDDEN",
        "message": "You are not allowed to accept this invitation.",
        "retryable": False,
    }


def test_expired_invitation_is_rejected() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, invited_token = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    invitation_response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invited_email": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    db = client.session_factory()
    try:
        invitation = db.query(Invitation).filter(Invitation.id == 1).first()
        invitation.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.add(invitation)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/v1/invitations/{invitation_id}/accept".format(
            invitation_id=invitation_response.json()["invitation_id"],
        ),
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "INVITATION_EXPIRED",
        "message": "Invitation has expired.",
        "retryable": False,
    }


def test_already_accepted_invitation_is_rejected() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, invited_token = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    invitation_response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invited_email": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    accept_url = "/v1/invitations/{invitation_id}/accept".format(
        invitation_id=invitation_response.json()["invitation_id"],
    )

    first_response = client.post(
        accept_url,
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )
    second_response = client.post(
        accept_url,
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json() == {
        "error_code": "INVITATION_ALREADY_PROCESSED",
        "message": "Invitation has already been processed.",
        "retryable": False,
    }
