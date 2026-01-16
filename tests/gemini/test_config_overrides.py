"""
Unit tests for location-specific configuration overrides.

Tests the hierarchical configuration loading mechanism (global → area → site)
with partial overrides and deep merging.
"""

import pytest
import tempfile
from pathlib import Path
import yaml
from gemini.config import merge_configs, GeminiConfig


class TestMergeConfigs:
    """Test the merge_configs utility function"""

    def test_merge_simple_values(self):
        """Test merging simple key-value pairs"""
        base = {"a": 1, "b": 2, "c": 3}
        override = {"b": 999}
        result = merge_configs(base, override)

        assert result == {"a": 1, "b": 999, "c": 3}
        assert base == {"a": 1, "b": 2, "c": 3}  # Base not modified

    def test_merge_nested_dicts(self):
        """Test deep merging of nested dictionaries"""
        base = {"app": {"name": "Test App", "type": "test"}, "other": "value"}
        override = {"app": {"name": "Override App"}}
        result = merge_configs(base, override)

        assert result == {
            "app": {"name": "Override App", "type": "test"},
            "other": "value",
        }

    def test_merge_replaces_lists(self):
        """Test that lists are replaced entirely, not appended"""
        base = {"items": [1, 2, 3], "other": "value"}
        override = {"items": [4, 5]}
        result = merge_configs(base, override)

        assert result == {"items": [4, 5], "other": "value"}

    def test_merge_adds_new_keys(self):
        """Test that override can add new keys"""
        base = {"a": 1}
        override = {"b": 2, "c": 3}
        result = merge_configs(base, override)

        assert result == {"a": 1, "b": 2, "c": 3}

    def test_merge_deeply_nested(self):
        """Test merging deeply nested structures"""
        base = {
            "level1": {"level2": {"level3": {"value": "old"}}, "other": "keep"}
        }
        override = {"level1": {"level2": {"level3": {"value": "new"}}}}
        result = merge_configs(base, override)

        assert result == {
            "level1": {"level2": {"level3": {"value": "new"}}, "other": "keep"}
        }

    def test_merge_empty_override(self):
        """Test that empty override dict returns base unchanged"""
        base = {"a": 1, "b": 2}
        override = {}
        result = merge_configs(base, override)

        assert result == base

    def test_merge_does_not_modify_inputs(self):
        """Test that merge does not modify input dictionaries"""
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"c": 999}}
        base_copy = {"a": 1, "b": {"c": 2}}
        override_copy = {"b": {"c": 999}}

        merge_configs(base, override)

        assert base == base_copy
        assert override == override_copy


