"""
Centralized settings via Pydantic Settings. Everything is env-driven —
no hardcoded secrets, no dev-fallback secrets reachable in prod
(see validator on jwt_secret).
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["development", "staging", "production"] = "development"

    # Postgres (async driver)
    database_url: str = Field(..., description="postgresql+asyncpg://user:pass@host:5432/nexus")
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis — token budget counters, rate limiting, SSE fan-out cache
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # CORS — frontend origin(s), comma-separated
    cors_origins: str = "http://localhost:3000"

    # Model providers
    # Model providers. These act as an OPTIONAL platform-wide fallback --
    # if set, any tenant without their own configured key still gets a
    # working default (useful for solo/dev deployments). In a real
    # multi-tenant SaaS deployment, leave these blank and require every
    # tenant to configure their own key via ProviderCredential (see
    # app/services/credential_service.py) -- otherwise every tenant is
    # silently spending from your API budget.
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    default_model_id: str = "claude-sonnet-5"

    # Fernet key encrypting ProviderCredential rows at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Required before any user can save a provider API key through the
    # Configure Models UI -- app/core/crypto.py raises clearly if unset.
    credential_encryption_key: str | None = None

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Sandbox execution (implementation phase).
    #
    # Off by default: turning it on lets the agent run code it wrote itself.
    # That only ever happens inside Docker with networking disabled and the
    # session workspace as the sole writable mount -- app/agents/sandbox.py
    # refuses to execute rather than falling back to the host. Requires the
    # image to be built: docker build -t nexus-sandbox:latest backend/sandbox/
    sandbox_enabled: bool = False
    sandbox_image: str = "nexus-sandbox:latest"
    sandbox_cpu_limit: str = "1.0"
    sandbox_mem_limit: str = "512m"
    sandbox_timeout_seconds: int = 30

    # Where per-session workspaces live (see app/agents/workspace.py). These
    # are working copies bind-mounted into the sandbox; SessionFile rows in
    # Postgres remain the durable record, so this directory is safe to wipe
    # and is deliberately not assumed to survive a redeploy.
    workspace_root: str = "./.nexus-workspaces"

    # LangGraph checkpointer: MemorySaver (default, dev-only -- thread
    # state is lost on process restart) or Postgres-backed (survives
    # restarts, required before staging/production). See app/main.py
    # lifespan for where this is wired up.
    use_postgres_checkpointer: bool = False

    # GitHub OAuth App (Review phase "push to GitHub"). Register one at
    # github.com/settings/developers -- Homepage URL http://localhost:3000,
    # Authorization callback URL {this backend's public URL}/api/integrations/github/callback
    # -- and put the resulting Client ID/Secret here. Left unset, the
    # /integrations/github/authorize route returns a clear "not configured"
    # error rather than a broken redirect; nothing else in the app depends
    # on these being set.
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_oauth_redirect_uri: str = "http://localhost:8000/api/integrations/github/callback"
    # Where the callback sends the browser back to after connecting/failing.
    frontend_base_url: str = "http://localhost:3000"

    # Outbound email (currently only password-reset links).
    #
    # With SMTP_HOST unset, app/services/email_service.py falls back to
    # LOGGING the message instead of sending it -- the reset flow stays fully
    # functional in development without inventing mail credentials, and the
    # link is read from the server log. That fallback refuses to run when
    # ENV=production, so a misconfigured deploy fails loudly instead of
    # silently dropping every reset email.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    smtp_from: str = "Nexus Coder <no-reply@nexus.local>"

    # How long an emailed reset link stays valid.
    password_reset_ttl_minutes: int = 30

    # How long a step-up ("sudo") elevation lasts after the user re-enters
    # their password, before managing provider API keys asks again. Short by
    # design -- see app/core/security.create_sudo_token.
    sudo_ttl_minutes: int = 10

    # Uploaded avatars. Served back as static files from /uploads (see
    # app/main.py) -- only raster image types are accepted and the stored
    # filename is always generated here, never taken from the client.
    upload_root: str = "./.nexus-uploads"
    max_avatar_bytes: int = 2 * 1024 * 1024  # 2 MiB
    # Public origin the stored avatar URL is built against. Separate from
    # frontend_base_url because these files are served BY THE API, so a
    # deployment behind a different public API hostname needs to say so.
    api_base_url: str = "http://localhost:8000"

    # Live preview (Review phase). Off by default for the same reason the
    # build sandbox is: it means Docker starts a NETWORK-ENABLED container
    # running whatever the agent generated. See app/agents/preview.py.
    preview_enabled: bool = False
    preview_image: str = "nexus-preview:latest"
    preview_idle_timeout_minutes: int = 15

    @property
    def checkpointer_conn_string(self) -> str:
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_not_default(cls, v: str) -> str:
        if v.strip().lower() in {"changeme", "secret", "dev-secret"}:
            raise ValueError("jwt_secret must not use a placeholder value")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()