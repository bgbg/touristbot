#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tourism Guide RAG Q&A - Streamlit App

Usage:
    streamlit run gemini/main_qa.py
"""

import streamlit as st
import requests

# Page config
st.set_page_config(
    page_title="Tourism Guide",
    page_icon="🗺️",
    layout="wide"
)

# =============================================================================
# Backend Configuration
# =============================================================================

# Load backend configuration from secrets
backend_url = st.secrets.get("backend_api_url")
backend_key = st.secrets.get("backend_api_key")

if not backend_url:
    st.error("Missing `backend_api_url` in .streamlit/secrets.toml")
    st.info("Please configure `backend_api_url` with your backend endpoint URL")
    st.stop()

if not backend_key:
    st.error("Missing `backend_api_key` in .streamlit/secrets.toml")
    st.stop()

# Store backend URL in session state for easy access
st.session_state.backend_url = backend_url

# =============================================================================
# Sidebar
# =============================================================================

# Display active endpoint
st.sidebar.markdown(f"**Backend:** `{backend_url}`")

# Cache clear button
if st.sidebar.button("🔄 Clear Cache"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

# =============================================================================
# Title and Header
# =============================================================================

st.title("🗺️ Tourism Guide")

# =============================================================================
# Sidebar - Location Selection
# =============================================================================

st.sidebar.header("Select Location")

# Fetch locations
@st.cache_data(ttl=3600)
def get_locations(backend_url_param: str, backend_key_param: str):
    """Fetch available locations from backend"""
    try:
        response = requests.get(
            f"{backend_url_param}/locations",
            headers={"Authorization": f"Bearer {backend_key_param}"},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        try:
            error_detail = e.response.json().get("detail", e.response.text)
        except:
            error_detail = e.response.text
        st.error(f"Backend error ({e.response.status_code}): {error_detail}")
        return {"locations": [], "areas": [], "count": 0}
    except requests.exceptions.RequestException as e:
        st.error(f"Cannot connect to backend. Check that the server is running and .streamlit/secrets.toml is configured correctly.")
        st.error(f"Error: {str(e)}")
        return {"locations": [], "areas": [], "count": 0}
    except Exception as e:
        st.error(f"Failed to fetch locations: {e}")
        return {"locations": [], "areas": [], "count": 0}

locations_data = get_locations(st.session_state.backend_url, backend_key)

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

# Area selection - default to mazkeret_batya if available
area_options = sorted(area_sites.keys())
default_index = area_options.index("mazkeret_batya") if "mazkeret_batya" in area_options else 0

selected_area = st.sidebar.selectbox(
    "Area",
    options=area_options,
    index=default_index
)

# Site selection
selected_site = st.sidebar.selectbox(
    "Site",
    options=sorted(area_sites[selected_area]),
    index=0
)

# =============================================================================
# Sidebar - Available Topics
# =============================================================================

# Fetch topics for selected location
@st.cache_data(ttl=3600)
def get_topics(backend_url_param: str, backend_key_param: str, area: str, site: str):
    """Fetch topics for a location"""
    try:
        response = requests.get(
            f"{backend_url_param}/topics/{area}/{site}",
            headers={"Authorization": f"Bearer {backend_key_param}"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data.get("topics", [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # No topics found, not an error
            return []
        st.sidebar.error(f"Failed to fetch topics ({e.response.status_code}): {e.response.text}")
        return []
    except Exception as e:
        st.sidebar.warning(f"Could not load topics: {str(e)}")
        return []

topics = get_topics(st.session_state.backend_url, backend_key, selected_area, selected_site)

if topics:
    st.sidebar.markdown("### Available Topics")
    for topic in topics:
        if st.sidebar.button(topic, key=f"topic_{topic}"):
            # Add topic as a query
            if "messages" not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "user", "content": topic})
            st.rerun()

# =============================================================================
# Chat Interface
# =============================================================================

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
                    # Use backend format (source, text)
                    st.markdown(f"- **{citation.get('source', 'Unknown')}**")
                    citation_text = citation.get("text")
                    if citation_text:
                        st.text(citation_text[:200] + ("..." if len(citation_text) > 200 else ""))

        # Display images if present
        if "images" in message and message["images"]:
            with st.expander("🖼️ Images", expanded=False):
                for img in message["images"]:
                    # Prefer new backend fields (uri, file_api_uri), but fall back to legacy gcs_public_url
                    image_url = img.get("uri") or img.get("file_api_uri") or img.get("gcs_public_url")
                    if image_url:
                        st.image(image_url, caption=img.get("caption", ""))
                        # Prefer context but support legacy context_text
                        context_text = img.get("context") or img.get("context_text")
                        if context_text:
                            st.caption(context_text)

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
                    f"{st.session_state.backend_url}/qa",
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

                # Extract response text with fallback for unexpected types
                response_text = data["response_text"]

                # Defensive fallback: if response_text is not a string, convert it to string
                # Note: Backend validation (qa.py) should ensure this is always a string,
                # but this provides an extra safety layer for edge cases
                if not isinstance(response_text, str):
                    st.warning("⚠️ Backend returned unexpected response format. Converting response to text.")
                    response_text = str(response_text)

                # Display response
                st.markdown(response_text)

                # Build assistant message
                assistant_msg = {
                    "role": "assistant",
                    "content": response_text,
                    "citations": data.get("citations", []),
                    "images": data.get("images", [])
                }

                st.session_state.messages.append(assistant_msg)

                # Display citations
                if data.get("citations"):
                    with st.expander("📚 Sources", expanded=False):
                        for citation in data["citations"]:
                            st.markdown(f"- **{citation.get('source', 'Unknown')}**")
                            citation_text = citation.get("text")
                            if citation_text:
                                st.text(citation_text[:200] + ("..." if len(citation_text) > 200 else ""))

                # Display images
                if data.get("images"):
                    with st.expander("🖼️ Images", expanded=False):
                        for img in data["images"]:
                            image_url = img.get("uri") or img.get("file_api_uri") or img.get("gcs_public_url")
                            if image_url:
                                st.image(image_url, caption=img.get("caption", ""))
                                context_text = img.get("context") or img.get("context_text")
                                if context_text:
                                    st.caption(context_text)

                # Show latency
                st.caption(f"⏱️ Response time: {data.get('latency_ms', 0)}ms")

            except requests.exceptions.HTTPError as e:
                try:
                    error_detail = e.response.json().get("detail", e.response.text)
                except:
                    error_detail = e.response.text
                st.error(f"Backend error ({e.response.status_code}): {error_detail}")
            except requests.exceptions.RequestException as e:
                st.error("Cannot connect to backend. Check that the server is running and .streamlit/secrets.toml is configured correctly.")
                st.error(f"Error: {str(e)}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

# =============================================================================
# Sidebar - Debug Info and Controls
# =============================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("### Debug Info")
st.sidebar.text(f"Conversation ID: {st.session_state.conversation_id or 'None'}")
st.sidebar.text(f"Messages: {len(st.session_state.messages)}")

# Clear conversation button
if st.sidebar.button("🔄 Clear Conversation"):
    st.session_state.messages = []
    st.session_state.conversation_id = None
    st.rerun()
