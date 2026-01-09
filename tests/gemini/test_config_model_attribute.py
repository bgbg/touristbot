"""
Unit tests to verify GeminiConfig model attribute access patterns.

This test suite ensures that all code correctly accesses the model configuration
using the proper attribute name (model_name, not model).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from gemini.config import GeminiConfig


class TestConfigModelAttribute:
    """Test GeminiConfig model attribute naming"""

    def test_config_has_model_name_attribute(self):
        """Verify GeminiConfig has model_name attribute"""
        config = GeminiConfig(
            api_key="test_key",
            content_root="/test/content",
            chunks_dir="/test/chunks",
            model_name="gemini-2.0-flash"
        )

        assert hasattr(config, "model_name")
        assert config.model_name == "gemini-2.0-flash"

    def test_config_does_not_have_model_attribute(self):
        """Verify GeminiConfig does not have model attribute (common bug)"""
        config = GeminiConfig(
            api_key="test_key",
            content_root="/test/content",
            chunks_dir="/test/chunks",
            model_name="gemini-2.0-flash"
        )

        # This should raise AttributeError if we try to access .model
        with pytest.raises(AttributeError, match="'GeminiConfig' object has no attribute 'model'"):
            _ = config.model

    def test_extract_topics_accepts_model_name(self):
        """Verify extract_topics_from_chunks accepts model_name string"""
        from gemini.topic_extractor import extract_topics_from_chunks

        # Mock the dependencies
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = '["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Topic 5"]'
        mock_client.models.generate_content.return_value = mock_response

        with patch('gemini.topic_extractor.PromptLoader') as MockPromptLoader:
            mock_config = Mock()
            mock_config.temperature = 0.3
            mock_config.format.return_value = ("system instruction", "user message")
            MockPromptLoader.load.return_value = mock_config

            # This should work with model_name string
            topics = extract_topics_from_chunks(
                chunks="test content",
                area="Test Area",
                site="Test Site",
                model="gemini-2.0-flash",  # String parameter, not config.model
                client=mock_client
            )

            assert len(topics) == 5
            assert all(isinstance(t, str) for t in topics)

    def test_ui_button_should_use_model_name(self):
        """Test that UI code pattern should use config.model_name not config.model"""
        config = GeminiConfig(
            api_key="test_key",
            content_root="/test/content",
            chunks_dir="/test/chunks",
            model_name="gemini-2.0-flash"
        )

        # Correct usage pattern
        model_to_use = config.model_name
        assert model_to_use == "gemini-2.0-flash"

        # Incorrect usage pattern should fail
        with pytest.raises(AttributeError):
            _ = config.model  # This is the bug we're fixing
