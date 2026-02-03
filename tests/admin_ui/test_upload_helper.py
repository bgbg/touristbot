"""Tests for upload helper module."""

import os
import tempfile
import pytest
from pathlib import Path

from admin_ui.upload_helper import UploadManager
from gemini.config import GeminiConfig


@pytest.fixture
def config():
    """Create a test configuration."""
    return GeminiConfig.from_yaml()


@pytest.fixture
def manager(config):
    """Create an UploadManager instance."""
    return UploadManager(config)


class TestFileValidation:
    """Tests for file validation logic."""

    def test_validate_files_valid_docx(self, manager):
        """Test validation accepts valid DOCX file."""
        # Create a temporary DOCX file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            valid, invalid = manager.validate_files([temp_path])

            assert len(valid) == 1
            assert temp_path in valid
            assert len(invalid) == 0
        finally:
            os.unlink(temp_path)

    def test_validate_files_valid_pdf(self, manager):
        """Test validation accepts valid PDF file."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            valid, invalid = manager.validate_files([temp_path])

            assert len(valid) == 1
            assert temp_path in valid
            assert len(invalid) == 0
        finally:
            os.unlink(temp_path)

    def test_validate_files_invalid_extension(self, manager):
        """Test validation rejects unsupported file types."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            valid, invalid = manager.validate_files([temp_path])

            assert len(valid) == 0
            assert len(invalid) == 1
            assert "Unsupported format" in invalid[0]
        finally:
            os.unlink(temp_path)

    def test_validate_files_nonexistent(self, manager):
        """Test validation rejects non-existent files."""
        fake_path = "/tmp/nonexistent_file_12345.docx"

        valid, invalid = manager.validate_files([fake_path])

        assert len(valid) == 0
        assert len(invalid) == 1
        assert "File not found" in invalid[0]

    def test_validate_files_empty_file(self, manager):
        """Test validation rejects empty files."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            # Create empty file
            temp_path = f.name

        try:
            valid, invalid = manager.validate_files([temp_path])

            assert len(valid) == 0
            assert len(invalid) == 1
            assert "File is empty" in invalid[0]
        finally:
            os.unlink(temp_path)

    def test_validate_files_too_large(self, manager):
        """Test validation rejects files larger than 50 MB."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            # Create a file larger than 50 MB (write 51 MB of zeros)
            f.write(b"0" * (51 * 1024 * 1024))
            temp_path = f.name

        try:
            valid, invalid = manager.validate_files([temp_path])

            assert len(valid) == 0
            assert len(invalid) == 1
            assert "File too large" in invalid[0]
        finally:
            os.unlink(temp_path)

    def test_validate_files_mixed_valid_invalid(self, manager):
        """Test validation separates valid and invalid files."""
        # Create valid file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"valid content")
            valid_path = f.name

        # Create invalid file (wrong extension)
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"invalid content")
            invalid_path = f.name

        try:
            valid, invalid = manager.validate_files([valid_path, invalid_path])

            assert len(valid) == 1
            assert valid_path in valid
            assert len(invalid) == 1
            assert "Unsupported format" in invalid[0]
        finally:
            os.unlink(valid_path)
            os.unlink(invalid_path)

    def test_validate_files_all_supported_formats(self, manager):
        """Test that all documented formats are accepted."""
        supported_formats = [".docx", ".pdf", ".txt", ".md"]
        temp_files = []

        try:
            # Create files for each format
            for ext in supported_formats:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                    f.write(b"test content")
                    temp_files.append(f.name)

            valid, invalid = manager.validate_files(temp_files)

            assert len(valid) == len(supported_formats)
            assert len(invalid) == 0
        finally:
            for temp_file in temp_files:
                os.unlink(temp_file)


class TestUploadManager:
    """Tests for UploadManager initialization."""

    def test_manager_initialization(self, config):
        """Test UploadManager can be initialized."""
        manager = UploadManager(config)
        assert manager.config == config

    def test_manager_requires_config(self):
        """Test UploadManager requires config parameter."""
        with pytest.raises(TypeError):
            UploadManager()


# Note: upload_files() is not unit tested here because it uses subprocess
# to call the existing CLI uploader. Integration tests should be used to
# verify the full upload workflow end-to-end.
