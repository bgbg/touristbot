"""
Unit tests for authentication middleware.
"""

import os
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth import get_valid_api_keys, verify_api_key


class TestGetValidApiKeys:
    """Tests for get_valid_api_keys function."""

    def test_no_api_keys_env_var(self):
        """Test with missing BACKEND_API_KEYS environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            keys = get_valid_api_keys()
            assert keys == set()

    def test_empty_api_keys(self):
        """Test with empty BACKEND_API_KEYS."""
        with patch.dict(os.environ, {"BACKEND_API_KEYS": ""}):
            keys = get_valid_api_keys()
            assert keys == set()

    def test_single_api_key(self):
        """Test with single API key."""
        with patch.dict(os.environ, {"BACKEND_API_KEYS": "test-key-123"}):
            keys = get_valid_api_keys()
            assert keys == {"test-key-123"}

    def test_multiple_api_keys(self):
        """Test with multiple comma-separated API keys."""
        with patch.dict(
            os.environ, {"BACKEND_API_KEYS": "key1,key2,key3"}
        ):
            keys = get_valid_api_keys()
            assert keys == {"key1", "key2", "key3"}

    def test_api_keys_with_whitespace(self):
        """Test that whitespace is trimmed from API keys."""
        with patch.dict(
            os.environ, {"BACKEND_API_KEYS": " key1 , key2 ,  key3  "}
        ):
            keys = get_valid_api_keys()
            assert keys == {"key1", "key2", "key3"}

    def test_api_keys_with_empty_entries(self):
        """Test that empty entries are filtered out."""
        with patch.dict(
            os.environ, {"BACKEND_API_KEYS": "key1,,,key2,  ,key3"}
        ):
            keys = get_valid_api_keys()
            assert keys == {"key1", "key2", "key3"}


class TestVerifyApiKey:
    """Tests for verify_api_key function."""

    def test_missing_credentials(self):
        """Test with missing credentials."""
        with patch("backend.auth.VALID_API_KEYS", {"test-key"}):
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(None)
            assert exc_info.value.status_code == 401
            assert "Missing Authorization header" in exc_info.value.detail

    def test_no_valid_keys_configured(self):
        """Test when no valid API keys are configured."""
        with patch("backend.auth.VALID_API_KEYS", set()):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="any-key"
            )
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(credentials)
            assert exc_info.value.status_code == 401
            assert "not configured" in exc_info.value.detail

    def test_invalid_api_key(self):
        """Test with invalid API key."""
        with patch("backend.auth.VALID_API_KEYS", {"valid-key-123"}):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="invalid-key"
            )
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(credentials)
            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    def test_valid_api_key(self):
        """Test with valid API key."""
        valid_key = "valid-key-123"
        with patch("backend.auth.VALID_API_KEYS", {valid_key}):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=valid_key
            )
            result = verify_api_key(credentials)
            assert result == valid_key

    def test_valid_api_key_multiple_keys(self):
        """Test with valid API key when multiple keys are configured."""
        keys = {"key1", "key2", "key3"}
        with patch("backend.auth.VALID_API_KEYS", keys):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="key2"
            )
            result = verify_api_key(credentials)
            assert result == "key2"
