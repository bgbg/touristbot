"""
Conversation Storage - GCS-backed conversation history management.

Stores conversations as JSON files in GCS bucket.
Format: conversations/{conversation_id}.json
"""

import json
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Optional

from backend.gcs_storage import StorageBackend

logger = logging.getLogger(__name__)

# Conversation expiration timeout in hours
# Messages older than this will be filtered from conversation history
CONVERSATION_TIMEOUT_HOURS = 3


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    citations: Optional[List[dict]] = None
    images: Optional[List[dict]] = None


@dataclass
class Conversation:
    """A conversation with its metadata and message history."""

    conversation_id: str
    area: str
    site: str
    created_at: str
    updated_at: str
    messages: List[Message]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "conversation_id": self.conversation_id,
            "area": self.area,
            "site": self.site,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [asdict(msg) for msg in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """Create from dictionary loaded from JSON."""
        messages = [Message(**msg) for msg in data.get("messages", [])]
        return cls(
            conversation_id=data["conversation_id"],
            area=data["area"],
            site=data["site"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            messages=messages,
        )


class ConversationStore:
    """
    Manages conversation storage in GCS.

    Conversations are stored as JSON files at:
    conversations/{conversation_id}.json
    """

    def __init__(self, storage_backend: StorageBackend, gcs_prefix: str = "conversations"):
        """
        Initialize conversation store.

        Args:
            storage_backend: GCS storage backend
            gcs_prefix: GCS prefix for conversation files (default: "conversations")
        """
        self.storage = storage_backend
        self.gcs_prefix = gcs_prefix.rstrip("/")
        logger.info(f"ConversationStore initialized with prefix: {self.gcs_prefix}")

    def _get_gcs_path(self, conversation_id: str) -> str:
        """Get GCS path for a conversation."""
        return f"{self.gcs_prefix}/{conversation_id}.json"

    def _filter_expired_messages(
        self, conversation: Conversation
    ) -> tuple[Conversation, int]:
        """
        Filter out messages older than CONVERSATION_TIMEOUT_HOURS.

        Args:
            conversation: Conversation to filter

        Returns:
            Tuple of (filtered_conversation, expired_count)
            - filtered_conversation: Conversation with only recent messages
            - expired_count: Number of messages that were filtered out
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=CONVERSATION_TIMEOUT_HOURS)
        original_count = len(conversation.messages)

        # Filter messages, keeping only those newer than cutoff
        recent_messages = []
        for msg in conversation.messages:
            try:
                # Parse timestamp (format: "2024-01-01T00:00:00Z")
                msg_time = datetime.fromisoformat(msg.timestamp.rstrip("Z"))

                if msg_time >= cutoff_time:
                    recent_messages.append(msg)
            except (ValueError, AttributeError) as e:
                # Backward compatibility: if timestamp is missing or invalid, keep the message
                logger.warning(
                    f"Message has invalid/missing timestamp in {conversation.conversation_id}, "
                    f"keeping message: {e}"
                )
                recent_messages.append(msg)

        # Update conversation with filtered messages
        conversation.messages = recent_messages
        expired_count = original_count - len(recent_messages)

        if expired_count > 0:
            logger.info(
                f"Filtered {expired_count} expired message(s) from {conversation.conversation_id} "
                f"(cutoff: {cutoff_time.isoformat()}Z, kept: {len(recent_messages)})"
            )

        return conversation, expired_count

    def create_conversation(
        self, area: str, site: str, conversation_id: Optional[str] = None
    ) -> Conversation:
        """
        Create a new conversation.

        Args:
            area: Location area
            site: Location site
            conversation_id: Optional conversation ID (generates UUID if not provided)

        Returns:
            New Conversation object
        """
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        now = datetime.utcnow().isoformat() + "Z"
        conversation = Conversation(
            conversation_id=conversation_id,
            area=area,
            site=site,
            created_at=now,
            updated_at=now,
            messages=[],
        )

        logger.info(f"Created new conversation: {conversation_id} ({area}/{site})")
        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Load conversation from GCS and filter expired messages.

        Messages older than CONVERSATION_TIMEOUT_HOURS are automatically filtered out.
        The conversation file in GCS remains unchanged (read-time filtering only).

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation object with filtered messages if found, None otherwise
        """
        gcs_path = self._get_gcs_path(conversation_id)

        try:
            # Load from GCS
            content = self.storage.read_file(gcs_path)
            if not content:
                logger.info(f"Conversation not found: {conversation_id}")
                return None

            # Parse JSON
            data = json.loads(content)
            conversation = Conversation.from_dict(data)

            # Apply expiration filter (read-time filtering)
            conversation, expired_count = self._filter_expired_messages(conversation)

            logger.info(
                f"Loaded conversation: {conversation_id} "
                f"({len(conversation.messages)} messages, {expired_count} expired)"
            )
            return conversation

        except FileNotFoundError:
            logger.info(f"Conversation not found in GCS: {conversation_id}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse conversation JSON: {conversation_id} - {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading conversation: {conversation_id} - {e}")
            return None

    def save_conversation(self, conversation: Conversation) -> bool:
        """
        Save conversation to GCS.

        Args:
            conversation: Conversation to save

        Returns:
            True if save succeeded, False otherwise
        """
        # Update timestamp
        conversation.updated_at = datetime.utcnow().isoformat() + "Z"

        gcs_path = self._get_gcs_path(conversation.conversation_id)

        try:
            # Serialize to JSON
            content = json.dumps(conversation.to_dict(), ensure_ascii=False, indent=2)

            # Write to GCS
            self.storage.write_file(gcs_path, content)

            logger.info(
                f"Saved conversation: {conversation.conversation_id} "
                f"({len(conversation.messages)} messages)"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to save conversation: {conversation.conversation_id} - {e}"
            )
            return False

    def add_message(
        self,
        conversation: Conversation,
        role: str,
        content: str,
        citations: Optional[List[dict]] = None,
        images: Optional[List[dict]] = None,
    ) -> Conversation:
        """
        Add a message to conversation and save.

        Args:
            conversation: Conversation to update
            role: Message role ("user" or "assistant")
            content: Message content
            citations: Optional list of citations
            images: Optional list of images

        Returns:
            Updated conversation
        """
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat() + "Z",
            citations=citations,
            images=images,
        )

        conversation.messages.append(message)
        self.save_conversation(conversation)

        logger.debug(f"Added {role} message to conversation: {conversation.conversation_id}")
        return conversation

    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation from GCS.

        Args:
            conversation_id: Conversation ID to delete

        Returns:
            True if deletion succeeded, False otherwise
        """
        gcs_path = self._get_gcs_path(conversation_id)

        try:
            self.storage.delete_file(gcs_path)
            logger.info(f"Deleted conversation: {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete conversation: {conversation_id} - {e}")
            return False


    def list_conversations(self, prefix: str = "") -> List[str]:
        """
        List all conversation IDs from GCS.

        Args:
            prefix: Optional prefix filter for conversation IDs (e.g., "whatsapp_")

        Returns:
            List of conversation IDs (without .json extension)
        """
        try:
            # List all files in conversations prefix
            files = self.storage.list_files(self.gcs_prefix)

            # Extract conversation IDs from file paths
            conversation_ids = []
            for file_path in files:
                # Extract filename from path (e.g., "conversations/conv_123.json" -> "conv_123.json")
                filename = file_path.split("/")[-1]

                # Remove .json extension
                if filename.endswith(".json"):
                    conversation_id = filename[:-5]  # Remove ".json"

                    # Apply prefix filter if provided
                    if not prefix or conversation_id.startswith(prefix):
                        conversation_ids.append(conversation_id)

            logger.info(
                f"Listed {len(conversation_ids)} conversation(s) "
                f"(prefix: '{prefix}' if prefix else 'all')"
            )
            return conversation_ids

        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []

    def delete_conversations_older_than(self, hours: int, prefix: str = "") -> int:
        """
        Delete conversations where ALL messages are older than specified hours.

        This is an administrative cleanup operation. Conversations are only deleted
        if every message in the conversation is older than the threshold.

        Args:
            hours: Age threshold in hours
            prefix: Optional prefix filter (e.g., "whatsapp_")

        Returns:
            Number of conversations deleted
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        deleted_count = 0

        try:
            # List all conversations
            conversation_ids = self.list_conversations(prefix=prefix)

            logger.info(
                f"Bulk deletion: checking {len(conversation_ids)} conversation(s) "
                f"for deletion (cutoff: {cutoff_time.isoformat()}Z, prefix: '{prefix}')"
            )

            # Check each conversation
            for conversation_id in conversation_ids:
                try:
                    # Load conversation (without expiration filtering to check all messages)
                    gcs_path = self._get_gcs_path(conversation_id)
                    content = self.storage.read_file(gcs_path)
                    if not content:
                        continue

                    data = json.loads(content)
                    conversation = Conversation.from_dict(data)

                    # Check if ALL messages are older than cutoff
                    if not conversation.messages:
                        # Empty conversation - skip (keep it)
                        continue

                    all_messages_old = True
                    for msg in conversation.messages:
                        try:
                            msg_time = datetime.fromisoformat(msg.timestamp.rstrip("Z"))
                            if msg_time >= cutoff_time:
                                # Found a recent message - don't delete
                                all_messages_old = False
                                break
                        except (ValueError, AttributeError):
                            # Invalid timestamp - keep conversation
                            all_messages_old = False
                            break

                    # Delete if all messages are old
                    if all_messages_old:
                        if self.delete_conversation(conversation_id):
                            deleted_count += 1
                            logger.info(
                                f"Bulk deletion: deleted {conversation_id} "
                                f"(all {len(conversation.messages)} messages older than cutoff)"
                            )

                except Exception as e:
                    logger.error(f"Error checking conversation {conversation_id}: {e}")
                    continue

            logger.info(
                f"Bulk deletion complete: deleted {deleted_count} of {len(conversation_ids)} conversations"
            )
            return deleted_count

        except Exception as e:
            logger.error(f"Bulk deletion failed: {e}")
            return deleted_count

    def list_all_conversations(
        self,
        limit: Optional[int] = None,
        area_filter: Optional[str] = None,
        site_filter: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """
        List all conversations with metadata (without loading full message history).

        Args:
            limit: Maximum number of conversations to return
            area_filter: Filter by area
            site_filter: Filter by site
            start_date: Filter by created_at >= start_date (ISO format)
            end_date: Filter by created_at <= end_date (ISO format)

        Returns:
            List of dicts with conversation_id, area, site, created_at, updated_at,
            message_count, last_query (first 100 chars of last user message)
        """
        try:
            # List all conversation files
            files = self.storage.list_files(self.gcs_prefix, "*.json")
            logger.info(f"Found {len(files)} conversation files")

            conversations = []

            for file_path in files:
                try:
                    # Read conversation metadata
                    content = self.storage.read_file(file_path)
                    data = json.loads(content)

                    # Apply filters
                    if area_filter and data.get("area") != area_filter:
                        continue
                    if site_filter and data.get("site") != site_filter:
                        continue

                    # Date filters
                    if start_date:
                        created_at = data.get("created_at", "")
                        if created_at < start_date:
                            continue
                    if end_date:
                        created_at = data.get("created_at", "")
                        if created_at > end_date:
                            continue

                    # Extract metadata
                    messages = data.get("messages", [])
                    message_count = len(messages)

                    # Get last user message preview
                    last_query = ""
                    for msg in reversed(messages):
                        if msg.get("role") == "user":
                            last_query = msg.get("content", "")[:100]
                            break

                    conversations.append({
                        "conversation_id": data.get("conversation_id", ""),
                        "area": data.get("area", ""),
                        "site": data.get("site", ""),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "message_count": message_count,
                        "last_query": last_query,
                    })

                except Exception as e:
                    logger.warning(f"Error processing conversation file {file_path}: {e}")
                    continue

            # Sort by updated_at DESC
            conversations.sort(key=lambda x: x["updated_at"], reverse=True)

            # Apply limit
            if limit and limit > 0:
                conversations = conversations[:limit]

            logger.info(f"Returning {len(conversations)} conversations after filtering")
            return conversations

        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return []

    def delete_conversations_bulk(self, conversation_ids: List[str]) -> dict:
        """
        Delete multiple conversations.

        Args:
            conversation_ids: List of conversation IDs to delete

        Returns:
            Dict with success_count, failed_count, failed_ids
        """
        success_count = 0
        failed_count = 0
        failed_ids = []

        for conversation_id in conversation_ids:
            if self.delete_conversation(conversation_id):
                success_count += 1
            else:
                failed_count += 1
                failed_ids.append(conversation_id)

        logger.info(
            f"Bulk delete completed: {success_count} succeeded, {failed_count} failed"
        )

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_ids": failed_ids,
        }

    def get_conversations_stats(self) -> dict:
        """
        Get aggregate statistics about conversations.

        Returns:
            Dict with total_conversations, by_area, by_site, date_range
        """
        try:
            conversations = self.list_all_conversations()

            if not conversations:
                return {
                    "total_conversations": 0,
                    "by_area": {},
                    "by_site": {},
                    "date_range": {"earliest": None, "latest": None},
                }

            # Aggregate by area and site
            by_area = {}
            by_site = {}

            for conv in conversations:
                area = conv["area"]
                site = conv["site"]

                by_area[area] = by_area.get(area, 0) + 1
                by_site[f"{area}/{site}"] = by_site.get(f"{area}/{site}", 0) + 1

            # Find date range
            dates = [conv["created_at"] for conv in conversations if conv["created_at"]]
            earliest = min(dates) if dates else None
            latest = max(dates) if dates else None

            return {
                "total_conversations": len(conversations),
                "by_area": by_area,
                "by_site": by_site,
                "date_range": {"earliest": earliest, "latest": latest},
            }

        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {
                "total_conversations": 0,
                "by_area": {},
                "by_site": {},
                "date_range": {"earliest": None, "latest": None},
            }

