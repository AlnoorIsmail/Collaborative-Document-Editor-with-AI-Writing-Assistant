from pydantic import BaseModel, ConfigDict, EmailStr


class AuthUserResponse(BaseModel):
    user_id: int
    email: EmailStr
    display_name: str


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str
    password: str

    model_config = ConfigDict(extra="forbid")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    model_config = ConfigDict(extra="forbid")


class RegisterResponse(BaseModel):
    user_id: int
    email: EmailStr
    display_name: str
    account_status: str
    created_at: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class MeResponse(BaseModel):
    user_id: int
    email: EmailStr
    display_name: str
    account_status: str
