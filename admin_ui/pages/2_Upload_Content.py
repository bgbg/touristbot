"""Content upload page."""

import streamlit as st
import tempfile
import os
import shutil

from admin_ui.upload_helper import UploadManager
from backend.store_registry import StoreRegistry

st.title("📤 Upload Content")

# Check if session state is initialized
if "config" not in st.session_state:
    st.error("❌ Session not initialized. Please return to the main page.")
    st.stop()

config = st.session_state.config
storage = st.session_state.storage

# Area/Site selection
st.markdown("### 1. Select Location")
col1, col2 = st.columns(2)

with col1:
    area = st.text_input("Area", placeholder="e.g., hefer_valley", help="Location area identifier")

with col2:
    site = st.text_input("Site", placeholder="e.g., agamon_hefer", help="Location site identifier")

# File upload
st.markdown("### 2. Upload Files")
uploaded_files = st.file_uploader(
    "Choose files to upload",
    type=["docx", "pdf", "txt", "md"],
    accept_multiple_files=True,
    help="Supported formats: DOCX, PDF, TXT, MD"
)

# Options
force_reupload = st.checkbox(
    "Force re-upload",
    help="Re-upload files even if they were already uploaded"
)

# Upload button
upload_disabled = not (area and site and uploaded_files)
if upload_disabled:
    if not area or not site:
        st.info("👆 Please enter both area and site to enable upload")
    elif not uploaded_files:
        st.info("👆 Please select files to upload")

if st.button("🚀 Upload", disabled=upload_disabled):
    # Save to temp directory
    temp_dir = tempfile.mkdtemp(prefix="admin_upload_")

    try:
        # Save uploaded files to temp directory
        file_paths = []
        for uploaded_file in uploaded_files:
            file_path = os.path.join(temp_dir, uploaded_file.name)
            with open(file_path, "wb") as fp:
                fp.write(uploaded_file.getbuffer())
            file_paths.append(file_path)

        st.info(f"📁 Saved {len(file_paths)} file(s) to temporary directory")

        # Initialize upload manager
        manager = UploadManager(config)

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        def progress_callback(current, total, message):
            """Update progress bar and status text."""
            if total > 0:
                progress_bar.progress(current / total)
            status_text.text(f"⏳ {message}")

        # Upload
        with st.spinner("Uploading files..."):
            result = manager.upload_files(
                file_paths=file_paths,
                area=area,
                site=site,
                force=force_reupload,
                progress_callback=progress_callback
            )

        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()

        # Display results
        if result["errors"]:
            st.warning("⚠️ Upload completed with some errors")
        else:
            st.success("✅ Upload complete!")

        # Metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Files Uploaded", result["uploaded_count"])

        with col2:
            st.metric("Files Skipped", result["skipped_count"])

        with col3:
            st.metric("Images Extracted", result.get("image_count", 0))

        with col4:
            st.metric("Topics Generated", result.get("topics_count", 0))

        # Show errors if any
        if result["errors"]:
            with st.expander("⚠️ View Errors", expanded=True):
                for error in result["errors"]:
                    st.error(error)

    except Exception as e:
        st.error(f"❌ Upload failed: {e}")
        import traceback
        with st.expander("🔍 Error Details"):
            st.code(traceback.format_exc())

    finally:
        # Cleanup temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            st.warning(f"⚠️ Cleanup warning: {cleanup_error}")

# Show existing locations
st.markdown("---")
st.markdown("### Existing Locations")

try:
    registry = StoreRegistry(
        storage_backend=storage,
        gcs_path=config.store_registry_gcs_path
    )

    locations = registry.list_all()

    if locations:
        from collections import defaultdict
        by_area = defaultdict(list)

        for (loc_area, loc_site), store_name in locations.items():
            by_area[loc_area].append(loc_site)

        # Display as expandable sections
        for loc_area in sorted(by_area.keys()):
            with st.expander(f"📍 {loc_area}", expanded=False):
                sites = by_area[loc_area]
                for loc_site in sorted(sites):
                    st.markdown(f"- `{loc_site}`")

        st.caption(f"Total: {len(locations)} location(s)")
    else:
        st.info("No content uploaded yet. Upload your first files above!")

except Exception as e:
    st.error(f"Error loading locations: {e}")
