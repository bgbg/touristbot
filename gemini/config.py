"""
Configuration management for Gemini Tourism/Museum RAG system
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from gemini.utils import load_env_file, get_secret


def find_config_file() -> str:
    """Find the project root config.yaml file"""
    current_dir = Path(__file__).resolve().parent

    # Search up the directory tree for config.yaml
    for parent in [current_dir] + list(current_dir.parents):
        config_path = parent / "config.yaml"
        if config_path.exists():
            return str(config_path)

    raise FileNotFoundError("Could not find config.yaml in project directories")


@dataclass
class GeminiConfig:
    """Configuration for Gemini Tourism RAG system"""

    # API Configuration
    api_key: str

    # Content paths
    content_root: str
    chunks_dir: str

    # App Configuration
    app_name: str = "Tourism Guide Assistant"
    app_type: str = "museum_tourism"
    language: str = "English"

    # Store Configuration
    store_display_name: str = "Tourism_RAG_Store"

    # Chunking Configuration
    use_token_chunking: bool = True
    chunk_tokens: int = 400
    chunk_overlap_percent: float = 0.15
    chunk_size: int = 1000  # Legacy character-based

    # Model Configuration
    model_name: str = "gemini-1.5-pro"
    temperature: float = 0.7

    # Upload Configuration
    max_upload_wait_seconds: int = 300
    max_files_per_query: int = 10

    # Registry and tracking paths
    registry_path: str = "gemini/store_registry.json"
    upload_tracking_path: str = "gemini/upload_tracking.json"

    # Force reupload flag
    force_reupload: bool = False

    # Registry rebuild configuration
    auto_rebuild_registry: bool = True  # Rebuild registry from API on startup

    # GCS Storage Configuration
    gcs_bucket_name: str = "tarasa_tourist_bot_content"
    gcs_credentials_json: Optional[str] = None
    enable_local_cache: bool = False

    # Supported file formats
    supported_formats: List[str] = None

    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = [".txt", ".md", ".pdf", ".docx"]

    @classmethod
    def from_yaml(cls, config_path: Optional[str] = None) -> "GeminiConfig":
        """
        Create configuration from YAML file

        Args:
            config_path: Optional path to config.yaml (auto-detected if not provided)

        Returns:
            GeminiConfig instance
        """
        # Find config file
        if config_path is None:
            config_path = find_config_file()

        # Load YAML config
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        # Load environment variables from .env file (optional fallback)
        load_env_file()

        # Get API key from Streamlit secrets
        try:
            api_key = get_secret("GOOGLE_API_KEY")
        except KeyError:
            raise ValueError(
                "GOOGLE_API_KEY not found. "
                "Please add it to .streamlit/secrets.toml (local) or Streamlit Cloud secrets: GOOGLE_API_KEY='your-api-key'"
            )

        # Get GCS credentials from Streamlit secrets (optional)
        gcs_credentials_json = None
        try:
            # Try to get GCS credentials from secrets
            gcs_creds = get_secret("gcs_credentials")
            if gcs_creds:
                # If gcs_credentials is a dict (from TOML), convert to JSON string
                if isinstance(gcs_creds, dict):
                    import json
                    gcs_credentials_json = json.dumps(gcs_creds)
                else:
                    # If it's already a string, use it directly
                    gcs_credentials_json = gcs_creds
        except KeyError:
            # GCS credentials not in secrets - will try to use Application Default Credentials
            pass

        # Extract configuration
        content_root = yaml_config.get("content_root", "/path/to/tourism/content")
        app_config = yaml_config.get("app", {})
        gemini_config = yaml_config.get("gemini_rag", {})
        storage_config = yaml_config.get("storage", {})

        config = cls(
            api_key=api_key,
            content_root=content_root,
            chunks_dir=gemini_config.get("chunks_dir", f"{content_root}_chunks"),
            app_name=app_config.get("name", "Tourism Guide Assistant"),
            app_type=app_config.get("type", "museum_tourism"),
            language=app_config.get("language", "English"),
            use_token_chunking=gemini_config.get("use_token_chunking", True),
            chunk_tokens=gemini_config.get("chunk_tokens", 400),
            chunk_overlap_percent=gemini_config.get("chunk_overlap_percent", 0.15),
            chunk_size=gemini_config.get("chunk_size", 1000),
            model_name=gemini_config.get("model", "gemini-1.5-pro"),
            temperature=gemini_config.get("temperature", 0.7),
            max_upload_wait_seconds=gemini_config.get("max_upload_wait_seconds", 300),
            max_files_per_query=gemini_config.get("max_files_per_query", 10),
            registry_path=gemini_config.get(
                "registry_path", "gemini/store_registry.json"
            ),
            upload_tracking_path=gemini_config.get(
                "upload_tracking_path", "gemini/upload_tracking.json"
            ),
            force_reupload=gemini_config.get("force_reupload", False),
            auto_rebuild_registry=gemini_config.get("auto_rebuild_registry", True),
            gcs_bucket_name=storage_config.get(
                "gcs_bucket_name", "tarasa_tourist_bot_content"
            ),
            gcs_credentials_json=gcs_credentials_json,
            enable_local_cache=storage_config.get("enable_local_cache", False),
            supported_formats=yaml_config.get(
                "supported_formats", [".txt", ".md", ".pdf", ".docx"]
            ),
        )

        return config

    @classmethod
    def from_env(cls, store_name: Optional[str] = None) -> "GeminiConfig":
        """
        Create configuration from environment variables only (fallback)

        Args:
            store_name: Optional custom store name

        Returns:
            GeminiConfig instance
        """
        try:
            api_key = source_key("GEMINI_API_KEY")
        except KeyError:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Please add to ~/.bashrc: export GEMINI_API_KEY='your-api-key'"
            )

        config = cls(
            api_key=api_key,
            content_root="/path/to/tourism/content",
            chunks_dir="/path/to/tourism/content_chunks",
        )

        if store_name:
            config.store_display_name = store_name

        return config
