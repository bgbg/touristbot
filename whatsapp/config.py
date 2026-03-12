"""
Configuration management for WhatsApp bot.

Loads and validates environment variables required for WhatsApp integration.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class PhoneNumberConfig:
    """Configuration for a single WhatsApp phone number."""
    phone_number_id: str
    access_token: str
    area: str
    site: str
    app_secret: Optional[str] = None


@dataclass
class WhatsAppConfig:
    """WhatsApp bot configuration loaded from environment variables."""

    # WhatsApp API credentials
    verify_token: str
    access_token: str
    phone_number_id: str
    app_secret: Optional[str]

    # Backend API configuration
    backend_api_url: str
    backend_api_key: str

    # GCS storage
    gcs_bucket: str

    # Meta Graph API version
    graph_api_version: str

    # Server configuration
    port: int
    use_local_backend: bool
    backend_port: int

    # Default location context (used when phone_number_id not found in map)
    default_area: str
    default_site: str

    # Multi-number routing map: phone_number_id -> PhoneNumberConfig
    phone_number_map: Dict[str, PhoneNumberConfig] = field(default_factory=dict)

    # True when PHONE_NUMBER_MAP env var was explicitly set (vs. auto-seeded primary)
    multi_number_mode: bool = False

    # Logging
    log_dir: Path = field(default_factory=lambda: Path("whatsapp_logs"))

    # Background task configuration
    background_task_timeout_seconds: int = 180
    message_dedup_ttl_seconds: int = 300

    @staticmethod
    def _parse_phone_number_map(raw: str, default_area: str, default_site: str) -> Dict[str, PhoneNumberConfig]:
        """
        Parse PHONE_NUMBER_MAP env var into a dict of PhoneNumberConfig.

        Format: id1:token1:area1:site1[:app_secret1],id2:token2:area2:site2[:app_secret2]

        The app_secret field (5th) is optional. When omitted, the global
        WHATSAPP_APP_SECRET is used for signature verification.

        Args:
            raw: Raw env var string
            default_area: Fallback area for entries with empty area field
            default_site: Fallback site for entries with empty site field

        Returns:
            Dict mapping phone_number_id to PhoneNumberConfig

        Raises:
            ValueError: If an entry has wrong number of fields or empty required fields
        """
        result: Dict[str, PhoneNumberConfig] = {}
        if not raw.strip():
            return result

        for entry in raw.strip().split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":")
            if len(parts) not in (4, 5):
                raise ValueError(
                    f"Invalid PHONE_NUMBER_MAP entry '{entry}': "
                    f"expected 'phone_number_id:access_token:area:site[:app_secret]', got {len(parts)} fields"
                )
            phone_number_id, access_token, area, site = parts[:4]
            app_secret = parts[4] if len(parts) == 5 else None
            if not phone_number_id or not access_token:
                raise ValueError(
                    f"Invalid PHONE_NUMBER_MAP entry '{entry}': "
                    f"phone_number_id and access_token must not be empty"
                )
            result[phone_number_id] = PhoneNumberConfig(
                phone_number_id=phone_number_id,
                access_token=access_token,
                area=area or default_area,
                site=site or default_site,
                app_secret=app_secret or None,
            )

        return result

    @classmethod
    def from_env(cls) -> WhatsAppConfig:
        """
        Load configuration from environment variables.

        Returns:
            WhatsAppConfig instance with all configuration loaded

        Raises:
            RuntimeError: If required environment variables are missing
        """
        # Auto-detect environment: use local backend in dev, Cloud Run backend in production
        use_local_backend_str = os.getenv(
            "USE_LOCAL_BACKEND",
            "false" if os.getenv("K_SERVICE") else "true"
        )
        use_local_backend = use_local_backend_str.lower() in ("true", "1", "yes")

        backend_port = int(os.getenv("BACKEND_PORT", "8001"))
        backend_api_url = os.getenv(
            "BACKEND_API_URL",
            f"http://localhost:{backend_port}" if use_local_backend
            else "https://tourism-rag-backend-347968285860.me-west1.run.app"
        )

        # Backward compatible PORT handling: Cloud Run uses PORT, local dev may use WHATSAPP_LISTENER_PORT
        port_env = os.getenv("PORT") or os.getenv("WHATSAPP_LISTENER_PORT")
        port = int(port_env) if port_env else 8080

        default_area = "עמק חפר"  # Hefer Valley
        default_site = "אגמון חפר"  # Agamon Hefer

        primary_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        primary_access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")

        # Build phone_number_map from PHONE_NUMBER_MAP env var
        phone_number_map_raw = os.getenv("PHONE_NUMBER_MAP", "")
        phone_number_map = cls._parse_phone_number_map(phone_number_map_raw, default_area, default_site)
        multi_number_mode = bool(phone_number_map)  # True only if PHONE_NUMBER_MAP had entries

        # Always seed the primary number into the map if set and not already there
        if primary_phone_number_id and primary_phone_number_id not in phone_number_map:
            phone_number_map[primary_phone_number_id] = PhoneNumberConfig(
                phone_number_id=primary_phone_number_id,
                access_token=primary_access_token,
                area=default_area,
                site=default_site,
            )

        return cls(
            verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN", "your-verify-token-here"),
            access_token=primary_access_token,
            phone_number_id=primary_phone_number_id,
            app_secret=os.getenv("WHATSAPP_APP_SECRET"),
            backend_api_url=backend_api_url,
            backend_api_key=os.getenv("BACKEND_API_KEY", ""),
            gcs_bucket=os.getenv("GCS_BUCKET", ""),
            graph_api_version=os.getenv("META_GRAPH_API_VERSION", "v22.0"),
            port=port,
            use_local_backend=use_local_backend,
            backend_port=backend_port,
            default_area=default_area,
            default_site=default_site,
            phone_number_map=phone_number_map,
            multi_number_mode=multi_number_mode,
            log_dir=Path("whatsapp_logs"),
            background_task_timeout_seconds=180,  # 3 minutes (handles large image uploads)
            message_dedup_ttl_seconds=300,  # 5 minutes
        )

    def validate(self) -> None:
        """
        Validate required environment variables at startup (fail fast).

        If PHONE_NUMBER_MAP was explicitly set (multi_number_mode), individual
        WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID are not required
        (tokens are configured via PHONE_NUMBER_MAP instead).

        Raises:
            RuntimeError: If required environment variables are missing
        """
        if not self.multi_number_mode:
            # Single-number mode: validate individual vars
            required_vars: Dict[str, tuple] = {
                "WHATSAPP_VERIFY_TOKEN": ("Token for Meta webhook verification", self.verify_token),
                "WHATSAPP_ACCESS_TOKEN": ("WhatsApp Business API access token", self.access_token),
                "WHATSAPP_PHONE_NUMBER_ID": ("WhatsApp phone number ID", self.phone_number_id),
                "BACKEND_API_KEY": ("Backend API authentication key", self.backend_api_key),
                "GCS_BUCKET": (
                    "Google Cloud Storage bucket for conversation persistence "
                    "(use Application Default Credentials for auth)",
                    self.gcs_bucket
                ),
            }
        else:
            # Multi-number mode: only require shared vars
            required_vars = {
                "WHATSAPP_VERIFY_TOKEN": ("Token for Meta webhook verification", self.verify_token),
                "BACKEND_API_KEY": ("Backend API authentication key", self.backend_api_key),
                "GCS_BUCKET": (
                    "Google Cloud Storage bucket for conversation persistence "
                    "(use Application Default Credentials for auth)",
                    self.gcs_bucket
                ),
            }

        # In production, WHATSAPP_APP_SECRET is also required for webhook signature validation
        is_production = os.getenv("K_SERVICE") or os.getenv("GAE_ENV")
        if is_production:
            required_vars["WHATSAPP_APP_SECRET"] = (
                "Meta app secret for webhook signature validation (required in production)",
                self.app_secret or ""
            )

        missing_vars = []
        for var_name, (description, value) in required_vars.items():
            if not value:
                missing_vars.append(f"  - {var_name}: {description}")

        if missing_vars:
            error_msg = "Missing required environment variables:\n" + "\n".join(missing_vars)
            print(error_msg, file=sys.stderr)
            raise RuntimeError(error_msg)

        # Create log directory if it doesn't exist
        self.log_dir.mkdir(exist_ok=True)


def is_production_environment() -> bool:
    """
    Detect if running in production environment.

    Returns:
        True if running on Cloud Run or App Engine, False otherwise
    """
    return bool(os.getenv("K_SERVICE") or os.getenv("GAE_ENV"))
