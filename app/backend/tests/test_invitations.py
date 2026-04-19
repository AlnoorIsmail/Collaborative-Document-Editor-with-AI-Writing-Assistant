from datetime import timedelta

from app.backend.core.contracts import utc_now
from app.backend.models.document_permission import DocumentPermission
from app.backend.models.invitation import Invitation
from app.backend.tests.conftest import create_test_client
from app.backend.tests.test_documents import create_user_and_token


def test_owner_can_send_invitation() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_user_and_token(client, "editor@example.com", "Editor")
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


def test_owner_cannot_invite_email_without_existing_account() -> None:
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
        json={"invited_email": "missing@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "USER_NOT_FOUND",
        "message": "No account exists for this email.",
        "retryable": False,
    }


def test_owner_can_send_invitation_by_username() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_user_and_token(client, "editor@example.com", "Editor Name")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]

    response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invitee": "editor_name", "role": "editor"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    assert response.status_code == 201
    assert response.json()["document_id"] == "doc_{id}".format(id=document_id)
    assert response.json()["invited_email"] == "editor@example.com"
    assert response.json()["role"] == "editor"


def test_non_owner_cannot_send_invitation() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, stranger_token = create_user_and_token(
        client, "stranger@example.com", "Stranger"
    )
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
    invited_user, invited_token = create_user_and_token(
        client, "editor@example.com", "Editor"
    )
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
            .filter(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == invited_user["user_id"],
            )
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
    _, stranger_token = create_user_and_token(
        client, "stranger@example.com", "Stranger"
    )
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
        invitation.expires_at = utc_now() - timedelta(minutes=1)
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


def test_invited_user_can_list_pending_invitations() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    create_user_and_token(client, "editor@example.com", "Editor Name")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Shared Draft", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invitee": "editor_name", "role": "editor"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    _, invited_token = create_user_and_token(
        client, "recipient@example.com", "Recipient"
    )
    response = client.get(
        "/v1/invitations",
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )
    assert response.status_code == 200
    assert response.json() == []

    login_response = client.post(
        "/v1/auth/login",
        json={"email": "editor@example.com", "password": "strong-password"},
    )
    response = client.get(
        "/v1/invitations",
        headers={
            "Authorization": "Bearer {token}".format(
                token=login_response.json()["access_token"]
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "invitation_id": "inv_1",
            "document_id": "doc_{id}".format(id=document_id),
            "document_title": "Shared Draft",
            "role": "editor",
            "invited_email": "editor@example.com",
            "inviter": {
                "user_id": "usr_1",
                "email": "owner@example.com",
                "username": "owner",
                "display_name": "Owner",
            },
            "created_at": response.json()[0]["created_at"],
            "expires_at": response.json()[0]["expires_at"],
        }
    ]


def test_processed_and_expired_invitations_are_excluded_from_inbox() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, invited_token = create_user_and_token(client, "editor@example.com", "Editor")
    first_doc = client.post(
        "/v1/documents",
        json={"title": "Accepted Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    ).json()
    second_doc = client.post(
        "/v1/documents",
        json={"title": "Declined Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    ).json()
    third_doc = client.post(
        "/v1/documents",
        json={"title": "Expired Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    ).json()
    fourth_doc = client.post(
        "/v1/documents",
        json={"title": "Open Doc", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    ).json()

    accepted_invitation = client.post(
        "/v1/documents/{document_id}/invitations".format(
            document_id=first_doc["document_id"]
        ),
        json={"invitee": "editor@example.com", "role": "viewer"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    ).json()
    declined_invitation = client.post(
        "/v1/documents/{document_id}/invitations".format(
            document_id=second_doc["document_id"]
        ),
        json={"invitee": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    ).json()
    client.post(
        "/v1/documents/{document_id}/invitations".format(
            document_id=third_doc["document_id"]
        ),
        json={"invitee": "editor@example.com", "role": "editor"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    open_invitation = client.post(
        "/v1/documents/{document_id}/invitations".format(
            document_id=fourth_doc["document_id"]
        ),
        json={"invitee": "editor@example.com", "role": "editor"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    ).json()

    client.post(
        "/v1/invitations/{invitation_id}/accept".format(
            invitation_id=accepted_invitation["invitation_id"]
        ),
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )
    client.post(
        "/v1/invitations/{invitation_id}/decline".format(
            invitation_id=declined_invitation["invitation_id"]
        ),
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )

    db = client.session_factory()
    try:
        expired_invitation = db.query(Invitation).filter(Invitation.id == 3).first()
        expired_invitation.expires_at = utc_now() - timedelta(minutes=1)
        db.add(expired_invitation)
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/v1/invitations",
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )

    assert response.status_code == 200
    assert [item["invitation_id"] for item in response.json()] == [
        open_invitation["invitation_id"]
    ]


def test_invited_user_can_decline_invitation() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, invited_token = create_user_and_token(client, "editor@example.com", "Editor")
    create_response = client.post(
        "/v1/documents",
        json={"title": "Decline Me", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    invitation_response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invited_email": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post(
        "/v1/invitations/{invitation_id}/decline".format(
            invitation_id=invitation_response.json()["invitation_id"],
        ),
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "invitation_id": invitation_response.json()["invitation_id"],
        "status": "declined",
        "document_id": "doc_{id}".format(id=document_id),
        "role": "commenter",
    }

    inbox_response = client.get(
        "/v1/invitations",
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )
    assert inbox_response.status_code == 200
    assert inbox_response.json() == []


def test_wrong_user_cannot_decline() -> None:
    client = create_test_client()
    _, owner_token = create_user_and_token(client, "owner@example.com", "Owner")
    _, invited_token = create_user_and_token(client, "editor@example.com", "Editor")
    _, stranger_token = create_user_and_token(
        client, "stranger@example.com", "Stranger"
    )
    create_response = client.post(
        "/v1/documents",
        json={"title": "Decline Me", "initial_content": ""},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )
    document_id = create_response.json()["document_id"]
    invitation_response = client.post(
        "/v1/documents/{document_id}/invitations".format(document_id=document_id),
        json={"invited_email": "editor@example.com", "role": "commenter"},
        headers={"Authorization": "Bearer {token}".format(token=owner_token)},
    )

    response = client.post(
        "/v1/invitations/{invitation_id}/decline".format(
            invitation_id=invitation_response.json()["invitation_id"],
        ),
        headers={"Authorization": "Bearer {token}".format(token=stranger_token)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error_code": "FORBIDDEN",
        "message": "You are not allowed to decline this invitation.",
        "retryable": False,
    }

    inbox_response = client.get(
        "/v1/invitations",
        headers={"Authorization": "Bearer {token}".format(token=invited_token)},
    )
    assert inbox_response.status_code == 200
    assert [item["invitation_id"] for item in inbox_response.json()] == [
        invitation_response.json()["invitation_id"]
    ]
