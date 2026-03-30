from pydantic import BaseModel, ConfigDict


class ShareLinkCreateRequest(BaseModel):
    document_id: str
    role: str
    require_sign_in: bool
    expires_at: str

    model_config = ConfigDict(extra="forbid")


class ShareLinkCreateResponse(BaseModel):
    link_id: str
    document_id: str
    token: str
    role: str
    require_sign_in: bool
    expires_at: str
    revoked: bool


class ShareLinkRedeemResponse(BaseModel):
    document_id: str
    role: str
    access_granted: bool
