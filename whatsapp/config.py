"""
Configuration management for WhatsApp bot.

Loads and validates environment variables required for WhatsApp integration.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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

    # Default location context
    default_area: str
    default_site: str

    # Logging
    log_dir: Path

    # Background task configuration
    background_task_timeout_seconds: int
    message_dedup_ttl_seconds: int

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

        return cls(
            verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN", "your-verify-token-here"),
            access_token=os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
            phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
            app_secret=os.getenv("WHATSAPP_APP_SECRET"),
            backend_api_url=backend_api_url,
            backend_api_key=os.getenv("BACKEND_API_KEY", ""),
            gcs_bucket=os.getenv("GCS_BUCKET", ""),
            graph_api_version=os.getenv("META_GRAPH_API_VERSION", "v22.0"),
            port=port,
            use_local_backend=use_local_backend,
            backend_port=backend_port,
            default_area="עמק חפר",  # Hefer Valley
            default_site="אגמון חפר",  # Agamon Hefer
            log_dir=Path("whatsapp_logs"),
            background_task_timeout_seconds=180,  # 3 minutes (handles large image uploads)
            message_dedup_ttl_seconds=300,  # 5 minutes
        )

    def validate(self) -> None:
        """
        Validate required environment variables at startup (fail fast).

        Raises:
            RuntimeError: If required environment variables are missing
        """
        required_vars = {
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
