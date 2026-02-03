"""Conversation management."""

import streamlit as st
from datetime import datetime

from backend.conversation_storage.conversations import ConversationStore

st.title("💬 Conversations")

# Check if session state is initialized
if "config" not in st.session_state:
    st.error("❌ Session not initialized. Please return to the main page.")
    st.stop()

config = st.session_state.config
storage = st.session_state.storage

# Initialize conversation store
conv_store = ConversationStore(storage, gcs_prefix="conversations")

# Filters
st.markdown("### Filters")

col1, col2, col3 = st.columns(3)

with col1:
    area_filter = st.text_input("Area", placeholder="All areas", help="Filter by area")

with col2:
    site_filter = st.text_input("Site", placeholder="All sites", help="Filter by site")

with col3:
    limit = st.number_input(
        "Limit",
        min_value=10,
        max_value=1000,
        value=100,
        help="Maximum conversations to load"
    )

# List conversations
try:
    conversations = conv_store.list_all_conversations(
        limit=limit,
        area_filter=area_filter if area_filter else None,
        site_filter=site_filter if site_filter else None
    )

    st.markdown(f"### Found {len(conversations)} conversation(s)")

    if not conversations:
        st.info("💬 No conversations found. Try adjusting filters or check back later.")
        st.stop()

    # Selection for bulk operations
    if "selected_ids" not in st.session_state:
        st.session_state.selected_ids = set()

    # Display table header
    header_cols = st.columns([0.5, 2, 2, 1, 1.5, 1])
    header_cols[0].markdown("**Select**")
    header_cols[1].markdown("**Conversation ID**")
    header_cols[2].markdown("**Location**")
    header_cols[3].markdown("**Messages**")
    header_cols[4].markdown("**Updated**")
    header_cols[5].markdown("**Actions**")

    st.markdown("---")

    # Display conversations
    for conv in conversations:
        conv_id = conv["conversation_id"]

        cols = st.columns([0.5, 2, 2, 1, 1.5, 1])

        with cols[0]:
            checkbox_key = f"check_{conv_id}"
            is_selected = st.checkbox(
                "",
                key=checkbox_key,
                label_visibility="collapsed",
                value=conv_id in st.session_state.selected_ids
            )
            if is_selected:
                st.session_state.selected_ids.add(conv_id)
            else:
                st.session_state.selected_ids.discard(conv_id)

        with cols[1]:
            st.text(conv_id[:30] + ("..." if len(conv_id) > 30 else ""))

        with cols[2]:
            st.text(f"{conv['area']} / {conv['site']}")

        with cols[3]:
            st.text(f"{conv['message_count']}")

        with cols[4]:
            try:
                updated = datetime.fromisoformat(conv['updated_at'].replace("Z", ""))
                st.text(updated.strftime("%Y-%m-%d %H:%M"))
            except Exception:
                st.text(conv['updated_at'][:16])

        with cols[5]:
            if st.button("View", key=f"view_{conv_id}"):
                st.session_state.selected_conversation = conv_id
                st.rerun()

    # Bulk operations
    st.markdown("---")
    st.markdown("### Bulk Operations")

    selected_count = len(st.session_state.selected_ids)

    if selected_count > 0:
        st.info(f"✅ Selected: {selected_count} conversation(s)")

        if st.button(f"🗑️ Delete {selected_count} conversation(s)", type="primary"):
            if st.session_state.get("confirm_bulk_delete"):
                # Perform delete
                result = conv_store.delete_conversations_bulk(
                    list(st.session_state.selected_ids)
                )

                st.success(f"✅ Deleted {result['success_count']} conversation(s)")

                if result['failed_count'] > 0:
                    st.error(f"❌ Failed to delete {result['failed_count']} conversation(s)")
                    if result['failed_ids']:
                        with st.expander("View failed IDs"):
                            for failed_id in result['failed_ids']:
                                st.text(failed_id)

                # Clear selection and confirmation state
                st.session_state.selected_ids = set()
                st.session_state.confirm_bulk_delete = False
                st.rerun()
            else:
                st.warning("⚠️ Click again to confirm deletion")
                st.session_state.confirm_bulk_delete = True
    else:
        st.text("Select conversations above to enable bulk operations")
        # Reset confirmation if nothing selected
        st.session_state.confirm_bulk_delete = False

    # View selected conversation
    if st.session_state.get("selected_conversation"):
        st.markdown("---")
        st.markdown("### Conversation Details")

        conv_id = st.session_state.selected_conversation
        conv = conv_store.get_conversation(conv_id)

        if conv:
            # Conversation header
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**ID:** `{conv_id}`")
                st.markdown(f"**Location:** {conv.area} / {conv.site}")
                st.markdown(f"**Created:** {conv.created_at}")
                st.markdown(f"**Updated:** {conv.updated_at}")
                st.markdown(f"**Messages:** {len(conv.messages)}")

            with col2:
                if st.button("❌ Close", key="close_conversation"):
                    del st.session_state.selected_conversation
                    st.rerun()

            st.markdown("---")

            # Display messages
            for msg in conv.messages:
                with st.chat_message(msg.role):
                    st.markdown(msg.content)

                    # Citations
                    if msg.citations:
                        with st.expander(f"📚 Citations ({len(msg.citations)})"):
                            for cite in msg.citations:
                                source = cite.get('source', 'Unknown')
                                text = cite.get('text', '')
                                st.markdown(f"**Source:** {source}")
                                if text:
                                    st.caption(text[:200] + ("..." if len(text) > 200 else ""))
                                st.markdown("---")

                    # Images
                    if msg.images:
                        with st.expander(f"🖼️ Images ({len(msg.images)})"):
                            for img in msg.images:
                                caption = img.get('caption', '')
                                if caption:
                                    st.caption(caption)
                                uri = img.get('uri', '')
                                if uri:
                                    st.text(f"URI: {uri[:60]}...")

            # Delete conversation button
            st.markdown("---")
            if st.button("🗑️ Delete This Conversation", type="secondary"):
                if st.session_state.get("confirm_single_delete"):
                    if conv_store.delete_conversation(conv_id):
                        st.success("✅ Conversation deleted")
                        del st.session_state.selected_conversation
                        st.session_state.confirm_single_delete = False
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete conversation")
                else:
                    st.warning("⚠️ Click again to confirm deletion")
                    st.session_state.confirm_single_delete = True
        else:
            st.error(f"❌ Conversation not found: {conv_id}")
            if st.button("Clear Selection"):
                del st.session_state.selected_conversation
                st.rerun()

except Exception as e:
    st.error(f"❌ Error loading conversations: {e}")
    import traceback
    with st.expander("🔍 Error Details"):
        st.code(traceback.format_exc())
