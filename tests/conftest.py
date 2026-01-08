"""
Shared pytest fixtures for all tests
"""

import pytest
from unittest.mock import Mock
import tempfile
import os


@pytest.fixture
def mock_genai_client():
    """Mock Gemini API client for testing"""
    client = Mock()
    client.models.generate_content.return_value = Mock(text="Mock response")
    return client


@pytest.fixture
def sample_text():
    """Sample text content for testing chunking and parsing"""
    return """This is a sample document for testing.

It has multiple paragraphs with different content. This paragraph contains several sentences. Each sentence adds more content to test chunking logic.

This is the third paragraph. It should help test boundary detection and chunk splitting logic."""


@pytest.fixture
def sample_text_long():
    """Longer sample text for testing chunking with multiple chunks"""
    paragraphs = []
    for i in range(20):
        paragraphs.append(f"This is paragraph {i}. " + "Sample text content. " * 10)
    return "\n\n".join(paragraphs)


@pytest.fixture
def temp_text_file(tmp_path):
    """Create a temporary text file for testing"""
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("This is test content.\nWith multiple lines.\n", encoding="utf-8")
    return file_path


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary YAML config file for testing"""
    config_content = """
model: gemini-1.5-pro
temperature: 0.7
max_tokens: 1000
"""
    file_path = tmp_path / "test_config.yaml"
    file_path.write_text(config_content, encoding="utf-8")
    return file_path