class TestConfigOverrides:
    """Test GeminiConfig.from_yaml() with location overrides"""

    @pytest.fixture
    def temp_config_structure(self):
        """Create temporary config structure for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create base config.yaml
            base_config = {
                "content_root": "data/locations",
                "app": {"name": "Test App", "type": "test", "language": "English"},
                "gemini_rag": {
                    "model": "gemini-2.0-flash",
                    "temperature": 0.7,
                    "chunk_tokens": 400,
                    "prompts_dir": "prompts/",
                },
                "storage": {"gcs_bucket_name": "test_bucket"},
                "supported_formats": [".txt", ".md"],
            }

            config_path = tmpdir / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(base_config, f)

            # Create config/locations directory
            locations_dir = tmpdir / "config" / "locations"
            locations_dir.mkdir(parents=True)

            yield tmpdir, config_path, locations_dir

    def test_load_without_overrides(self, temp_config_structure, monkeypatch):
        """Test loading config without any location overrides"""
        tmpdir, config_path, _ = temp_config_structure

        # Mock secrets
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")

        def mock_get_secret(key):
            if key == "GOOGLE_API_KEY":
                return "test_key"
            raise KeyError(key)

        monkeypatch.setattr("gemini.config.get_secret", mock_get_secret)

        config = GeminiConfig.from_yaml(str(config_path))

        assert config.temperature == 0.7
        assert config.model_name == "gemini-2.0-flash"
        assert config.chunk_tokens == 400

    def test_load_with_area_override(self, temp_config_structure, monkeypatch):
        """Test loading config with area-level override"""
        tmpdir, config_path, locations_dir = temp_config_structure

        # Create area override
        area_override = {"gemini_rag": {"temperature": 0.5}}
        area_file = locations_dir / "test_area.yaml"
        with open(area_file, "w") as f:
            yaml.dump(area_override, f)

        # Mock secrets
        def mock_get_secret(key):
            if key == "GOOGLE_API_KEY":
                return "test_key"
            raise KeyError(key)

        monkeypatch.setattr("gemini.config.get_secret", mock_get_secret)

        config = GeminiConfig.from_yaml(str(config_path), area="test_area")

        # Temperature should be overridden
        assert config.temperature == 0.5
        # Other fields should be inherited
        assert config.model_name == "gemini-2.0-flash"
        assert config.chunk_tokens == 400

    def test_load_with_site_override(self, temp_config_structure, monkeypatch):
        """Test loading config with site-level override"""
        tmpdir, config_path, locations_dir = temp_config_structure

        # Create site directory and override
        site_dir = locations_dir / "test_area"
        site_dir.mkdir()
        site_override = {"gemini_rag": {"temperature": 0.3, "chunk_tokens": 500}}
        site_file = site_dir / "test_site.yaml"
        with open(site_file, "w") as f:
            yaml.dump(site_override, f)

        # Mock secrets
        def mock_get_secret(key):
            if key == "GOOGLE_API_KEY":
                return "test_key"
            raise KeyError(key)

        monkeypatch.setattr("gemini.config.get_secret", mock_get_secret)

        config = GeminiConfig.from_yaml(
            str(config_path), area="test_area", site="test_site"
        )

        # Both should be overridden
        assert config.temperature == 0.3
        assert config.chunk_tokens == 500
        # Model should be inherited
        assert config.model_name == "gemini-2.0-flash"

    def test_load_with_full_hierarchy(self, temp_config_structure, monkeypatch):
        """Test full hierarchy: global → area → site"""
        tmpdir, config_path, locations_dir = temp_config_structure

        # Create area override
        area_override = {"gemini_rag": {"temperature": 0.5, "chunk_tokens": 450}}
        area_file = locations_dir / "test_area.yaml"
        with open(area_file, "w") as f:
            yaml.dump(area_override, f)

        # Create site override (only temperature)
        site_dir = locations_dir / "test_area"
        site_dir.mkdir()
        site_override = {"gemini_rag": {"temperature": 0.3}}
        site_file = site_dir / "test_site.yaml"
        with open(site_file, "w") as f:
            yaml.dump(site_override, f)

        # Mock secrets
        def mock_get_secret(key):
            if key == "GOOGLE_API_KEY":
                return "test_key"
            raise KeyError(key)

        monkeypatch.setattr("gemini.config.get_secret", mock_get_secret)

        config = GeminiConfig.from_yaml(
            str(config_path), area="test_area", site="test_site"
        )

        # Temperature from site (most specific)
        assert config.temperature == 0.3
        # Chunk tokens from area (site doesn't override)
        assert config.chunk_tokens == 450
        # Model from global (neither area nor site override)
        assert config.model_name == "gemini-2.0-flash"

    def test_missing_override_files_graceful(self, temp_config_structure, monkeypatch):
        """Test that missing override files don't cause errors"""
        tmpdir, config_path, _ = temp_config_structure

        # Mock secrets
        def mock_get_secret(key):
            if key == "GOOGLE_API_KEY":
                return "test_key"
            raise KeyError(key)

        monkeypatch.setattr("gemini.config.get_secret", mock_get_secret)

        # Request overrides for non-existent location - should work fine
        config = GeminiConfig.from_yaml(
            str(config_path), area="nonexistent_area", site="nonexistent_site"
        )

        # Should use global config values
        assert config.temperature == 0.7
        assert config.model_name == "gemini-2.0-flash"

    def test_override_list_replacement(self, temp_config_structure, monkeypatch):
        """Test that lists are replaced entirely in overrides"""
        tmpdir, config_path, locations_dir = temp_config_structure

        # Create area override with different supported formats
        area_override = {"supported_formats": [".pdf", ".docx"]}
        area_file = locations_dir / "test_area.yaml"
        with open(area_file, "w") as f:
            yaml.dump(area_override, f)

        # Mock secrets
        def mock_get_secret(key):
            if key == "GOOGLE_API_KEY":
                return "test_key"
            raise KeyError(key)

        monkeypatch.setattr("gemini.config.get_secret", mock_get_secret)

        config = GeminiConfig.from_yaml(str(config_path), area="test_area")

        # List should be replaced, not merged
        assert config.supported_formats == [".pdf", ".docx"]
