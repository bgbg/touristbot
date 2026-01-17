"""
Prompt loader for YAML-based LLM prompt configurations
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

import yaml

from gemini.config import merge_configs, find_project_root


@dataclass
class PromptConfig:
    """Configuration for LLM prompts loaded from YAML"""

    model_name: str
    temperature: float
    system_prompt: str
    user_prompt: str

    def format(self, **kwargs) -> Tuple[str, str]:
        """
        Format prompts with variable interpolation

        Args:
            **kwargs: Variables to interpolate into prompts

        Returns:
            Tuple of (formatted_system_prompt, formatted_user_prompt)

        Raises:
            KeyError: If a required variable is missing from kwargs
        """
        try:
            formatted_system = self.system_prompt.format(**kwargs)
            formatted_user = self.user_prompt.format(**kwargs)
            return formatted_system, formatted_user
        except KeyError as e:
            raise KeyError(
                f"Missing required variable for prompt interpolation: {e}"
            ) from e


def _load_yaml_file(path: Path, context: str) -> Optional[dict]:
    """
    Load and parse a YAML file with error handling.

    Args:
        path: Path to YAML file
        context: Description for error messages (e.g., "base config", "area override")

    Returns:
        Parsed YAML data or None if file doesn't exist

    Raises:
        yaml.YAMLError: If YAML parsing fails
    """
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse {context} {path}: {e}") from e
    except IOError as e:
        raise IOError(f"Failed to read {context} {path}: {e}") from e


def _validate_prompt_config(config_data: dict, yaml_path: str) -> float:
    """
    Validate prompt configuration data.

    Args:
        config_data: Configuration dictionary to validate
        yaml_path: Path for error messages

    Returns:
        Validated temperature as float

    Raises:
        ValueError: If validation fails
    """
    if config_data is None or not isinstance(config_data, dict):
        raise ValueError(
            f"YAML file {yaml_path} is empty or does not contain a valid configuration"
        )

    required_fields = ["model_name", "temperature", "system_prompt", "user_prompt"]
    missing_fields = [field for field in required_fields if field not in config_data]
    if missing_fields:
        raise ValueError(
            f"YAML file {yaml_path} missing required fields: {', '.join(missing_fields)}"
        )

    # Type validation
    type_checks = [
        ("model_name", str),
        ("system_prompt", str),
        ("user_prompt", str),
    ]
    for field, expected_type in type_checks:
        if not isinstance(config_data[field], expected_type):
            raise ValueError(
                f"Invalid type for '{field}' in {yaml_path}: "
                f"expected {expected_type.__name__}, got {type(config_data[field]).__name__}"
            )

    if not isinstance(config_data["temperature"], (int, float)):
        raise ValueError(
            f"Invalid type for 'temperature' in {yaml_path}: "
            f"expected float, got {type(config_data['temperature']).__name__}"
        )

    temperature = float(config_data["temperature"])
    if not 0.0 <= temperature <= 2.0:
        raise ValueError(
            f"Invalid temperature value in {yaml_path}: {temperature}. Must be between 0.0 and 2.0"
        )

    return temperature


class PromptLoader:
    """Loader for YAML-based prompt configurations"""

    @staticmethod
    def load(
        yaml_path: str,
        area: Optional[str] = None,
        site: Optional[str] = None,
    ) -> PromptConfig:
        """
        Load prompt configuration from YAML file with optional location-specific overrides

        Supports hierarchical prompt loading: global -> area -> site
        Each level inherits all fields from parent and overrides specified fields only.

        Args:
            yaml_path: Path to YAML configuration file (relative or absolute)
            area: Optional area name for location-specific overrides
            site: Optional site name for location-specific overrides (requires area)

        Returns:
            PromptConfig instance with merged configuration

        Raises:
            FileNotFoundError: If base YAML file doesn't exist
            ValueError: If YAML file has invalid schema or missing required fields
            yaml.YAMLError: If YAML file has syntax errors
        """
        yaml_path_obj = Path(yaml_path)
        if not yaml_path_obj.is_absolute():
            yaml_path_obj = Path.cwd() / yaml_path_obj
        yaml_path_obj = yaml_path_obj.resolve()

        cache_key = (str(yaml_path_obj), area or "", site or "")
        return PromptLoader._load_cached(cache_key)

    @staticmethod
    @lru_cache(maxsize=10)
    def _load_cached(cache_key: tuple) -> PromptConfig:
        """Internal cached loader (called after path normalization)"""
        yaml_path, area, site = cache_key
        yaml_path_obj = Path(yaml_path)

        if not yaml_path_obj.exists():
            raise FileNotFoundError(f"Prompt configuration file not found: {yaml_path}")

        config_data = _load_yaml_file(yaml_path_obj, "base config")

        # Apply location-specific overrides
        if area:
            prompt_filename = yaml_path_obj.name
            project_root = find_project_root(yaml_path_obj)
            locations_base = project_root / "config" / "locations"

            # Area-level override
            area_config = _load_yaml_file(
                locations_base / area / "prompts" / prompt_filename,
                "area override"
            )
            if area_config:
                config_data = merge_configs(config_data, area_config)

            # Site-level override
            if site:
                site_config = _load_yaml_file(
                    locations_base / area / site / "prompts" / prompt_filename,
                    "site override"
                )
                if site_config:
                    config_data = merge_configs(config_data, site_config)

        temperature = _validate_prompt_config(config_data, yaml_path)

        return PromptConfig(
            model_name=config_data["model_name"],
            temperature=temperature,
            system_prompt=config_data["system_prompt"],
            user_prompt=config_data["user_prompt"],
        )
