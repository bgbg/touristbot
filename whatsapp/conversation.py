"""
Conversation management for WhatsApp bot.

Provides interface for loading, creating, and resetting conversations stored in GCS.
Area and site are always passed explicitly at call sites for multi-number routing.
"""

from __future__ import annotations

from typing import Optional

from backend.conversation_storage.conversations import ConversationStore, Conversation

from .logging_utils import eprint


class ConversationLoader:
    """
    Conversation loader for WhatsApp bot.

    Wraps ConversationStore with WhatsApp-specific logic:
    - Conversation ID generation (whatsapp_{normalized_phone})
    - Reset command handling

    Area and site are passed explicitly at each call site, supporting
    multi-number routing where each phone number maps to a different location.
    """

    def __init__(self, conversation_store: ConversationStore):
        """
        Initialize conversation loader.

        Args:
            conversation_store: GCS-backed conversation store
        """
        self.conversation_store = conversation_store

    def load_conversation(
        self,
        phone: str,
        area: str,
        site: str,
        profile_name: Optional[str] = None,
    ) -> Conversation:
        """
        Load existing conversation or create new one.

        Args:
            phone: Normalized phone number (digits only)
            area: Location area (used when creating new conversation)
            site: Location site (used when creating new conversation)
            profile_name: Optional WhatsApp profile name (from webhook)

        Returns:
            Conversation object with message history

        Raises:
            Exception: If GCS storage fails

        Example:
            loader = ConversationLoader(store)
            conv = loader.load_conversation("972501234567", "עמק חפר", "אגמון חפר", profile_name="John Doe")
            print(f"Loaded {len(conv.messages)} messages")
        """
        conversation_id = self._generate_conversation_id(phone)

        try:
            # Try to load existing conversation from GCS
            conv = self.conversation_store.get_conversation(conversation_id)
            if conv:
                # Update profile name if provided (handles name changes)
                if profile_name:
                    self.conversation_store.update_profile_name(conv, profile_name)

                # Check if all messages were expired (conversation exists but empty after filtering)
                if len(conv.messages) == 0:
                    eprint(f"[CONV] Loaded conversation with all messages expired: {conversation_id}")
                    eprint(f"[CONV] Starting fresh conversation after expiration")
                else:
                    eprint(f"[CONV] Loaded existing conversation: {conversation_id} ({len(conv.messages)} messages)")
                return conv
            else:
                # Create new conversation
                eprint(f"[CONV] Creating new conversation: {conversation_id}")
                conv = self.conversation_store.create_conversation(
                    area=area,
                    site=site,
                    conversation_id=conversation_id,
                    profile_name=profile_name,
                )
                # Save immediately to GCS
                self.conversation_store.save_conversation(conv)
                return conv
        except Exception as e:
            eprint(f"[ERROR] Failed to load/create conversation: {e}")
            # Fail-fast: re-raise exception to trigger error response
            raise

    def reset_conversation(self, phone: str, area: str, site: str) -> Conversation:
        """
        Delete old conversation and create fresh one.

        Used for "reset" or "התחל מחדש" commands.

        Args:
            phone: Normalized phone number (digits only)
            area: Location area for the new conversation
            site: Location site for the new conversation

        Returns:
            New conversation object (empty message history)

        Raises:
            Exception: If GCS storage fails

        Example:
            loader = ConversationLoader(store)
            conv = loader.reset_conversation("972501234567", "עמק חפר", "אגמון חפר")
        """
        conversation_id = self._generate_conversation_id(phone)

        try:
            # Delete old conversation
            self.conversation_store.delete_conversation(conversation_id)

            # Create new conversation
            conv = self.conversation_store.create_conversation(
                area=area,
                site=site,
                conversation_id=conversation_id,
            )

            # Save immediately to GCS
            self.conversation_store.save_conversation(conv)

            eprint(f"[CONV] Conversation reset: {conversation_id}")
            return conv
        except Exception as e:
            eprint(f"[ERROR] Failed to reset conversation: {e}")
            raise

    @staticmethod
    def _generate_conversation_id(phone: str) -> str:
        """
        Generate conversation ID from phone number.

        Args:
            phone: Normalized phone number (digits only)

        Returns:
            Conversation ID (format: whatsapp_{phone})

        Example:
            conv_id = ConversationLoader._generate_conversation_id("972501234567")
            # Returns: "whatsapp_972501234567"
        """
        return f"whatsapp_{phone}"
