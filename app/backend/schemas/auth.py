from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EmailField = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthUserResponse(BaseModel):
    user_id: int = Field(..., description="Numeric user identifier.")
    email: str = Field(
        ...,
        description="Unique login email for the authenticated user.",
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    display_name: str = Field(
        ..., description="Display name shown in document metadata."
    )


class RegisterRequest(BaseModel):
    email: str = Field(
        ...,
        description="Email used to create the account.",
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    display_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(
        ..., min_length=8, description="Raw password to hash securely."
    )

    model_config = ConfigDict(extra="forbid")


class LoginRequest(BaseModel):
    email: str = Field(
        ...,
        description="Previously registered account email.",
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(..., min_length=8)

    model_config = ConfigDict(extra="forbid")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(
        ...,
        description="Valid refresh JWT used to obtain a new access token.",
        min_length=20,
    )

    model_config = ConfigDict(extra="forbid")


class RegisterResponse(BaseModel):
    user_id: int = Field(..., description="Numeric user identifier.")
    email: str = Field(
        ...,
        description="Registered account email.",
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    display_name: str = Field(..., description="Human-friendly display name.")
    account_status: str = Field(..., description="Current backend account status.")
    created_at: str = Field(..., description="ISO-8601 UTC account creation timestamp.")


class TokenPairResponse(BaseModel):
    access_token: str = Field(..., description="Short-lived JWT bearer token.")
    refresh_token: str = Field(
        ...,
        description="Refresh JWT used to rotate the session without re-entering credentials.",
    )
    token_type: Literal["bearer"] = Field(
        default="bearer",
        description="Authorization scheme for the access token.",
    )
    access_token_expires_in: int = Field(
        ...,
        description="Access token lifetime in seconds.",
        ge=1,
    )
    refresh_token_expires_in: int = Field(
        ...,
        description="Refresh token lifetime in seconds.",
        ge=1,
    )


class LoginResponse(TokenPairResponse):
    user: AuthUserResponse


class RefreshResponse(TokenPairResponse):
    user: AuthUserResponse


class MeResponse(BaseModel):
    user_id: int = Field(..., description="Numeric user identifier.")
    email: str = Field(
        ...,
        description="Authenticated account email.",
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    display_name: str = Field(..., description="Display name for the signed-in user.")
    account_status: str = Field(..., description="Current backend account status.")
