"""View uploaded content."""

import streamlit as st
import json
from collections import defaultdict
from datetime import datetime

from backend.store_registry import StoreRegistry
from backend.image_registry import ImageRegistry
from gemini.file_search_store import FileSearchStoreManager
import google.genai as genai

st.title("📁 View Content")

# Check if session state is initialized
if "config" not in st.session_state:
    st.error("❌ Session not initialized. Please return to the main page.")
    st.stop()

config = st.session_state.config
storage = st.session_state.storage

# Initialize registries
registry = StoreRegistry(
    storage_backend=storage,
    gcs_path=config.store_registry_gcs_path
)

img_registry = ImageRegistry(
    storage_backend=storage,
    gcs_path=config.image_registry_gcs_path
)

# Location tree view
st.markdown("### Content Hierarchy")

try:
    locations = registry.list_all()

    if not locations:
        st.info("📂 No content uploaded yet. Use the Upload Content page to add files.")
        st.stop()

    # Group by area
    by_area = defaultdict(list)
    for (area, site), store_name in locations.items():
        entry = registry.get_entry(area, site)
        by_area[area].append((site, entry))

    # Display tree
    for area in sorted(by_area.keys()):
        with st.expander(f"📍 {area}", expanded=True):
            sites = by_area[area]

            for site, entry in sorted(sites, key=lambda x: x[0]):
                st.markdown(f"### 📌 {site}")

                metadata = entry.get("metadata", {}) if entry else {}
                # Get store name from locations dict (already available from list_all())
                file_search_store_name = locations.get((area, site))

                # Metrics row
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    file_count = metadata.get("file_count", 0)
                    st.metric("Files", file_count)

                with col2:
                    try:
                        images = img_registry.get_images_for_location(area, site)
                        st.metric("Images", len(images))
                    except Exception as e:
                        st.metric("Images", "Error")
                        st.caption(f"⚠️ {str(e)[:30]}")
                        images = []

                with col3:
                    # Get topics count
                    topics_path = f"topics/{area}/{site}/topics.json"
                    try:
                        topics_json = storage.read_file(topics_path)
                        topics = json.loads(topics_json)
                        st.metric("Topics", len(topics))
                    except FileNotFoundError:
                        st.metric("Topics", 0)
                    except Exception as e:
                        st.metric("Topics", "Error")
                        st.caption(f"⚠️ {str(e)[:30]}")

                with col4:
                    last_updated = metadata.get("last_updated", "Unknown")
                    if last_updated != "Unknown":
                        try:
                            dt = datetime.fromisoformat(last_updated.replace("Z", ""))
                            last_updated_formatted = dt.strftime("%Y-%m-%d")
                        except Exception:
                            last_updated_formatted = last_updated[:10]
                    else:
                        last_updated_formatted = "Unknown"
                    st.metric("Last Updated", last_updated_formatted)

                # Delete button for this site
                delete_key = f"delete_{area}_{site}"
                confirm_key = f"confirm_delete_{area}_{site}"

                if st.button(f"🗑️ Delete all content for {site}", key=delete_key, type="secondary"):
                    st.session_state[confirm_key] = True

                if st.session_state.get(confirm_key, False):
                    st.warning(f"⚠️ This will permanently delete ALL content for **{area}/{site}**:")
                    st.markdown(f"""
                    - {file_count} document(s) from File Search Store
                    - {len(images) if 'images' in locals() else 0} image(s) from GCS
                    - Topics file
                    - All registry entries
                    """)

                    col_confirm, col_cancel = st.columns([1, 1])
                    with col_confirm:
                        if st.button(f"✓ Confirm Delete", key=f"confirm_yes_{area}_{site}", type="primary"):
                            try:
                                # Delete documents from File Search Store
                                deleted_docs = 0
                                failed_docs = 0
                                if file_search_store_name and file_count > 0:
                                    client = genai.Client(api_key=config.api_key)
                                    file_search_manager = FileSearchStoreManager(client)
                                    documents = file_search_manager.list_documents_in_store(file_search_store_name)

                                    for doc in documents:
                                        # Check if doc belongs to this area/site
                                        doc_area = None
                                        doc_site = None
                                        if hasattr(doc, "custom_metadata") and doc.custom_metadata:
                                            for meta_item in doc.custom_metadata:
                                                if hasattr(meta_item, "key") and hasattr(meta_item, "string_value"):
                                                    if meta_item.key == "area":
                                                        doc_area = meta_item.string_value
                                                    elif meta_item.key == "site":
                                                        doc_site = meta_item.string_value

                                        if doc_area == area and doc_site == site:
                                            doc_name = getattr(doc, "name", None)
                                            if doc_name:
                                                try:
                                                    file_search_manager.delete_document(file_search_store_name, doc_name)
                                                    deleted_docs += 1
                                                except Exception as e:
                                                    st.caption(f"Warning: Could not delete document {doc_name}: {str(e)[:50]}")
                                                    failed_docs += 1

                                # Delete images from GCS
                                deleted_images = 0
                                if 'images' in locals() and images:
                                    for img in images:
                                        try:
                                            # Delete image file from GCS
                                            storage.delete_file(img.gcs_path)
                                            # Delete File API upload if exists
                                            if img.file_api_uri:
                                                # Extract file name from URI and delete
                                                # File API URIs format: https://generativelanguage.googleapis.com/v1beta/files/{file_id}
                                                pass  # File API files auto-expire, no need to delete
                                            deleted_images += 1
                                        except Exception as e:
                                            st.caption(f"Warning: Could not delete image {img.gcs_path}: {str(e)[:50]}")

                                    # Remove from image registry
                                    img_registry.remove_images_for_location(area, site)

                                # Delete topics file
                                try:
                                    topics_path = f"topics/{area}/{site}/topics.json"
                                    storage.delete_file(topics_path)
                                except FileNotFoundError:
                                    pass  # Topics file doesn't exist, that's fine

                                # Remove from store registry
                                registry.remove_entry(area, site)

                                st.success(f"✓ Deleted all content for {area}/{site}:")
                                st.markdown(f"- Deleted {deleted_docs} document(s) from File Search Store")
                                if failed_docs > 0:
                                    st.markdown(f"- ⚠️ {failed_docs} document(s) could not be deleted (check warnings above)")
                                st.markdown(f"- Deleted {deleted_images} image(s) from GCS")
                                st.markdown(f"- Removed topics and registry entries")

                                # Clear confirmation state
                                st.session_state[confirm_key] = False

                                # Rerun to refresh the page
                                st.rerun()

                            except Exception as e:
                                st.error(f"Error during deletion: {str(e)}")
                                import traceback
                                with st.expander("Error details"):
                                    st.code(traceback.format_exc())

                    with col_cancel:
                        if st.button(f"✗ Cancel", key=f"confirm_no_{area}_{site}"):
                            st.session_state[confirm_key] = False
                            st.rerun()

                # Show uploaded documents
                if file_search_store_name and file_count > 0:
                    with st.expander(f"📄 View {file_count} document(s)", expanded=True):
                        try:
                            # Initialize Gemini client and list documents
                            client = genai.Client(api_key=config.api_key)
                            file_search_manager = FileSearchStoreManager(client)
                            documents = file_search_manager.list_documents_in_store(file_search_store_name)

                            # Filter documents for this area/site
                            site_docs = []
                            for doc in documents:
                                doc_area = None
                                doc_site = None
                                if hasattr(doc, "custom_metadata") and doc.custom_metadata:
                                    for meta_item in doc.custom_metadata:
                                        if hasattr(meta_item, "key") and hasattr(meta_item, "string_value"):
                                            if meta_item.key == "area":
                                                doc_area = meta_item.string_value
                                            elif meta_item.key == "site":
                                                doc_site = meta_item.string_value

                                if doc_area == area and doc_site == site:
                                    site_docs.append(doc)

                            if site_docs:
                                for doc in site_docs:
                                    doc_display_name = getattr(doc, "display_name", "Unknown")
                                    doc_name = getattr(doc, "name", "")
                                    doc_uri = getattr(doc, "uri", None)

                                    st.markdown(f"**{doc_display_name}**")
                                    st.caption(f"Resource: `{doc_name}`")

                                    # Show document metadata
                                    if hasattr(doc, "custom_metadata") and doc.custom_metadata:
                                        metadata_text = []
                                        for meta_item in doc.custom_metadata:
                                            if hasattr(meta_item, "key") and hasattr(meta_item, "string_value"):
                                                if meta_item.key == "doc":
                                                    metadata_text.append(f"Document ID: {meta_item.string_value}")
                                        if metadata_text:
                                            st.text(" | ".join(metadata_text))

                                    # Try to get document content from GCS
                                    # Original files might be stored in GCS at documents/{area}/{site}/{filename}
                                    try:
                                        # Try to find original file in GCS
                                        # File Search doesn't provide direct download, but we can try GCS paths
                                        possible_paths = [
                                            f"documents/{area}/{site}/{doc_display_name}",
                                            f"data/locations/{area}/{site}/{doc_display_name}",
                                        ]

                                        content = None
                                        content_path = None
                                        for gcs_path in possible_paths:
                                            try:
                                                content_bytes = storage.read_file_bytes(gcs_path)
                                                if content_bytes:
                                                    # Try to decode as text
                                                    try:
                                                        content = content_bytes.decode('utf-8')
                                                        content_path = gcs_path
                                                        break
                                                    except UnicodeDecodeError:
                                                        # Binary file, show size instead
                                                        st.info(f"📄 Binary file ({len(content_bytes):,} bytes) - stored at `{gcs_path}`")
                                                        content_path = gcs_path
                                                        break
                                            except (FileNotFoundError, IOError):
                                                continue

                                        if content:
                                            # Show text preview
                                            st.success(f"📄 File found in GCS: `{content_path}`")
                                            preview = content[:500]
                                            st.text(preview)
                                            if len(content) > 500:
                                                st.caption(f"... ({len(content) - 500:,} more characters)")

                                            # Full content in expander
                                            with st.expander("View full content"):
                                                st.text_area("Full content", content, height=400, label_visibility="collapsed")
                                        elif not content_path:
                                            # File not found in GCS, only in File Search Store
                                            st.info("📄 Document indexed in File Search Store (original file not in GCS)")
                                            st.caption(f"Resource ID: `{doc_name}`")
                                    except Exception as e:
                                        st.warning(f"Could not load file content: {str(e)[:80]}")

                                    st.markdown("---")
                            else:
                                st.info("No documents found for this location")

                        except Exception as e:
                            st.error(f"Error loading documents: {str(e)[:100]}")

                # Show sample images
                # Debug: Always show this section to see what's happening
                st.write(f"Debug: images variable exists: {' images' in locals()}, length: {len(images) if 'images' in locals() else 'N/A'}")

                if images and len(images) > 0:
                    with st.expander(f"🖼️ View {len(images)} image(s)", expanded=True):
                        # Group images by document
                        images_by_doc = defaultdict(list)
                        for img in images:
                            images_by_doc[img.doc].append(img)

                        for doc_name in sorted(images_by_doc.keys()):
                            st.markdown(f"**Document:** `{doc_name}`")
                            doc_images = images_by_doc[doc_name]

                            # Show first 5 images per document
                            for img in doc_images[:5]:
                                caption_text = f"Image {img.image_index}"
                                if img.caption:
                                    caption_text += f": {img.caption}"

                                # Download and display image (ADC doesn't support signed URLs)
                                try:
                                    # Download image data directly from GCS
                                    image_data = storage.read_file_bytes(img.gcs_path)
                                    st.image(image_data, caption=caption_text, width=400)
                                except Exception as e:
                                    st.caption(caption_text)
                                    st.error(f"Could not load image")
                                    with st.expander("Error details"):
                                        st.text(f"GCS Path: {img.gcs_path}")
                                        st.text(f"Error: {str(e)}")

                                # Show context if available
                                if img.context_before or img.context_after:
                                    context_preview = ""
                                    if img.context_before:
                                        context_preview += f"...{img.context_before[-50:]}"
                                    context_preview += " [IMAGE] "
                                    if img.context_after:
                                        context_preview += f"{img.context_after[:50]}..."
                                    with st.expander("View context"):
                                        st.text(context_preview)

                            if len(doc_images) > 5:
                                st.caption(f"... and {len(doc_images) - 5} more image(s)")

                            st.markdown("---")

                st.markdown("---")

    # Summary
    st.markdown("### Summary")
    st.caption(f"Total locations: {len(locations)}")

except Exception as e:
    st.error(f"❌ Error loading content: {e}")
    import traceback
    with st.expander("🔍 Error Details"):
        st.code(traceback.format_exc())
