#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tourism RAG Admin Panel - Streamlit App

Features:
- Query logs exploration (reads directly from GCS)
- Conversation management
- System monitoring

Usage:
    streamlit run admin/app.py
"""

import json
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Import backend modules for direct GCS access
from backend.gcs_storage import GCSStorage
from backend.query_logging.query_logger import QueryLogger

# =============================================================================
# Page Configuration
# =============================================================================

st.set_page_config(
    page_title="Tourism RAG Admin",
    page_icon="⚙️",
    layout="wide"
)

# =============================================================================
# GCS Configuration
# =============================================================================

# Load GCS bucket from secrets
gcs_bucket = st.secrets.get("GCS_BUCKET")

if not gcs_bucket:
    st.error("Missing `GCS_BUCKET` in .streamlit/secrets.toml")
    st.info("Please configure `GCS_BUCKET` with your GCS bucket name")
    st.stop()

# Initialize storage backend (direct GCS access)
@st.cache_resource
def get_storage():
    """Initialize GCS storage backend (singleton)"""
    # Try to get credentials from Streamlit secrets
    gcs_credentials = st.secrets.get("gcs_credentials")

    if gcs_credentials:
        # Convert Streamlit secrets dict to JSON string
        credentials_json = json.dumps(dict(gcs_credentials))
        return GCSStorage(bucket_name=gcs_bucket, credentials_json=credentials_json)
    else:
        # Fall back to ADC (Application Default Credentials)
        # ADC requires GOOGLE_CLOUD_PROJECT environment variable to be set
        import os
        if not os.getenv("GOOGLE_CLOUD_PROJECT"):
            # Set default project for ADC
            os.environ["GOOGLE_CLOUD_PROJECT"] = "gen-lang-client-0860749390"
        return GCSStorage(bucket_name=gcs_bucket, credentials_json=None)

@st.cache_resource
def get_query_logger():
    """Initialize query logger (singleton)"""
    storage = get_storage()
    return QueryLogger(storage)

storage = get_storage()
query_logger = get_query_logger()

# =============================================================================
# Sidebar Navigation
# =============================================================================

st.sidebar.title("⚙️ Admin Panel")
st.sidebar.markdown(f"**GCS Bucket:** `{gcs_bucket}`")
st.sidebar.markdown("---")

# Tab selection
selected_tab = st.sidebar.radio(
    "Navigation",
    ["📊 Query Logs", "💬 Conversations", "🔍 System Info"],
    index=0
)

st.sidebar.markdown("---")

# Cache clear button
if st.sidebar.button("🔄 Clear Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

# =============================================================================
# TAB 1: Query Logs Explorer
# =============================================================================

if selected_tab == "📊 Query Logs":
    st.title("📊 Query Logs Explorer")
    st.markdown("Explore query logs stored in GCS (JSONL format)")

    # Date selection
    col1, col2, col3 = st.columns([2, 2, 3])

    with col1:
        # Default to today
        default_date = datetime.now().date()
        selected_date = st.date_input(
            "Select Date",
            value=default_date,
            max_value=datetime.now().date(),
            help="Select a date to view query logs"
        )

    with col2:
        # Multi-day range option
        use_range = st.checkbox("Date Range", value=False)
        if use_range:
            days_back = st.number_input(
                "Days to look back",
                min_value=1,
                max_value=30,
                value=7,
                help="Number of days to include (including selected date)"
            )

    with col3:
        st.markdown("**Quick Actions:**")
        if st.button("📅 Today"):
            selected_date = datetime.now().date()
            st.rerun()
        if st.button("📅 Yesterday"):
            selected_date = (datetime.now() - timedelta(days=1)).date()
            st.rerun()

    # Fetch logs
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def fetch_logs(date_str: str, use_range_param: bool, days_back_param: int) -> List[Dict[str, Any]]:
        """Fetch logs from GCS"""
        if use_range_param:
            end_date = datetime.strptime(date_str, "%Y-%m-%d")
            start_date = end_date - timedelta(days=days_back_param - 1)
            return query_logger.get_logs_range(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
        else:
            return query_logger.get_logs(date_str)

    date_str = selected_date.strftime("%Y-%m-%d")

    with st.spinner("Loading logs from GCS..."):
        if use_range:
            logs = fetch_logs(date_str, True, days_back)
        else:
            logs = fetch_logs(date_str, False, 0)

    # Display log count
    st.markdown(f"**Found {len(logs)} queries**")

    if not logs:
        st.info(f"No logs found for {date_str}")
        st.stop()

    # Filters
    st.markdown("---")
    st.subheader("🔍 Filters")

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    with filter_col1:
        # Area filter
        all_areas = sorted(set(log.get("area", "unknown") for log in logs))
        selected_areas = st.multiselect(
            "Area",
            options=all_areas,
            default=all_areas,
            help="Filter by location area"
        )

    with filter_col2:
        # Site filter
        all_sites = sorted(set(log.get("site", "unknown") for log in logs))
        selected_sites = st.multiselect(
            "Site",
            options=all_sites,
            default=all_sites,
            help="Filter by location site"
        )

    with filter_col3:
        # Error filter
        error_filter = st.selectbox(
            "Errors",
            options=["All", "Errors Only", "Success Only"],
            index=0,
            help="Filter by error status"
        )

    with filter_col4:
        # Search text
        search_text = st.text_input(
            "Search Query/Response",
            placeholder="Enter search term...",
            help="Search in query and response text"
        )

    # Apply filters
    filtered_logs = logs

    # Area filter
    if selected_areas:
        filtered_logs = [log for log in filtered_logs if log.get("area", "unknown") in selected_areas]

    # Site filter
    if selected_sites:
        filtered_logs = [log for log in filtered_logs if log.get("site", "unknown") in selected_sites]

    # Error filter
    if error_filter == "Errors Only":
        filtered_logs = [log for log in filtered_logs if log.get("error") is not None]
    elif error_filter == "Success Only":
        filtered_logs = [log for log in filtered_logs if log.get("error") is None]

    # Text search
    if search_text:
        search_lower = search_text.lower()
        filtered_logs = [
            log for log in filtered_logs
            if search_lower in log.get("query", "").lower()
            or search_lower in log.get("response_text", "").lower()
        ]

    st.markdown(f"**Showing {len(filtered_logs)} / {len(logs)} queries**")

    # Statistics
    st.markdown("---")
    st.subheader("📈 Statistics")

    stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)

    with stat_col1:
        st.metric(
            "Total Queries",
            len(filtered_logs)
        )

    with stat_col2:
        avg_latency = sum(log.get("latency_ms", 0) for log in filtered_logs) / len(filtered_logs) if filtered_logs else 0
        st.metric(
            "Avg Latency",
            f"{avg_latency:.0f} ms"
        )

    with stat_col3:
        error_count = sum(1 for log in filtered_logs if log.get("error") is not None)
        st.metric(
            "Errors",
            error_count,
            delta=f"{(error_count/len(filtered_logs)*100):.1f}%" if filtered_logs else "0%"
        )

    with stat_col4:
        total_citations = sum(log.get("citations_count", 0) for log in filtered_logs)
        avg_citations = total_citations / len(filtered_logs) if filtered_logs else 0
        st.metric(
            "Avg Citations",
            f"{avg_citations:.1f}"
        )

    with stat_col5:
        images_shown = sum(1 for log in filtered_logs if log.get("should_include_images") is True)
        st.metric(
            "Images Shown",
            images_shown,
            delta=f"{(images_shown/len(filtered_logs)*100):.1f}%" if filtered_logs else "0%"
        )

    # Log entries table
    st.markdown("---")
    st.subheader("📋 Log Entries")

    # Display mode
    display_mode = st.radio(
        "Display Mode",
        options=["Table", "Detailed Cards", "Raw JSON"],
        index=0,
        horizontal=True
    )

    if display_mode == "Table":
        # Convert to DataFrame
        df_data = []
        for log in filtered_logs:
            df_data.append({
                "Time": log.get("timestamp", "")[:19].replace("T", " "),
                "Area": log.get("area", ""),
                "Site": log.get("site", ""),
                "Query": log.get("query", "")[:50] + ("..." if len(log.get("query", "")) > 50 else ""),
                "Response": log.get("response_text", "")[:50] + ("..." if len(log.get("response_text", "")) > 50 else ""),
                "Latency (ms)": log.get("latency_ms", 0),
                "Citations": log.get("citations_count", 0),
                "Images": "✓" if log.get("should_include_images") else "✗",
                "Error": "✗ " + str(log.get("error", ""))[:30] if log.get("error") else "✓"
            })

        if df_data:
            df = pd.DataFrame(df_data)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Latency (ms)": st.column_config.NumberColumn(format="%.0f"),
                }
            )

    elif display_mode == "Detailed Cards":
        # Display as expandable cards
        for idx, log in enumerate(filtered_logs):
            timestamp = log.get("timestamp", "")[:19].replace("T", " ")
            query_preview = log.get("query", "")[:100]
            latency = log.get("latency_ms", 0)
            error = log.get("error")

            # Card header with key info
            card_title = f"**{timestamp}** | {log.get('area', '')}/{log.get('site', '')} | {latency:.0f}ms"
            if error:
                card_title += " | ⚠️ ERROR"

            with st.expander(f"{idx+1}. {query_preview}...", expanded=False):
                st.markdown(card_title)
                st.markdown("---")

                # Query
                st.markdown("**Query:**")
                st.text(log.get("query", ""))

                # Response
                st.markdown("**Response:**")
                st.text(log.get("response_text", ""))

                # Metadata
                meta_col1, meta_col2, meta_col3 = st.columns(3)
                with meta_col1:
                    st.markdown(f"**Model:** {log.get('model_name', 'N/A')}")
                    st.markdown(f"**Temperature:** {log.get('temperature', 'N/A')}")
                with meta_col2:
                    st.markdown(f"**Citations:** {log.get('citations_count', 0)}")
                    st.markdown(f"**Images:** {log.get('images_count', 0)}")
                with meta_col3:
                    st.markdown(f"**Conv ID:** `{log.get('conversation_id', 'N/A')[:16]}...`")
                    st.markdown(f"**Show Images:** {'✓' if log.get('should_include_images') else '✗'}")

                # Error details
                if error:
                    st.error(f"**Error:** {error}")

                # Citations
                citations = log.get("citations", [])
                if citations:
                    st.markdown("**Citations:**")
                    for i, citation in enumerate(citations, 1):
                        st.text(f"{i}. {citation.get('source', 'Unknown')}: {citation.get('text', '')[:100]}...")

                # Images
                images = log.get("images", [])
                if images:
                    st.markdown("**Images:**")
                    for i, img in enumerate(images, 1):
                        st.text(f"{i}. {img.get('caption', 'No caption')} (relevance: {img.get('relevance_score', 'N/A')})")

                # Image relevance data
                image_relevance = log.get("image_relevance", [])
                if image_relevance:
                    st.markdown("**Image Relevance Scores:**")
                    for i, rel in enumerate(image_relevance, 1):
                        uri_short = rel.get("image_uri", "")[-40:]
                        st.text(f"{i}. ...{uri_short}: {rel.get('relevance_score', 'N/A')}")

    else:  # Raw JSON
        st.json(filtered_logs, expanded=False)

# =============================================================================
# TAB 2: Conversations
# =============================================================================

elif selected_tab == "💬 Conversations":
    st.title("💬 Conversation Management")
    st.markdown("Browse and manage conversation history stored in GCS")

    st.info("🚧 Coming soon: Conversation browsing, deletion, and export functionality")

    # Placeholder for future implementation
    st.markdown("""
    **Planned features:**
    - List all active conversations
    - View conversation history
    - Delete old/expired conversations
    - Export conversations to CSV/JSON
    - Search conversations by phone number or text
    """)

# =============================================================================
# TAB 3: System Info
# =============================================================================

elif selected_tab == "🔍 System Info":
    st.title("🔍 System Information")
    st.markdown("GCS bucket status and registry information")

    st.info("🚧 Coming soon: System monitoring and registry inspection")

    # Placeholder for future implementation
    st.markdown("""
    **Planned features:**
    - GCS bucket usage statistics
    - Store registry contents
    - Image registry contents
    - Upload tracking status
    - File Search Store information
    """)
