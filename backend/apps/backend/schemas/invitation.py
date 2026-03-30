from pydantic import BaseModel, ConfigDict, EmailStr


class InvitationCreateRequest(BaseModel):
    invited_email: EmailStr
    role: str

    model_config = ConfigDict(extra="forbid")


class InvitationCreateResponse(BaseModel):
    invitation_id: str
    document_id: str
    invited_email: EmailStr
    role: str
    status: str
    expires_at: str


class InvitationAcceptResponse(BaseModel):
    invitation_id: str
    status: str
    document_id: str
    role: str
