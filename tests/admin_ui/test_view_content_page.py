"""Tests for View Content page configuration access."""

import pytest
from gemini.config import GeminiConfig


class TestViewContentPageConfig:
    """Tests for View Content page's use of GeminiConfig."""

    def test_config_has_api_key_attribute(self):
        """Test that GeminiConfig has api_key attribute (not google_api_key)."""
        # Create a minimal config
        config = GeminiConfig(
            api_key="test-key-123",
            content_root="/tmp/test",
            chunks_dir="/tmp/test_chunks"
        )

        # Verify correct attribute exists
        assert hasattr(config, "api_key"), "GeminiConfig should have 'api_key' attribute"
        assert config.api_key == "test-key-123"

        # Verify incorrect attribute does NOT exist
        assert not hasattr(config, "google_api_key"), \
            "GeminiConfig should NOT have 'google_api_key' attribute - use 'api_key' instead"

    def test_view_content_page_would_fail_with_google_api_key(self):
        """Test that accessing config.google_api_key raises AttributeError."""
        config = GeminiConfig(
            api_key="test-key-123",
            content_root="/tmp/test",
            chunks_dir="/tmp/test_chunks"
        )

        # This is what View Content page was trying to do - it should fail
        with pytest.raises(AttributeError, match="'GeminiConfig' object has no attribute 'google_api_key'"):
            _ = config.google_api_key

    def test_correct_api_key_access_pattern(self):
        """Test the correct way to access API key from GeminiConfig."""
        config = GeminiConfig(
            api_key="test-key-456",
            content_root="/tmp/test",
            chunks_dir="/tmp/test_chunks"
        )

        # This is the CORRECT way to access the API key
        api_key = config.api_key
        assert api_key == "test-key-456"

    def test_genai_sdk_import(self):
        """Test that google.genai SDK is available (not google.generativeai)."""
        # The new SDK should be available
        import google.genai
        assert hasattr(google.genai, 'Client')

        # The old SDK should NOT be used
        try:
            import google.generativeai
            # If it's installed, that's fine, but View Content page should NOT use it
        except ImportError:
            # Expected - old SDK not installed
            pass
