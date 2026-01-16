"""
Configuration management for Gemini Tourism/Museum RAG system
"""

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from gemini.utils import load_env_file, get_secret


def merge_configs(base: dict, override: dict) -> dict:
    """
    Deep merge two configuration dictionaries

    Merges override dict into base dict, with override values taking precedence.
    - For nested dicts: recursively merges
    - For lists: replaces entire list (no smart merging)
    - For other types: override value replaces base value

    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary (values take precedence)

    Returns:
        New dictionary with merged configuration (does not modify inputs)

    Example:
        >>> base = {"a": 1, "b": {"c": 2, "d": 3}, "e": [1, 2]}
        >>> override = {"b": {"c": 999}, "e": [3, 4, 5]}
        >>> merge_configs(base, override)
        {"a": 1, "b": {"c": 999, "d": 3}, "e": [3, 4, 5]}
    """
    # Create a deep copy of base to avoid modifying it or its nested structures
    result = copy.deepcopy(base)

    for key, override_value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(override_value, dict):
            # Recursively merge nested dictionaries
            result[key] = merge_configs(result[key], override_value)
        else:
            # For lists, primitives, or new keys: replace entirely
            result[key] = override_value

    return result


def find_project_root(start_path: Path) -> Path:
    """
    Find the project root directory by searching upward for config/locations marker.

    Searches from the given path upward through parent directories until it finds
    a directory containing config/locations/. This provides a robust way to locate
    the project root regardless of the starting file's location.

    Args:
        start_path: Path to start searching from (file or directory)

    Returns:
        Path to project root directory

    Raises:
        FileNotFoundError: If no project root marker found
    """
    # Start from directory if given a file
    search_dir = start_path if start_path.is_dir() else start_path.parent

    # Search upward for config/locations marker
    for candidate in [search_dir] + list(search_dir.parents):
        if (candidate / "config" / "locations").exists():
            return candidate

    # Fallback: search for config.yaml as secondary marker
    for candidate in [search_dir] + list(search_dir.parents):
        if (candidate / "config.yaml").exists():
            return candidate

    raise FileNotFoundError(
        f"Could not find project root from {start_path}. "
        "Expected to find config/locations/ or config.yaml in parent directories."
    )


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
    file_search_store_name: str = "TARASA_Tourism_RAG"

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

    # Registry paths (GCS)
    store_registry_gcs_path: str = "metadata/store_registry.json"
    image_registry_gcs_path: str = "metadata/image_registry.json"
    upload_tracking_path: str = ".cache/upload_tracking.json"

    # Prompts directory
    prompts_dir: str = "prompts/"

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
    def from_yaml(
        cls,
        config_path: Optional[str] = None,
        area: Optional[str] = None,
        site: Optional[str] = None,
    ) -> "GeminiConfig":
        """
        Create configuration from YAML file with optional location-specific overrides

        Supports hierarchical configuration loading: global → area → site
        Each level inherits all fields from parent and overrides specified fields only.

        Args:
            config_path: Optional path to config.yaml (auto-detected if not provided)
            area: Optional area name for location-specific overrides
            site: Optional site name for location-specific overrides (requires area)

        Returns:
            GeminiConfig instance with merged configuration

        Example:
            # Load global config only
            config = GeminiConfig.from_yaml()

            # Load with area override
            config = GeminiConfig.from_yaml(area="hefer_valley")

            # Load with site override (inherits from area if exists, then global)
            config = GeminiConfig.from_yaml(area="hefer_valley", site="agamon_hefer")
        """
        # Find config file
        if config_path is None:
            config_path = find_config_file()

        # Load base YAML config
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        # Apply location-specific overrides if provided
        if area:
            # Find project root using unified detection
            project_root = find_project_root(Path(config_path))

            # Try area-level override: config/locations/{area}.yaml
            area_override_path = project_root / "config" / "locations" / f"{area}.yaml"
            if area_override_path.exists():
                with open(area_override_path, "r", encoding="utf-8") as f:
                    area_config = yaml.safe_load(f)
                    if area_config:
                        yaml_config = merge_configs(yaml_config, area_config)

            # Try site-level override if site provided: config/locations/{area}/{site}.yaml
            if site:
                site_override_path = project_root / "config" / "locations" / area / f"{site}.yaml"
                if site_override_path.exists():
                    with open(site_override_path, "r", encoding="utf-8") as f:
                        site_config = yaml.safe_load(f)
                        if site_config:
                            yaml_config = merge_configs(yaml_config, site_config)

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
                # If gcs_credentials is a dict-like object (from TOML), convert to JSON string
                # This includes both dict and Streamlit's AttrDict
                if hasattr(gcs_creds, 'keys') or isinstance(gcs_creds, dict):
                    import json
                    # Convert to regular dict if it's an AttrDict or similar
                    if hasattr(gcs_creds, 'to_dict'):
                        gcs_creds = gcs_creds.to_dict()
                    elif not isinstance(gcs_creds, dict):
                        # Convert AttrDict-like objects to dict
                        gcs_creds = dict(gcs_creds)
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
            file_search_store_name=gemini_config.get(
                "file_search_store_name", "TARASA_Tourism_RAG"
            ),
            use_token_chunking=gemini_config.get("use_token_chunking", True),
            chunk_tokens=gemini_config.get("chunk_tokens", 400),
            chunk_overlap_percent=gemini_config.get("chunk_overlap_percent", 0.15),
            chunk_size=gemini_config.get("chunk_size", 1000),
            model_name=gemini_config.get("model", "gemini-1.5-pro"),
            temperature=gemini_config.get("temperature", 0.7),
            max_upload_wait_seconds=gemini_config.get("max_upload_wait_seconds", 300),
            max_files_per_query=gemini_config.get("max_files_per_query", 10),
            store_registry_gcs_path=gemini_config.get(
                "store_registry_gcs_path", "metadata/store_registry.json"
            ),
            upload_tracking_path=gemini_config.get(
                "upload_tracking_path", ".cache/upload_tracking.json"
            ),
            image_registry_gcs_path=gemini_config.get(
                "image_registry_gcs_path", "metadata/image_registry.json"
            ),
            prompts_dir=gemini_config.get("prompts_dir", "prompts/"),
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
