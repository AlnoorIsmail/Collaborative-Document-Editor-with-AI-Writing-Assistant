from pydantic import BaseModel, ConfigDict, Field


EmailField = Field(
    pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    description="User email address.",
)


class AuthUserResponse(BaseModel):
    """Authenticated user details returned by auth endpoints."""

    user_id: int
    email: str = EmailField
    display_name: str


class RegisterRequest(BaseModel):
    """Payload used to create a new user account."""

    email: str = EmailField
    display_name: str = Field(
        min_length=2,
        max_length=255,
        description="Display name shown in document ownership metadata.",
    )
    password: str = Field(
        min_length=8,
        max_length=255,
        description="Plaintext password that will be hashed before storage.",
    )

    model_config = ConfigDict(extra="forbid")


class LoginRequest(BaseModel):
    """Payload used to authenticate an existing user."""

    email: str = EmailField
    password: str = Field(min_length=8, max_length=255)

    model_config = ConfigDict(extra="forbid")


class RefreshTokenRequest(BaseModel):
    """Payload used to exchange a refresh token for a new token pair."""

    refresh_token: str = Field(
        min_length=20,
        description="Previously issued refresh token.",
    )

    model_config = ConfigDict(extra="forbid")


class RegisterResponse(BaseModel):
    """Created user payload returned after successful registration."""

    user_id: int
    email: str = EmailField
    display_name: str
    account_status: str
    created_at: str


class TokenPairResponse(BaseModel):
    """JWT bundle returned after login or refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_in_seconds: int
    refresh_token_expires_in_seconds: int


class LoginResponse(TokenPairResponse):
    """Successful login response containing user details and tokens."""

    user: AuthUserResponse


class RefreshTokenResponse(TokenPairResponse):
    """Successful refresh response containing a rotated token pair."""


class MeResponse(BaseModel):
    """Authenticated user profile returned by protected identity endpoints."""

    user_id: int
    email: str = EmailField
    display_name: str
    account_status: str
