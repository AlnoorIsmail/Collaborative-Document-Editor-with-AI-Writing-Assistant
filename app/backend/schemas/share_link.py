from pydantic import BaseModel, ConfigDict, Field


class ShareLinkCreateRequest(BaseModel):
    document_id: str | int = Field(..., description="Document identifier for the shared document.")
    role: str = Field(..., description="Role granted when the link is redeemed.")
    require_sign_in: bool = Field(
        ..., description="Whether the redeemer must already be authenticated."
    )
    expires_at: str = Field(..., description="UTC timestamp when the link should expire.")

    model_config = ConfigDict(extra="forbid")


class ShareLinkCreateResponse(BaseModel):
    link_id: str = Field(..., description="Prefixed share-link identifier.")
    document_id: str = Field(..., description="Prefixed document identifier.")
    token: str = Field(..., description="Opaque share-link token.")
    role: str = Field(..., description="Role granted when the link is redeemed.")
    require_sign_in: bool = Field(
        ..., description="Whether sign-in is required before redemption."
    )
    expires_at: str = Field(..., description="UTC timestamp when the link expires.")
    revoked: bool = Field(..., description="Whether the share link has been revoked.")


class ShareLinkRedeemResponse(BaseModel):
    document_id: str = Field(..., description="Prefixed document identifier.")
    role: str = Field(..., description="Role granted by the redeemed share link.")
    access_granted: bool = Field(
        ..., description="Whether the current redemption attempt granted access."
    )
