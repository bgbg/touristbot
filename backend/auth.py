"""
Authentication middleware for Tourism RAG Backend.

Simple API key authentication via Authorization header.
API keys are loaded from BACKEND_API_KEYS environment variable (comma-separated list).
"""

import logging
import os
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Security scheme for Bearer token
security = HTTPBearer()


def get_valid_api_keys() -> set[str]:
    """
    Load valid API keys from environment variable.

    Returns:
        Set of valid API keys (whitespace-trimmed, non-empty).
    """
    api_keys_str = os.getenv("BACKEND_API_KEYS", "")
    if not api_keys_str:
        logger.warning("BACKEND_API_KEYS not set - no valid API keys configured")
        return set()

    # Split by comma, strip whitespace, filter empty strings
    keys = {key.strip() for key in api_keys_str.split(",") if key.strip()}
    logger.info(f"Loaded {len(keys)} valid API keys from environment")
    return keys


# Cache valid API keys (loaded once at startup)
VALID_API_KEYS = get_valid_api_keys()


def verify_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(security)]
) -> str:
    """
    Verify API key from Authorization header.

    Args:
        credentials: HTTPAuthorizationCredentials from Bearer token.

    Returns:
        The valid API key (if authentication succeeds).

    Raises:
        HTTPException: 401 if API key is missing or invalid.
    """
    if not credentials:
        logger.warning("Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = credentials.credentials

    if not VALID_API_KEYS:
        logger.error("No valid API keys configured - rejecting all requests")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API authentication not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if api_key not in VALID_API_KEYS:
        logger.warning(f"Invalid API key attempt: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"Valid API key: {api_key[:8]}...")
    return api_key


# Dependency for protected endpoints
ApiKeyDep = Annotated[str, Depends(verify_api_key)]
