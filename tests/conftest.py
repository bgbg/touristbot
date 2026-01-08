"""
Shared pytest fixtures for all tests

Note: These fixtures are defined for future test expansion.
Currently used by tests in tests/gemini/ for mocking and test data.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory for test files

    Automatically cleaned up after test completes
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_file(temp_dir):
    """
    Create a temporary text file with sample content

    Returns path to the file
    """
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("Sample test content\nLine 2\nLine 3\n", encoding="utf-8")
    return file_path


@pytest.fixture
def sample_config_yaml(temp_dir):
    """
    Create a sample config.yaml file for testing

    Returns path to the config file
    """
    config_content = """
content_root: "data/locations"

app:
  name: "Test Tourism App"
  type: "museum_tourism"
  language: "English"

gemini_rag:
  model: "gemini-1.5-pro"
  temperature: 0.7
  chunk_size: 1000

storage:
  gcs_bucket_name: "test_bucket"
  enable_local_cache: false
"""
    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_content, encoding="utf-8")
    return config_path


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
