"""
Dependency injection for FastAPI endpoints.

Provides singleton instances of storage, registries, and loggers.
"""

import os
from functools import lru_cache

from backend.conversation_storage.conversations import ConversationStore
from backend.gcs_storage import GCSStorage, StorageBackend
from backend.image_registry import ImageRegistry
from backend.query_logging.query_logger import QueryLogger
from backend.store_registry import StoreRegistry


@lru_cache()
def get_storage_backend() -> StorageBackend:
    """Get GCS storage backend (singleton)."""
    gcs_bucket = os.getenv("GCS_BUCKET")
    if not gcs_bucket:
        raise ValueError("GCS_BUCKET environment variable not set")

    # Get GCS credentials JSON if provided
    gcs_credentials_json = os.getenv("GCS_CREDENTIALS_JSON")

    # Alternatively, load from file path if GCS_CREDENTIALS_PATH is set
    gcs_credentials_path = os.getenv("GCS_CREDENTIALS_PATH")
    if not gcs_credentials_json and gcs_credentials_path:
        try:
            with open(gcs_credentials_path, "r", encoding="utf-8") as f:
                gcs_credentials_json = f.read()
        except FileNotFoundError as e:
            raise RuntimeError(
                f"GCS credentials file not found at path specified by GCS_CREDENTIALS_PATH: {gcs_credentials_path}"
            ) from e
        except PermissionError as e:
            raise RuntimeError(
                f"Permission denied when reading GCS credentials file: {gcs_credentials_path}"
            ) from e
        except OSError as e:
            raise RuntimeError(
                f"Error reading GCS credentials file ({gcs_credentials_path}): {e}"
            ) from e

    return GCSStorage(gcs_bucket, credentials_json=gcs_credentials_json)


@lru_cache()
def get_store_registry() -> StoreRegistry:
    """Get store registry (singleton)."""
    storage = get_storage_backend()
    return StoreRegistry(storage)


@lru_cache()
def get_image_registry() -> ImageRegistry:
    """Get image registry (singleton)."""
    storage = get_storage_backend()
    return ImageRegistry(storage)


@lru_cache()
def get_conversation_store() -> ConversationStore:
    """Get conversation store (singleton)."""
    storage = get_storage_backend()
    return ConversationStore(storage)


@lru_cache()
def get_query_logger() -> QueryLogger:
    """Get query logger (singleton)."""
    storage = get_storage_backend()
    return QueryLogger(storage)
