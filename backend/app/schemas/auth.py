from pydantic import EmailStr, Field, field_validator

from app.schemas.base import CamelModel


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    name: str | None = None
    tenant_name: str | None = Field(default=None, max_length=80)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.isdigit() or v.isalpha():
            raise ValueError("password must mix letters and numbers/symbols")
        return v


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class RefreshRequest(CamelModel):
    refresh_token: str


class UserOut(CamelModel):
    id: str
    email: str
    name: str | None
    avatar_url: str | None
    github_username: str | None = None


class TenantOut(CamelModel):
    id: str
    name: str
    slug: str
    plan: str
    token_budget: int | None = None


class PreferencesOut(CamelModel):
    default_mode: str
    default_model_id: str | None
    theme: str


class AuthResponse(CamelModel):
    token: str
    refresh_token: str
    user: UserOut
    tenant: TenantOut | None


class MeResponse(CamelModel):
    user: UserOut
    tenant: TenantOut | None
    preferences: PreferencesOut | None