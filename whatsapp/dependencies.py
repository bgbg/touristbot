"""
Dependency injection for WhatsApp bot.

Provides singleton instances of services via @lru_cache() pattern (following backend/).
"""

from __future__ import annotations

from functools import lru_cache

from backend.conversation_storage.conversations import ConversationStore
from backend.gcs_storage import GCSStorage

from .backend_client import BackendClient
from .background_tasks import BackgroundTaskManager
from .config import WhatsAppConfig
from .conversation import ConversationLoader
from .deduplication import MessageDeduplicator
from .logging_utils import EventLogger
from .whatsapp_client import WhatsAppClient


@lru_cache()
def get_config() -> WhatsAppConfig:
    """
    Get configuration singleton.

    Loads configuration from environment variables on first call,
    returns cached instance on subsequent calls.

    Returns:
        WhatsAppConfig instance

    Example:
        config = get_config()
        print(config.port)
    """
    config = WhatsAppConfig.from_env()
    config.validate()
    return config


@lru_cache()
def get_gcs_storage() -> GCSStorage:
    """
    Get GCS storage backend singleton.

    Uses Application Default Credentials (ADC) - no explicit credentials needed.

    Returns:
        GCSStorage instance

    Raises:
        Exception: If GCS initialization fails (fail-fast)
    """
    config = get_config()
    try:
        storage = GCSStorage(config.gcs_bucket, credentials_json=None)  # None enables ADC
        return storage
    except Exception as e:
        raise RuntimeError(f"Failed to initialize GCS storage: {e}")


@lru_cache()
def get_conversation_store() -> ConversationStore:
    """
    Get conversation store singleton.

    Uses GCS storage backend for conversation persistence.

    Returns:
        ConversationStore instance

    Example:
        store = get_conversation_store()
        conv = store.get_conversation("whatsapp_972501234567")
    """
    storage = get_gcs_storage()
    return ConversationStore(storage)


@lru_cache()
def get_event_logger() -> EventLogger:
    """
    Get event logger singleton.

    Logs events to daily JSONL files in configured log directory.

    Returns:
        EventLogger instance

    Example:
        logger = get_event_logger()
        logger.log_event("incoming_message", {"from": "972501234567"})
    """
    config = get_config()
    return EventLogger(config.log_dir)


@lru_cache()
def get_whatsapp_client() -> WhatsAppClient:
    """
    Get WhatsApp API client singleton.

    Returns:
        WhatsAppClient instance

    Example:
        client = get_whatsapp_client()
        client.send_text_message("+972501234567", "Hello!")
    """
    config = get_config()
    logger = get_event_logger()
    return WhatsAppClient(
        access_token=config.access_token,
        phone_number_id=config.phone_number_id,
        graph_api_version=config.graph_api_version,
        logger=logger
    )


@lru_cache()
def get_backend_client() -> BackendClient:
    """
    Get backend API client singleton.

    Returns:
        BackendClient instance

    Example:
        client = get_backend_client()
        response = client.call_qa_endpoint(
            "whatsapp_972501234567",
            "עמק חפר",
            "אגמון חפר",
            "מה יש לראות?",
            correlation_id="uuid-123"
        )
    """
    config = get_config()
    logger = get_event_logger()
    return BackendClient(
        base_url=config.backend_api_url,
        api_key=config.backend_api_key,
        logger=logger
    )


@lru_cache()
def get_conversation_loader() -> ConversationLoader:
    """
    Get conversation loader singleton.

    Wraps ConversationStore with WhatsApp-specific logic.

    Returns:
        ConversationLoader instance

    Example:
        loader = get_conversation_loader()
        conv = loader.load_conversation("972501234567")
    """
    config = get_config()
    conversation_store = get_conversation_store()
    return ConversationLoader(
        conversation_store=conversation_store,
        default_area=config.default_area,
        default_site=config.default_site
    )


@lru_cache()
def get_message_deduplicator() -> MessageDeduplicator:
    """
    Get message deduplicator singleton.

    Thread-safe deduplication cache with 5-minute TTL.

    Returns:
        MessageDeduplicator instance

    Example:
        dedup = get_message_deduplicator()
        if dedup.is_duplicate(msg_id):
            print("Duplicate message")
    """
    config = get_config()
    return MessageDeduplicator(ttl_seconds=config.message_dedup_ttl_seconds)


@lru_cache()
def get_task_manager() -> BackgroundTaskManager:
    """
    Get background task manager singleton.

    Manages background threads with timeout monitoring and graceful shutdown.

    Returns:
        BackgroundTaskManager instance

    Example:
        manager = get_task_manager()
        thread = manager.execute_async(
            process_message,
            phone="972501234567",
            text="שלום",
            correlation_id="uuid-123"
        )
    """
    config = get_config()
    logger = get_event_logger()
    return BackgroundTaskManager(
        timeout_seconds=config.background_task_timeout_seconds,
        logger=logger
    )
