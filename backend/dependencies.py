"""
Dependency injection for FastAPI endpoints.

Provides singleton instances of storage, registries, and loggers.
"""

import os
from functools import lru_cache

from backend.conversation_storage.conversations import ConversationStore
from backend.gcs_storage import StorageBackend
from backend.image_registry import ImageRegistry
from backend.logging.query_logger import QueryLogger
from backend.store_registry import StoreRegistry


@lru_cache()
def get_storage_backend() -> StorageBackend:
    """Get GCS storage backend (singleton)."""
    gcs_bucket = os.getenv("GCS_BUCKET")
    if not gcs_bucket:
        raise ValueError("GCS_BUCKET environment variable not set")

    return StorageBackend(gcs_bucket)


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
