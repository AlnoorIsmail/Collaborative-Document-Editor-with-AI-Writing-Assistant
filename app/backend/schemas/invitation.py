from pydantic import AliasChoices, BaseModel, ConfigDict, Field


EmailField = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvitationCreateRequest(BaseModel):
    invitee: str = Field(
        min_length=3,
        max_length=255,
        validation_alias=AliasChoices("invitee", "invited_email"),
        serialization_alias="invitee",
        description="Email address or username of the registered user being invited.",
    )
    role: str = Field(description="Role the invited user will receive after accepting.")

    model_config = ConfigDict(extra="forbid")


class InvitationCreateResponse(BaseModel):
    invitation_id: str = Field(..., description="Prefixed invitation identifier.")
    document_id: str = Field(..., description="Prefixed document identifier.")
    invited_email: str = EmailField
    role: str = Field(..., description="Role offered by the invitation.")
    status: str = Field(..., description="Current invitation workflow state.")
    expires_at: str = Field(..., description="UTC time when the invitation expires.")


class InvitationAcceptResponse(BaseModel):
    invitation_id: str = Field(..., description="Prefixed invitation identifier.")
    status: str = Field(..., description="Updated invitation workflow state.")
    document_id: str = Field(..., description="Prefixed document identifier.")
    role: str = Field(..., description="Role granted by the accepted invitation.")


class InvitationInviterResponse(BaseModel):
    user_id: str = Field(..., description="Prefixed inviter user identifier.")
    email: str = Field(..., description="Inviter email address.")
    username: str | None = Field(
        default=None,
        description="Inviter username when available.",
    )
    display_name: str = Field(..., description="Display name shown for the inviter.")


class InvitationInboxItemResponse(BaseModel):
    invitation_id: str = Field(..., description="Prefixed invitation identifier.")
    document_id: str = Field(..., description="Prefixed document identifier.")
    document_title: str = Field(..., description="Current document title.")
    role: str = Field(..., description="Role being offered to the recipient.")
    invited_email: str = EmailField
    inviter: InvitationInviterResponse = Field(
        ..., description="Display information for the user who sent the invitation."
    )
    created_at: str = Field(..., description="UTC time when the invitation was created.")
    expires_at: str = Field(..., description="UTC time when the invitation expires.")


class InvitationDeclineResponse(BaseModel):
    invitation_id: str = Field(..., description="Prefixed invitation identifier.")
    status: str = Field(..., description="Updated invitation workflow state.")
    document_id: str = Field(..., description="Prefixed document identifier.")
    role: str = Field(..., description="Role that was declined.")
