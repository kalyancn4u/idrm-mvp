"""
Single source of truth for settings — read once, cached for the process.

Both the FastAPI app and the Flask dashboard import from here.

Every setting has a safe default, so an empty `.env` still runs. Change a
value by putting its UPPER_CASE name in `.env` (see `.env.example`). The data
and privacy settings, their defaults and the reasons for them are explained
in docs/design/DATA-CONFIGURATION.md.

Out-of-range values stop start-up with a clear error rather than being
silently clamped: a privacy setting that quietly means something else is
worse than one that refuses to load.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
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
    # Declared but not yet used: no image is resized today (PENDING-TASKS G-3).
    image_max_dimension: int = 1920
    # How long a download link for an uploaded file works. Short, because
    # anyone holding the link can open the file (photos may show faces and
    # house numbers). ADR-0015 / privacy design §8.8.
    file_link_ttl_seconds: int = Field(default=300, ge=60, le=3600)

    # ---- Privacy (ADR-0015) — used now ------------------------------------
    # Grid that provider "coarse" locations are snapped to, in degrees.
    # 0.01° ≈ 1.1 km. Larger = more private, less useful for planning a route.
    privacy_coarse_grid_degrees: float = Field(default=0.01, ge=0.005, le=0.1)
    # After a request closes, how long the assigned organization keeps the
    # full view (for follow-up) before dropping to the coarse view. ADR-0015 D7.
    privacy_assignee_grace_hours: int = Field(default=72, ge=0, le=720)
    # Extra audit keys to mask, comma-separated (e.g. "aadhaar,vehicle_no").
    # Can only ADD to the built-in list in shared/privacy.py, never remove.
    audit_redact_extra_keys: str = ""

    # ---- Privacy — reserved for tasks not built yet ------------------------
    # Validated and documented now so the defaults are agreed in one place;
    # no code reads them until the named PENDING-TASKS item is built.
    privacy_rural_grid_degrees: float = Field(default=0.05, ge=0.005, le=0.5)   # G-4/G-5, D3
    privacy_k_anonymity: int = Field(default=5, ge=2, le=100)                   # G-9
    privacy_reveal_limit_per_hour: int = Field(default=20, ge=1, le=500)        # G-5
    privacy_reveal_ttl_hours: int = Field(default=24, ge=1, le=168)             # G-5

    # ---- Retention, in days (ADR-0015 D4) — reserved for G-7 ---------------
    # The daily retention job (G-7) will read these. Until it exists, nothing
    # is deleted automatically. The audit log is never deleted by this job.
    retention_contact_days: int = Field(default=30, ge=1, le=3650)
    retention_exact_location_days: int = Field(default=30, ge=1, le=3650)
    retention_free_text_days: int = Field(default=90, ge=1, le=3650)
    retention_photo_days: int = Field(default=30, ge=1, le=3650)
    retention_message_days: int = Field(default=90, ge=1, le=3650)
    retention_notification_days: int = Field(default=30, ge=1, le=3650)
    retention_live_location_days: int = Field(default=7, ge=1, le=365)
    retention_session_days: int = Field(default=90, ge=1, le=3650)
    retention_login_attempt_days: int = Field(default=90, ge=1, le=3650)
    retention_reveal_log_days: int = Field(default=365, ge=30, le=3650)
    retention_deactivated_account_days: int = Field(default=365, ge=30, le=3650)

    # ---- Flask dashboard --------------------------------------------------
    dashboard_secret_key: str = "change-me-dashboard"
    dashboard_session_cookie_secure: bool = False
    dashboard_session_lifetime_minutes: int = 480
    dashboard_allowed_roles: str = "coordinator,admin"

    # ---- First admin (used once, by migration 0003) -----------------------
    admin_initial_password: str = ""

    # ---- Seed -------------------------------------------------------------
    seed_password: str = "IDRMseed#2026"

    # ---- Cross-checks -----------------------------------------------------
    @model_validator(mode="after")
    def _privacy_values_agree(self) -> Settings:
        """Reject combinations that would quietly undo a privacy promise."""
        if self.privacy_rural_grid_degrees < self.privacy_coarse_grid_degrees:
            raise ValueError("PRIVACY_RURAL_GRID_DEGREES must be at least "
                             "PRIVACY_COARSE_GRID_DEGREES: rural areas need the "
                             "coarser grid, because fewer homes share a cell.")
        if self.privacy_assignee_grace_hours > self.retention_contact_days * 24:
            raise ValueError("PRIVACY_ASSIGNEE_GRACE_HOURS is longer than "
                             "RETENTION_CONTACT_DAYS: the contact details would "
                             "be deleted while the grace window still promises them.")
        return self

    # ---- Derived ----------------------------------------------------------
    @property
    def audit_redact_keys(self) -> frozenset[str]:
        """The extra audit keys from AUDIT_REDACT_EXTRA_KEYS, lower-cased."""
        return frozenset(k.strip().lower() for k in self.audit_redact_extra_keys.split(",")
                         if k.strip())

    @property
    def coarse_grid_km(self) -> float:
        """The coarse grid as a rough distance (1° of latitude ≈ 111 km)."""
        return round(self.privacy_coarse_grid_degrees * 111, 1)

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
