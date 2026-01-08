"""
Shared pytest fixtures for all tests
"""

import os
import tempfile
from pathlib import Path

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
