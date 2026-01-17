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

        Supports hierarchical prompt loading: global → area → site
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

        Example:
            # Load global prompt only
            config = PromptLoader.load("config/prompts/tourism_qa.yaml")

            # Load with area override
            config = PromptLoader.load("config/prompts/tourism_qa.yaml", area="hefer_valley")

            # Load with site override
            config = PromptLoader.load("config/prompts/tourism_qa.yaml",
                                      area="hefer_valley", site="agamon_hefer")
        """
        # Normalize path to absolute before caching for better cache efficiency
        yaml_path_obj = Path(yaml_path)
        if not yaml_path_obj.is_absolute():
            yaml_path_obj = Path.cwd() / yaml_path_obj

        # Resolve to canonical absolute path (resolves symlinks, .., etc.)
        yaml_path_obj = yaml_path_obj.resolve()
        normalized_path = str(yaml_path_obj)

        # Include location in cache key for proper caching
        cache_key = (normalized_path, area or "", site or "")

        # Use cached internal loader
        return PromptLoader._load_cached(cache_key)

    @staticmethod
    @lru_cache(maxsize=10)
    def _load_cached(cache_key: tuple) -> PromptConfig:
        """
        Internal cached loader (called after path normalization)

        Args:
            cache_key: Tuple of (yaml_path, area, site) for cache differentiation

        Returns:
            PromptConfig instance with merged configuration
        """
        yaml_path, area, site = cache_key
        yaml_path_obj = Path(yaml_path)

        if not yaml_path_obj.exists():
            raise FileNotFoundError(f"Prompt configuration file not found: {yaml_path}")

        # Load base YAML file
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(
                f"Failed to parse YAML file {yaml_path}: {e}"
            ) from e

        # Apply location-specific overrides if provided
        if area:
            # Extract prompt file name (e.g., "tourism_qa.yaml")
            prompt_filename = yaml_path_obj.name

            # Find project root using unified detection (robust to directory structure)
            project_root = find_project_root(yaml_path_obj)

            # Try area-level prompt override: config/locations/{area}/prompts/{prompt_name}.yaml
            area_prompt_path = project_root / "config" / "locations" / area / "prompts" / prompt_filename
            if area_prompt_path.exists():
                try:
                    with open(area_prompt_path, "r", encoding="utf-8") as f:
                        area_config = yaml.safe_load(f)
                        if area_config:
                            config_data = merge_configs(config_data, area_config)
                except yaml.YAMLError as e:
                    raise yaml.YAMLError(
                        f"Failed to parse area override {area_prompt_path}: {e}"
                    ) from e

            # Try site-level prompt override if site provided: config/locations/{area}/{site}/prompts/{prompt_name}.yaml
            if site:
                site_prompt_path = project_root / "config" / "locations" / area / site / "prompts" / prompt_filename
                if site_prompt_path.exists():
                    try:
                        with open(site_prompt_path, "r", encoding="utf-8") as f:
                            site_config = yaml.safe_load(f)
                            if site_config:
                                config_data = merge_configs(config_data, site_config)
                    except yaml.YAMLError as e:
                        raise yaml.YAMLError(
                            f"Failed to parse site override {site_prompt_path}: {e}"
                        ) from e

        # Validate that YAML contains a dictionary
        if config_data is None or not isinstance(config_data, dict):
            raise ValueError(
                f"YAML file {yaml_path} is empty or does not contain a valid configuration"
            )

        # Validate required fields
        required_fields = ["model_name", "temperature", "system_prompt", "user_prompt"]
        missing_fields = [
            field for field in required_fields if field not in config_data
        ]
        if missing_fields:
            raise ValueError(
                f"YAML file {yaml_path} missing required fields: {', '.join(missing_fields)}"
            )

        # Validate types
        if not isinstance(config_data["model_name"], str):
            raise ValueError(
                f"Invalid type for 'model_name' in {yaml_path}: expected str, got {type(config_data['model_name']).__name__}"
            )

        if not isinstance(config_data["temperature"], (int, float)):
            raise ValueError(
                f"Invalid type for 'temperature' in {yaml_path}: expected float, got {type(config_data['temperature']).__name__}"
            )

        # Validate temperature bounds (Gemini API accepts 0.0-2.0)
        temperature = float(config_data["temperature"])
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(
                f"Invalid temperature value in {yaml_path}: {temperature}. Must be between 0.0 and 2.0"
            )

        if not isinstance(config_data["system_prompt"], str):
            raise ValueError(
                f"Invalid type for 'system_prompt' in {yaml_path}: expected str, got {type(config_data['system_prompt']).__name__}"
            )

        if not isinstance(config_data["user_prompt"], str):
            raise ValueError(
                f"Invalid type for 'user_prompt' in {yaml_path}: expected str, got {type(config_data['user_prompt']).__name__}"
            )

        # Create and return PromptConfig
        return PromptConfig(
            model_name=config_data["model_name"],
            temperature=temperature,
            system_prompt=config_data["system_prompt"],
            user_prompt=config_data["user_prompt"],
        )
