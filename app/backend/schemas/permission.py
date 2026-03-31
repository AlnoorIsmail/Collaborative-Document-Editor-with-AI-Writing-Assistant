from pydantic import BaseModel, ConfigDict


class PermissionGrantRequest(BaseModel):
    grantee_type: str
    user_id: str
    role: str
    ai_allowed: bool

    model_config = ConfigDict(extra="forbid")


class PermissionResponse(BaseModel):
    permission_id: str
    document_id: str
    grantee_type: str
    user_id: str
    role: str
    ai_allowed: bool
    granted_at: str
