from types import SimpleNamespace

import pytest
from fastapi import status

from app.backend.core.errors import ApiError
from app.backend.models.document import Document
from app.backend.models.document_permission import DocumentPermission
from app.backend.schemas.common import ErrorCode
from app.backend.services.access_service import (
    DocumentAccessService,
)


class StubDocumentRepository:
    def __init__(self, document: Document | None) -> None:
        self._document = document

    def get_by_id(self, _: int) -> Document | None:
        return self._document


class StubPermissionRepository:
    def __init__(self, permission: DocumentPermission | None) -> None:
        self._permission = permission

    def get_by_document_and_user(
        self, *, document_id: int, user_id: int
    ) -> DocumentPermission | None:
        if (
            self._permission is not None
            and self._permission.document_id == document_id
            and self._permission.user_id == user_id
        ):
            return self._permission
        return None


def build_service(
    *,
    owner_id: int = 10,
    acting_user_id: int = 10,
    role: str | None = None,
    ai_allowed: bool = False,
    ai_enabled: bool = True,
    latest_version_number: int | None = None,
) -> DocumentAccessService:
    latest_version = None
    if latest_version_number is not None:
        latest_version = SimpleNamespace(version_number=latest_version_number)

    document = Document(
        id=1,
        title="Doc",
        content="Content",
        owner_id=owner_id,
        ai_enabled=ai_enabled,
        latest_version=latest_version,
    )
    permission = None
    if role is not None:
        permission = DocumentPermission(
            id=1,
            document_id=document.id,
            user_id=acting_user_id,
            grantee_type="user",
            role=role,
            ai_allowed=ai_allowed,
        )

    return DocumentAccessService(
        StubDocumentRepository(document),
        StubPermissionRepository(permission),
    )


def test_owner_has_full_access_and_current_revision() -> None:
    service = build_service(latest_version_number=7)

    access = service.resolve_access(
        document_id="doc_1",
        user_id=10,
    )

    assert access.role == "owner"
    assert access.user_id == 10
    assert access.can_read is True
    assert access.can_edit is True
    assert access.can_manage is True
    assert access.can_restore_versions is True
    assert access.can_use_ai is True
    assert access.current_revision == 7
    assert service.require_owner_access(document_id="doc_1", user_id=10) == access
    assert service.require_restore_access(document_id="doc_1", user_id=10) == access
    assert service.require_ai_access(document_id="doc_1", user_id=10) == access


def test_editor_can_edit_and_restore_but_cannot_manage_permissions() -> None:
    service = build_service(owner_id=10, acting_user_id=22, role="editor")

    edit_access = service.require_edit_access(document_id=1, user_id=22)
    restore_access = service.require_restore_access(document_id=1, user_id=22)

    assert edit_access.role == "editor"
    assert edit_access.can_read is True
    assert edit_access.can_edit is True
    assert edit_access.can_manage is False
    assert edit_access.can_restore_versions is True
    assert restore_access == edit_access

    with pytest.raises(ApiError) as exc_info:
        service.require_owner_access(document_id=1, user_id=22)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail["error_code"] == ErrorCode.PERMISSION_DENIED


def test_viewer_can_read_but_cannot_edit() -> None:
    service = build_service(owner_id=10, acting_user_id=22, role="viewer")

    access = service.require_read_access(document_id=1, user_id=22)

    assert access.role == "viewer"
    assert access.can_read is True
    assert access.can_edit is False
    assert access.can_manage is False
    assert access.can_restore_versions is False
    assert access.can_use_ai is False

    with pytest.raises(ApiError) as exc_info:
        service.require_edit_access(document_id=1, user_id=22)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail["error_code"] == ErrorCode.PERMISSION_DENIED


def test_missing_permission_for_non_owner_is_denied() -> None:
    service = build_service(owner_id=10, acting_user_id=22, role=None)

    with pytest.raises(ApiError) as exc_info:
        service.require_read_access(document_id=1, user_id=22)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail["error_code"] == ErrorCode.PERMISSION_DENIED


def test_ai_access_requires_enabled_document_and_ai_eligible_access() -> None:
    disabled_owner_service = build_service(
        owner_id=10,
        acting_user_id=10,
        ai_enabled=False,
    )
    editor_with_ai_service = build_service(
        owner_id=10,
        acting_user_id=22,
        role="editor",
        ai_allowed=True,
        ai_enabled=True,
    )
    editor_without_ai_service = build_service(
        owner_id=10,
        acting_user_id=23,
        role="editor",
        ai_allowed=False,
        ai_enabled=True,
    )
    enabled_owner_service = build_service(
        owner_id=10,
        acting_user_id=10,
        ai_enabled=True,
    )

    with pytest.raises(ApiError) as disabled_exc:
        disabled_owner_service.require_ai_access(document_id=1, user_id=10)
    with pytest.raises(ApiError) as editor_exc:
        editor_without_ai_service.require_ai_access(document_id=1, user_id=23)

    allowed_access = enabled_owner_service.require_ai_access(document_id=1, user_id=10)
    editor_access = editor_with_ai_service.require_ai_access(document_id=1, user_id=22)

    assert disabled_exc.value.detail["error_code"] == ErrorCode.AI_DISABLED
    assert editor_exc.value.detail["error_code"] == ErrorCode.AI_ROLE_NOT_ALLOWED
    assert allowed_access.role == "owner"
    assert editor_access.role == "editor"


def test_validate_role_normalizes_supported_roles_and_rejects_invalid_input() -> None:
    service = build_service()

    assert service.validate_role(" Viewer ") == "viewer"
    assert service.validate_role("EDITOR") == "editor"
    assert service.validate_role("commenter") == "commenter"

    with pytest.raises(ApiError) as exc_info:
        service.validate_role("OWNER")

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail["error_code"] == ErrorCode.VALIDATION_ERROR


def test_missing_document_raises_document_not_found() -> None:
    service = DocumentAccessService(
        StubDocumentRepository(None),
        StubPermissionRepository(None),
    )

    with pytest.raises(ApiError) as exc_info:
        service.require_read_access(document_id="doc_999", user_id=1)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail["error_code"] == ErrorCode.DOCUMENT_NOT_FOUND
