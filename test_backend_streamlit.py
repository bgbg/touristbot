#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal Streamlit app to test the backend API
This is a temporary test app - full integration is in issue #34
"""

import streamlit as st
import requests
import json
from typing import Optional

# Page config
st.set_page_config(
    page_title="Tourism Guide (Backend Test)",
    page_icon="🗺️",
    layout="wide"
)

# Load secrets
backend_url = st.secrets.get("backend_api_url")
backend_key = st.secrets.get("backend_api_key")

if not backend_url or not backend_key:
    st.error("Missing backend configuration in .streamlit/secrets.toml")
    st.stop()

st.title("🗺️ Tourism Guide - Backend API Test")
st.caption(f"Backend: {backend_url}")
st.caption("⚠️ Temporary test app - Full frontend integration in issue #34")

# Sidebar - Location selection
st.sidebar.header("Select Location")

# Fetch locations
@st.cache_data(ttl=3600)
def get_locations():
    """Fetch available locations from backend"""
    try:
        response = requests.get(
            f"{backend_url}/locations",
            headers={"Authorization": f"Bearer {backend_key}"},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch locations: {e}")
        return {"locations": [], "areas": [], "count": 0}

locations_data = get_locations()

if locations_data["count"] == 0:
    st.sidebar.warning("No locations available. Upload content first.")
    st.info("""
    No content has been uploaded yet. To upload content:

    ```bash
    python gemini/main_upload.py --area <area> --site <site>
    ```

    For example:
    ```bash
    python gemini/main_upload.py --area hefer_valley --site agamon_hefer
    ```
    """)
    st.stop()

# Build area -> sites mapping
area_sites = {}
for loc in locations_data["locations"]:
    area = loc["area"]
    site = loc["site"]
    if area not in area_sites:
        area_sites[area] = []
    area_sites[area].append(site)

# Area selection
selected_area = st.sidebar.selectbox(
    "Area",
    options=sorted(area_sites.keys()),
    index=0
)

# Site selection
selected_site = st.sidebar.selectbox(
    "Site",
    options=sorted(area_sites[selected_area]),
    index=0
)

# Fetch topics for selected location
@st.cache_data(ttl=3600)
def get_topics(area: str, site: str):
    """Fetch topics for a location"""
    try:
        response = requests.get(
            f"{backend_url}/topics/{area}/{site}",
            headers={"Authorization": f"Bearer {backend_key}"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data.get("topics", [])
    except Exception as e:
        st.sidebar.error(f"Failed to fetch topics: {e}")
        return []

topics = get_topics(selected_area, selected_site)

if topics:
    st.sidebar.markdown("### Available Topics")
    for topic in topics:
        if st.sidebar.button(topic, key=f"topic_{topic}"):
            # Add topic as a query
            if "messages" not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "user", "content": topic})
            st.rerun()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Display citations if present
        if "citations" in message and message["citations"]:
            with st.expander("📚 Sources", expanded=False):
                for citation in message["citations"]:
                    st.markdown(f"- **{citation.get('title', 'Unknown')}**")
                    if citation.get("chunk_text"):
                        st.text(citation["chunk_text"][:200] + "...")

        # Display images if present
        if "images" in message and message["images"]:
            with st.expander("🖼️ Images", expanded=False):
                for img in message["images"]:
                    if img.get("gcs_public_url"):
                        st.image(img["gcs_public_url"], caption=img.get("caption", ""))
                        if img.get("context_text"):
                            st.caption(img["context_text"])

# Chat input
if prompt := st.chat_input("Ask about the location..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Call backend API
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Prepare request
                request_data = {
                    "area": selected_area,
                    "site": selected_site,
                    "query": prompt
                }

                if st.session_state.conversation_id:
                    request_data["conversation_id"] = st.session_state.conversation_id

                # Call backend
                response = requests.post(
                    f"{backend_url}/qa",
                    headers={
                        "Authorization": f"Bearer {backend_key}",
                        "Content-Type": "application/json"
                    },
                    json=request_data,
                    timeout=60
                )
                response.raise_for_status()

                # Parse response
                data = response.json()

                # Save conversation ID
                st.session_state.conversation_id = data.get("conversation_id")

                # Display response
                st.markdown(data["response_text"])

                # Build assistant message
                assistant_msg = {
                    "role": "assistant",
                    "content": data["response_text"],
                    "citations": data.get("citations", []),
                    "images": data.get("images", [])
                }

                st.session_state.messages.append(assistant_msg)

                # Display citations
                if data.get("citations"):
                    with st.expander("📚 Sources", expanded=False):
                        for citation in data["citations"]:
                            st.markdown(f"- **{citation.get('title', 'Unknown')}**")
                            if citation.get("chunk_text"):
                                st.text(citation["chunk_text"][:200] + "...")

                # Display images
                if data.get("images"):
                    with st.expander("🖼️ Images", expanded=False):
                        for img in data["images"]:
                            if img.get("gcs_public_url"):
                                st.image(img["gcs_public_url"], caption=img.get("caption", ""))
                                if img.get("context_text"):
                                    st.caption(img["context_text"])

                # Show latency
                st.caption(f"⏱️ Response time: {data.get('latency_ms', 0)}ms")

            except requests.exceptions.HTTPError as e:
                st.error(f"Backend error: {e.response.status_code} - {e.response.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"Network error: {str(e)}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.markdown("### Debug Info")
st.sidebar.text(f"Conversation ID: {st.session_state.conversation_id or 'None'}")
st.sidebar.text(f"Messages: {len(st.session_state.messages)}")

# Clear conversation button
if st.sidebar.button("🔄 Clear Conversation"):
    st.session_state.messages = []
    st.session_state.conversation_id = None
    st.rerun()
