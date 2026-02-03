"""
Conversations endpoint - Administrative conversation management.

Provides endpoints for:
- Deleting individual conversations
- Bulk deletion of old conversations

These are administrative operations requiring API key authentication.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import ApiKeyDep
from backend.conversation_storage.conversations import ConversationStore
from backend.dependencies import get_conversation_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    api_key: ApiKeyDep,
    conv_store: ConversationStore = Depends(get_conversation_store),
) -> dict:
    """
    Delete a specific conversation (administrative operation).

    Args:
        conversation_id: Conversation ID to delete
        api_key: API key (from auth dependency)
        conv_store: Conversation store (injected dependency)

    Returns:
        JSON response with:
        - status: "deleted"
        - conversation_id: The deleted conversation ID
        - message: Success message

    Raises:
        HTTPException 404: If conversation not found
    """
    logger.info(f"Delete conversation request: {conversation_id}")

    # Check if conversation exists
    conversation = conv_store.get_conversation(conversation_id)
    if not conversation:
        logger.warning(f"Conversation not found for deletion: {conversation_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Conversation not found: {conversation_id}",
        )

    # Delete conversation
    success = conv_store.delete_conversation(conversation_id)
    if not success:
        logger.error(f"Failed to delete conversation: {conversation_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {conversation_id}",
        )

    logger.info(f"Successfully deleted conversation: {conversation_id}")
    return {
        "status": "deleted",
        "conversation_id": conversation_id,
        "message": f"Conversation {conversation_id} deleted successfully",
    }


@router.delete("")
async def delete_conversations_bulk(
    api_key: ApiKeyDep,
    older_than_hours: int = Query(
        default=3,
        ge=1,
        description="Delete conversations where ALL messages are older than this many hours",
    ),
    prefix: Optional[str] = Query(
        default="",
        description="Optional prefix filter (e.g., 'whatsapp_')",
    ),
    conv_store: ConversationStore = Depends(get_conversation_store),
) -> dict:
    """
    Bulk delete conversations older than specified hours (administrative operation).

    Only deletes conversations where ALL messages are older than the threshold.
    This is a hard delete operation - conversation files are permanently removed from GCS.

    Args:
        api_key: API key (from auth dependency)
        older_than_hours: Age threshold in hours (default: 3)
        prefix: Optional conversation ID prefix filter (default: all conversations)
        conv_store: Conversation store (injected dependency)

    Returns:
        JSON response with:
        - status: "deleted"
        - count: Number of conversations deleted
        - older_than_hours: The threshold used
        - prefix: The prefix filter used
        - message: Success message
    """
    logger.info(
        f"Bulk delete request: older_than_hours={older_than_hours}, prefix='{prefix}'"
    )

    # Perform bulk deletion
    deleted_count = conv_store.delete_conversations_older_than(
        hours=older_than_hours, prefix=prefix
    )

    logger.info(
        f"Bulk deletion complete: deleted {deleted_count} conversation(s) "
        f"(threshold: {older_than_hours}h, prefix: '{prefix}')"
    )

    return {
        "status": "deleted",
        "count": deleted_count,
        "older_than_hours": older_than_hours,
        "prefix": prefix if prefix else "all",
        "message": f"Deleted {deleted_count} conversation(s) older than {older_than_hours} hours",
    }
