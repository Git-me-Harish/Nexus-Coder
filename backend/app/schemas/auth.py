from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import CamelModel


def _check_password_strength(v: str) -> str:
    """The one place the password rule lives -- register and change-password
    must not be able to drift apart on what counts as strong enough."""
    if v.isdigit() or v.isalpha():
        raise ValueError("password must mix letters and numbers/symbols")
    return v


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    name: str | None = None
    tenant_name: str | None = Field(default=None, max_length=80)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


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
    bio: str | None = None
    company: str | None = None
    location: str | None = None
    created_at: datetime | None = None
    # Computed on the model (User.has_password), not a column: false means
    # this account was created through GitHub and has no password yet.
    has_password: bool = True


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


class ProfileUpdateRequest(CamelModel):
    name: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=280)
    company: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=80)


class ChangePasswordRequest(CamelModel):
    # Optional because an account created through "Continue with GitHub" has
    # no password to confirm -- that case is setting one for the first time.
    # The service still requires it whenever a password DOES exist.
    current_password: str | None = None
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class SudoRequest(CamelModel):
    password: str


class SudoResponse(CamelModel):
    token: str
    expires_in_minutes: int


class ForgotPasswordRequest(CamelModel):
    email: EmailStr


class ResetPasswordRequest(CamelModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class GithubExchangeRequest(CamelModel):
    code: str


class AvatarResponse(CamelModel):
    avatar_url: str | None


class PreferencesUpdateRequest(CamelModel):
    theme: str | None = None
    default_mode: str | None = None
    default_model_id: str | None = None

    @field_validator("theme")
    @classmethod
    def theme_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in ("light", "dark"):
            raise ValueError("theme must be 'light' or 'dark'")
        return v


class AuthResponse(CamelModel):
    token: str
    refresh_token: str
    user: UserOut
    tenant: TenantOut | None


class MeResponse(CamelModel):
    user: UserOut
    tenant: TenantOut | None
    preferences: PreferencesOut | None