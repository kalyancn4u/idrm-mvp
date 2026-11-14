"""
Single source of truth for settings — read once, cached for the process.

Both the FastAPI app and the Flask dashboard import from here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings sourced from the environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- App --------------------------------------------------------------
    app_env: str = "development"
    app_name: str = "IDRM"
    app_tagline: str = "Integrated Disaster Response Management"
    log_level: str = "INFO"
    default_language: str = "en"
    allowed_origins: str = "http://127.0.0.1:8000,http://127.0.0.1:5000"
    # Set to true ONLY when the app sits behind a reverse proxy you control
    # that overwrites X-Forwarded-For. Otherwise the header is caller-supplied
    # and must not be believed.
    trust_forwarded_for: bool = False

    # ---- Database ---------------------------------------------------------
    database_url: str = "postgresql+asyncpg://idrm_user:idrm_pass@127.0.0.1:5432/idrm_db"
    database_url_sync: str = "postgresql+psycopg2://idrm_user:idrm_pass@127.0.0.1:5432/idrm_db"

    # ---- Redis (optional) -------------------------------------------------
    redis_url: str = "redis://127.0.0.1:6379/0"

    # ---- JWT --------------------------------------------------------------
    jwt_private_key_path: str = "keys/jwt_private.pem"
    jwt_public_key_path: str = "keys/jwt_public.pem"

    jwt_access_ttl_citizen_min: int = 120
    jwt_access_ttl_provider_min: int = 120
    jwt_access_ttl_coordinator_min: int = 60
    jwt_access_ttl_admin_min: int = 30

    jwt_access_jitter_citizen_min: int = 20
    jwt_access_jitter_provider_min: int = 20
    jwt_access_jitter_coordinator_min: int = 10
    jwt_access_jitter_admin_min: int = 5

    jwt_refresh_ttl_citizen_days: int = 180
    jwt_refresh_ttl_provider_days: int = 180
    jwt_refresh_ttl_coordinator_days: int = 90
    jwt_refresh_ttl_admin_days: int = 30

    jwt_refresh_jitter_citizen_days: int = 7
    jwt_refresh_jitter_provider_days: int = 7
    jwt_refresh_jitter_coordinator_days: int = 5
    jwt_refresh_jitter_admin_days: int = 3

    # ---- Session limits ---------------------------------------------------
    session_limit_citizen: int = 2
    session_limit_provider: int = 3
    session_limit_coordinator: int = 3
    session_limit_admin: int = 2

    session_idle_citizen_hours: int = 2160
    session_idle_provider_hours: int = 2160
    session_idle_coordinator_hours: int = 12
    session_idle_admin_hours: int = 4

    session_cache_ttl_seconds: int = 60

    # ---- Auto-approval ----------------------------------------------------
    auto_approval_enabled: bool = True
    auto_approval_policy_cache_ttl: int = 60
    auto_approval_region_cache_ttl: int = 300
    auto_approval_list_cache_ttl: int = 30

    # ---- Object storage ---------------------------------------------------
    s3_endpoint: str = "http://127.0.0.1:9000"
    s3_bucket: str = "idrm-uploads"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"

    file_max_bytes: int = 10 * 1024 * 1024
    image_max_dimension: int = 1920

    # ---- Flask dashboard --------------------------------------------------
    dashboard_secret_key: str = "change-me-dashboard"
    dashboard_session_cookie_secure: bool = False
    dashboard_session_lifetime_minutes: int = 480
    dashboard_allowed_roles: str = "coordinator,admin"

    # ---- First admin (used once, by migration 0003) -----------------------
    admin_initial_password: str = ""

    # ---- Seed -------------------------------------------------------------
    seed_password: str = "IDRMseed#2026"

    # ---- Derived ----------------------------------------------------------
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def dashboard_roles(self) -> list[str]:
        return [r.strip() for r in self.dashboard_allowed_roles.split(",") if r.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def insecure_defaults(self) -> list[str]:
        """Names of settings still at a publicly known default value."""
        bad = []
        if self.dashboard_secret_key.startswith("change-me"):
            bad.append("DASHBOARD_SECRET_KEY")
        if not self.dashboard_session_cookie_secure:
            bad.append("DASHBOARD_SESSION_COOKIE_SECURE")
        if self.s3_secret_key == "minioadmin":
            bad.append("S3_SECRET_KEY")
        if ":idrm_pass@" in self.database_url or ":idrm_pass@" in self.database_url_sync:
            bad.append("DATABASE_URL / DATABASE_URL_SYNC (default password)")
        return bad

    def require_safe_for_production(self) -> None:
        """Refuse to start in production while development defaults are in use."""
        if self.is_production and (bad := self.insecure_defaults()):
            raise RuntimeError(
                "APP_ENV=production but these settings are still development "
                "defaults: " + ", ".join(bad)
            )

    def access_ttl_minutes(self, role: str) -> int:
        return getattr(self, f"jwt_access_ttl_{role}_min", 60)

    def access_jitter_minutes(self, role: str) -> int:
        return getattr(self, f"jwt_access_jitter_{role}_min", 10)

    def refresh_ttl_days(self, role: str) -> int:
        return getattr(self, f"jwt_refresh_ttl_{role}_days", 30)

    def refresh_jitter_days(self, role: str) -> int:
        return getattr(self, f"jwt_refresh_jitter_{role}_days", 3)

    def session_limit(self, role: str) -> int:
        return getattr(self, f"session_limit_{role}", 3)

    def session_idle_hours(self, role: str) -> int:
        return getattr(self, f"session_idle_{role}_hours", 24)


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached Settings instance."""
    return Settings()
