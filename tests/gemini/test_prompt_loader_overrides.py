"""
Unit tests for location-specific prompt configuration overrides.

Tests the hierarchical prompt loading mechanism (global → area → site)
with partial overrides for PromptLoader.
"""

import pytest
import tempfile
from pathlib import Path
import yaml
from gemini.prompt_loader import PromptLoader


class TestPromptLoaderOverrides:
    """Test PromptLoader.load() with location overrides"""

    @pytest.fixture
    def temp_prompt_structure(self):
        """Create temporary prompt structure for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create prompts directory
            prompts_dir = tmpdir / "prompts"
            prompts_dir.mkdir()

            # Create base prompt file
            base_prompt = {
                "model_name": "gemini-2.0-flash",
                "temperature": 0.7,
                "system_prompt": "You are a helpful assistant for {area} / {site}",
                "user_prompt": "{question}",
            }

            prompt_path = prompts_dir / "test_qa.yaml"
            with open(prompt_path, "w") as f:
                yaml.dump(base_prompt, f)

            # Create config/locations directory
            locations_dir = tmpdir / "config" / "locations"
            locations_dir.mkdir(parents=True)

            yield tmpdir, prompt_path, locations_dir

    def test_load_without_overrides(self, temp_prompt_structure):
        """Test loading prompt without any location overrides"""
        tmpdir, prompt_path, _ = temp_prompt_structure

        config = PromptLoader.load(str(prompt_path))

        assert config.model_name == "gemini-2.0-flash"
        assert config.temperature == 0.7
        assert "helpful assistant" in config.system_prompt

    def test_load_with_area_override(self, temp_prompt_structure):
        """Test loading prompt with area-level override"""
        tmpdir, prompt_path, locations_dir = temp_prompt_structure

        # Create area prompts directory and override
        area_prompts_dir = locations_dir / "test_area" / "prompts"
        area_prompts_dir.mkdir(parents=True)

        area_override = {
            "temperature": 0.5,
            "system_prompt": "You are a guide for {area}",
        }
        area_prompt_file = area_prompts_dir / "test_qa.yaml"
        with open(area_prompt_file, "w") as f:
            yaml.dump(area_override, f)

        config = PromptLoader.load(str(prompt_path), area="test_area")

        # Overridden fields
        assert config.temperature == 0.5
        assert config.system_prompt == "You are a guide for {area}"
        # Inherited fields
        assert config.model_name == "gemini-2.0-flash"
        assert config.user_prompt == "{question}"

    def test_load_with_site_override(self, temp_prompt_structure):
        """Test loading prompt with site-level override"""
        tmpdir, prompt_path, locations_dir = temp_prompt_structure

        # Create site prompts directory and override
        site_prompts_dir = locations_dir / "test_area" / "test_site" / "prompts"
        site_prompts_dir.mkdir(parents=True)

        site_override = {
            "temperature": 0.3,
            "system_prompt": "You are an expert for {site}",
        }
        site_prompt_file = site_prompts_dir / "test_qa.yaml"
        with open(site_prompt_file, "w") as f:
            yaml.dump(site_override, f)

        config = PromptLoader.load(
            str(prompt_path), area="test_area", site="test_site"
        )

        # Overridden fields
        assert config.temperature == 0.3
        assert config.system_prompt == "You are an expert for {site}"
        # Inherited fields
        assert config.model_name == "gemini-2.0-flash"
        assert config.user_prompt == "{question}"

    def test_load_with_full_hierarchy(self, temp_prompt_structure):
        """Test full hierarchy: global → area → site"""
        tmpdir, prompt_path, locations_dir = temp_prompt_structure

        # Create area override
        area_prompts_dir = locations_dir / "test_area" / "prompts"
        area_prompts_dir.mkdir(parents=True)

        area_override = {
            "temperature": 0.5,
            "system_prompt": "Area guide for {area}",
        }
        area_prompt_file = area_prompts_dir / "test_qa.yaml"
        with open(area_prompt_file, "w") as f:
            yaml.dump(area_override, f)

        # Create site override (only temperature)
        site_prompts_dir = locations_dir / "test_area" / "test_site" / "prompts"
        site_prompts_dir.mkdir(parents=True)

        site_override = {"temperature": 0.3}
        site_prompt_file = site_prompts_dir / "test_qa.yaml"
        with open(site_prompt_file, "w") as f:
            yaml.dump(site_override, f)

        config = PromptLoader.load(
            str(prompt_path), area="test_area", site="test_site"
        )

        # Temperature from site (most specific)
        assert config.temperature == 0.3
        # System prompt from area (site doesn't override)
        assert config.system_prompt == "Area guide for {area}"
        # Model and user prompt from global (neither area nor site override)
        assert config.model_name == "gemini-2.0-flash"
        assert config.user_prompt == "{question}"

    def test_missing_override_files_graceful(self, temp_prompt_structure):
        """Test that missing override files don't cause errors"""
        tmpdir, prompt_path, _ = temp_prompt_structure

        # Request overrides for non-existent location - should work fine
        config = PromptLoader.load(
            str(prompt_path), area="nonexistent_area", site="nonexistent_site"
        )

        # Should use global prompt values
        assert config.model_name == "gemini-2.0-flash"
        assert config.temperature == 0.7
        assert "helpful assistant" in config.system_prompt

    def test_cache_respects_location(self, temp_prompt_structure):
        """Test that cache differentiates between locations"""
        tmpdir, prompt_path, locations_dir = temp_prompt_structure

        # Create area1 override
        area1_prompts_dir = locations_dir / "area1" / "prompts"
        area1_prompts_dir.mkdir(parents=True)
        area1_override = {"temperature": 0.3}
        with open(area1_prompts_dir / "test_qa.yaml", "w") as f:
            yaml.dump(area1_override, f)

        # Create area2 override
        area2_prompts_dir = locations_dir / "area2" / "prompts"
        area2_prompts_dir.mkdir(parents=True)
        area2_override = {"temperature": 0.9}
        with open(area2_prompts_dir / "test_qa.yaml", "w") as f:
            yaml.dump(area2_override, f)

        # Load for area1
        config1 = PromptLoader.load(str(prompt_path), area="area1")
        assert config1.temperature == 0.3

        # Load for area2 - should get different config
        config2 = PromptLoader.load(str(prompt_path), area="area2")
        assert config2.temperature == 0.9

        # Load for area1 again - should hit cache but still return correct value
        config1_again = PromptLoader.load(str(prompt_path), area="area1")
        assert config1_again.temperature == 0.3

    def test_partial_override_system_prompt_only(self, temp_prompt_structure):
        """Test minimal override: only system prompt"""
        tmpdir, prompt_path, locations_dir = temp_prompt_structure

        # Create site override with only system_prompt
        site_prompts_dir = locations_dir / "test_area" / "test_site" / "prompts"
        site_prompts_dir.mkdir(parents=True)

        site_override = {"system_prompt": "Custom site prompt"}
        site_prompt_file = site_prompts_dir / "test_qa.yaml"
        with open(site_prompt_file, "w") as f:
            yaml.dump(site_override, f)

        config = PromptLoader.load(
            str(prompt_path), area="test_area", site="test_site"
        )

        # Only system_prompt should be overridden
        assert config.system_prompt == "Custom site prompt"
        # All others inherited
        assert config.model_name == "gemini-2.0-flash"
        assert config.temperature == 0.7
        assert config.user_prompt == "{question}"

    def test_partial_override_temperature_only(self, temp_prompt_structure):
        """Test minimal override: only temperature"""
        tmpdir, prompt_path, locations_dir = temp_prompt_structure

        # Create area override with only temperature
        area_prompts_dir = locations_dir / "test_area" / "prompts"
        area_prompts_dir.mkdir(parents=True)

        area_override = {"temperature": 0.4}
        area_prompt_file = area_prompts_dir / "test_qa.yaml"
        with open(area_prompt_file, "w") as f:
            yaml.dump(area_override, f)

        config = PromptLoader.load(str(prompt_path), area="test_area")

        # Only temperature should be overridden
        assert config.temperature == 0.4
        # All others inherited
        assert config.model_name == "gemini-2.0-flash"
        assert "helpful assistant" in config.system_prompt
        assert config.user_prompt == "{question}"
