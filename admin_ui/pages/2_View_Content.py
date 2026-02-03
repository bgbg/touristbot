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
                file_search_store_name = entry.get("file_search_store_name") if entry else None

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

                # Show uploaded documents
                if file_search_store_name and file_count > 0:
                    with st.expander(f"📄 View {file_count} document(s)", expanded=False):
                        try:
                            # Initialize Gemini client and list documents
                            client = genai.Client(api_key=config.google_api_key)
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

                                    # Try to download and display document content
                                    if doc_uri:
                                        with st.expander("View document content"):
                                            try:
                                                import requests
                                                import google.generativeai as genai

                                                # Get file via Gemini Files API
                                                genai.configure(api_key=config.google_api_key)
                                                file_obj = genai.get_file(name=doc_name)

                                                # Try to get text content
                                                if hasattr(file_obj, 'text') and file_obj.text:
                                                    st.text_area("Content", file_obj.text, height=300)
                                                elif doc_uri and doc_uri.startswith('http'):
                                                    # Try downloading via URI
                                                    response = requests.get(doc_uri, timeout=10)
                                                    if response.status_code == 200:
                                                        content = response.text
                                                        st.text_area("Content", content[:10000], height=300)
                                                        if len(content) > 10000:
                                                            st.caption(f"Showing first 10,000 characters of {len(content)}")
                                                    else:
                                                        st.warning(f"Could not download file (status {response.status_code})")
                                                else:
                                                    st.info("Document content not available for preview")
                                            except Exception as e:
                                                st.error(f"Error loading document: {str(e)[:100]}")

                                    st.markdown("---")
                            else:
                                st.info("No documents found for this location")

                        except Exception as e:
                            st.error(f"Error loading documents: {str(e)[:100]}")

                # Show sample images
                if images:
                    with st.expander(f"🖼️ View {len(images)} image(s)", expanded=False):
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

                                # Generate signed URL and display image
                                try:
                                    signed_url = storage.generate_signed_url(img.gcs_path, expiration_minutes=15)
                                    st.image(signed_url, caption=caption_text, width=400)
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
