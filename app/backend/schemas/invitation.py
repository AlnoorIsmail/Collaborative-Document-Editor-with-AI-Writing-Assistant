from pydantic import BaseModel, ConfigDict, Field


EmailField = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvitationCreateRequest(BaseModel):
    invited_email: str = EmailField
    role: str

    model_config = ConfigDict(extra="forbid")


class InvitationCreateResponse(BaseModel):
    invitation_id: str
    document_id: str
    invited_email: str = EmailField
    role: str
    status: str
    expires_at: str


class InvitationAcceptResponse(BaseModel):
    invitation_id: str
    status: str
    document_id: str
    role: str
