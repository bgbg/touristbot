"""Tourism RAG - Admin Backoffice UI"""

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st

from backend.gcs_storage import get_storage_backend
from backend.conversation_storage.conversations import ConversationStore
from backend.store_registry import StoreRegistry
from backend.image_registry import ImageRegistry
from gemini.config import GeminiConfig

st.set_page_config(
    page_title="Tourism RAG - Admin",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)


def check_auth():
    """Verify GCS credentials configured."""
    try:
        config = GeminiConfig.from_yaml()
        storage = get_storage_backend(
            bucket_name=config.gcs_bucket_name,
            credentials_json=config.gcs_credentials_json
        )
        # Test connection with a lightweight operation
        # Note: file_exists returns False for non-existent files, doesn't raise
        # Try listing files instead to verify permissions
        try:
            storage.list_files("metadata/", "*.json")
        except Exception as list_error:
            raise Exception(f"GCS permission test failed: {list_error}")

        return True
    except Exception as e:
        st.error(f"❌ Authentication failed: {e}")
        st.info("💡 See .streamlit/secrets.toml.example for GCS credentials setup")
        st.markdown("""
        **Setup Steps:**
        1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
        2. Add your GCS service account credentials under `[gcs_credentials]`
        3. Restart the app
        """)
        return False


if not check_auth():
    st.stop()

# Initialize session state
if "config" not in st.session_state:
    st.session_state.config = GeminiConfig.from_yaml()
    st.session_state.storage = get_storage_backend(
        bucket_name=st.session_state.config.gcs_bucket_name,
        credentials_json=st.session_state.config.gcs_credentials_json
    )

# Sidebar
st.sidebar.title("🔧 Admin Backoffice")
st.sidebar.info(f"📦 Bucket: {st.session_state.config.gcs_bucket_name}")

# Main page
st.title("🔧 Tourism RAG - Admin Backoffice")
st.markdown("""
### Available Features

- **📤 Upload Content**: Add documents to locations
- **📁 View Content**: Browse uploaded files
- **💬 Conversations**: Monitor and manage chats

Use the sidebar to navigate between pages.
""")

# Quick stats
st.markdown("### Quick Stats")

col1, col2, col3 = st.columns(3)

with col1:
    try:
        registry = StoreRegistry(
            storage_backend=st.session_state.storage,
            gcs_path=st.session_state.config.store_registry_gcs_path
        )
        locations = registry.list_all()
        st.metric("📍 Locations", len(locations))
    except Exception as e:
        st.metric("📍 Locations", "Error")
        st.caption(f"⚠️ {str(e)[:50]}")

with col2:
    try:
        conv_store = ConversationStore(
            st.session_state.storage,
            gcs_prefix="conversations"
        )
        conversations = conv_store.list_all_conversations(limit=1000)
        st.metric("💬 Conversations", len(conversations))
    except Exception as e:
        st.metric("💬 Conversations", "Error")
        st.caption(f"⚠️ {str(e)[:50]}")

with col3:
    try:
        img_registry = ImageRegistry(
            storage_backend=st.session_state.storage,
            gcs_path=st.session_state.config.image_registry_gcs_path
        )
        stats = img_registry.get_stats()
        st.metric("🖼️ Images", stats.get("total_images", 0))
    except Exception as e:
        st.metric("🖼️ Images", "Error")
        st.caption(f"⚠️ {str(e)[:50]}")

# Footer
st.markdown("---")
st.caption("Tourism RAG Admin Backoffice • Built with Streamlit")

# Auto-redirect to View Content page (make it the default landing page)
st.switch_page("pages/2_View_Content.py")
