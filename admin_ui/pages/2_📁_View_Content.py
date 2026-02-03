"""View uploaded content."""

import streamlit as st
import json
from collections import defaultdict
from datetime import datetime

from backend.store_registry import StoreRegistry
from backend.image_registry import ImageRegistry

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

                # Metrics row
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    file_count = metadata.get("file_count", "?")
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

                # Show sample images
                if images:
                    with st.expander(f"🖼️ View {len(images)} image(s)"):
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
                                st.caption(caption_text)

                                # Show context if available
                                if img.context_before or img.context_after:
                                    context_preview = ""
                                    if img.context_before:
                                        context_preview += f"...{img.context_before[-50:]}"
                                    context_preview += " [IMAGE] "
                                    if img.context_after:
                                        context_preview += f"{img.context_after[:50]}..."
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
