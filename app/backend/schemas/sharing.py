from pydantic import BaseModel, Field


class SharingUserResponse(BaseModel):
    user_id: str = Field(..., description="Prefixed user identifier.")
    email: str = Field(..., description="Email address for the shared user.")
    display_name: str = Field(..., description="Display name for the shared user.")


class SharingCollaboratorResponse(BaseModel):
    permission_id: str = Field(..., description="Prefixed permission identifier.")
    user: SharingUserResponse
    role: str = Field(..., description="Current document role.")
    ai_allowed: bool = Field(..., description="Whether AI is enabled for this user.")
    granted_at: str = Field(..., description="UTC time when the access was granted.")


class SharingInvitationResponse(BaseModel):
    invitation_id: str = Field(..., description="Prefixed invitation identifier.")
    invited_email: str = Field(..., description="Email address for the invitee.")
    role: str = Field(..., description="Pending invitation role.")
    status: str = Field(..., description="Invitation workflow status.")
    created_at: str = Field(..., description="UTC time when the invitation was created.")
    expires_at: str = Field(..., description="UTC time when the invitation expires.")


class SharingLinkResponse(BaseModel):
    link_id: str = Field(..., description="Prefixed share link identifier.")
    token: str = Field(..., description="Opaque share link token.")
    role: str = Field(..., description="Role granted by the link.")
    require_sign_in: bool = Field(
        ..., description="Whether sign-in is required before redeeming the link."
    )
    revoked: bool = Field(..., description="Whether the link has been revoked.")
    created_at: str = Field(..., description="UTC time when the link was created.")
    expires_at: str = Field(..., description="UTC time when the link expires.")


class SharingOverviewResponse(BaseModel):
    document_id: str = Field(..., description="Prefixed document identifier.")
    owner: SharingUserResponse
    collaborators: list[SharingCollaboratorResponse]
    invitations: list[SharingInvitationResponse]
    share_links: list[SharingLinkResponse]
