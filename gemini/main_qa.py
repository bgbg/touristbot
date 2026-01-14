#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tourism Guide RAG Q&A - Streamlit App

Usage:
    streamlit run gemini/main_qa.py
"""

import json
import os
import sys
import time
from datetime import datetime

import streamlit as st

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
os.chdir(parent_dir)

import google.genai as genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Dict, Optional

from gemini.config import GeminiConfig
from gemini.conversation_utils import convert_messages_to_gemini_format
from gemini.image_registry import ImageRegistry
from gemini.prompt_loader import PromptLoader
from gemini.query_logger import QueryLogger
from gemini.storage import get_storage_backend
from gemini.store_registry import StoreRegistry
from gemini.topic_extractor import extract_topics_from_chunks
from gemini.upload_manager import UploadManager
from gemini.upload_tracker import UploadTracker


# Pydantic schema for structured output from Gemini API
class ImageAwareResponse(BaseModel):
    """Structured response from Gemini that includes image relevance signals."""

    response_text: str = Field(
        description="The main response text to the user's query in Hebrew or the query language"
    )
    should_include_images: bool = Field(
        description="Whether images should be included in this response. Set to false for initial greetings, true for substantive queries where images add value."
    )
    image_relevance: Dict[str, int] = Field(
        default_factory=dict,
        description="Relevance scores (0-100) for each image URI. Only include images that are contextually relevant to the query. Key is the image file_api_uri, value is relevance score."
    )


def load_chunks(chunks_dir: str, storage_backend=None) -> tuple[str, list[str]]:
    """
    Load all chunk files and combine into context

    Args:
        chunks_dir: Directory path (local) or blob prefix (GCS) containing chunks
        storage_backend: Optional storage backend (GCS or None for local filesystem)

    Returns:
        Tuple of (combined_context, list_of_chunk_filenames)
    """
    chunks = []
    chunk_files = []

    if storage_backend:
        # Use storage backend (GCS)
        try:
            # List all chunk files in GCS
            all_chunk_paths = storage_backend.list_files(chunks_dir, "*.txt")

            for chunk_path in sorted(all_chunk_paths):
                filename = os.path.basename(chunk_path)
                try:
                    content = storage_backend.read_file(chunk_path)
                    chunks.append(f"=== {filename} ===\n{content}\n")
                    chunk_files.append(filename)
                except Exception as e:
                    st.warning(f"Could not read {filename} from GCS: {e}")
        except Exception as e:
            st.warning(f"Could not list chunks from GCS: {e}")
            return "", []
    else:
        # Use local filesystem
        if not os.path.exists(chunks_dir):
            return "", []

        for root, dirs, files in os.walk(chunks_dir):
            for file in sorted(files):
                if file.endswith(".txt"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                            chunks.append(f"=== {file} ===\n{content}\n")
                            chunk_files.append(file)
                    except Exception as e:
                        st.warning(f"Could not read {file}: {e}")

    return "\n".join(chunks), chunk_files


def load_topics(area: str, site: str, storage_backend=None, config=None) -> list[str]:
    """
    Load topics for a specific location from GCS or local filesystem

    Args:
        area: Area name
        site: Site name
        storage_backend: Optional storage backend (GCS or None for local filesystem)
        config: Configuration object with chunks_dir path

    Returns:
        List of topic strings, empty list if topics not found
    """
    try:
        if storage_backend:
            # Load from GCS
            topics_path = f"topics/{area}/{site}/topics.json"
            topics_json = storage_backend.read_file(topics_path)
            topics = json.loads(topics_json)
            return topics if isinstance(topics, list) else []
        else:
            # Load from local filesystem
            topics_file = os.path.join("topics", area, site, "topics.json")
            if os.path.exists(topics_file):
                with open(topics_file, "r", encoding="utf-8") as f:
                    topics = json.load(f)
                    return topics if isinstance(topics, list) else []
            return []
    except Exception as e:
        # Topics not found or invalid, return empty list
        # This is expected for locations without generated topics
        return []


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "config" not in st.session_state:
        try:
            st.session_state.config = GeminiConfig.from_yaml()
        except Exception as e:
            st.error(f"Failed to load configuration: {e}")
            st.stop()

    if "client" not in st.session_state:
        try:
            st.session_state.client = genai.Client(
                api_key=st.session_state.config.api_key
            )
        except Exception as e:
            st.error(f"Failed to connect to Gemini API: {e}")
            st.stop()

    if "registry" not in st.session_state:
        try:
            # Create registry instance
            st.session_state.registry = StoreRegistry(
                st.session_state.config.registry_path
            )

            # Rebuild registry from Gemini Files API on startup (if enabled in config)
            # This syncs local registry with files that still exist in Gemini (48-hour window)
            if st.session_state.config.auto_rebuild_registry:
                try:
                    with st.spinner("Rebuilding registry from Gemini Files API..."):
                        stats = st.session_state.registry.rebuild_from_api(
                            st.session_state.client, merge_with_existing=True
                        )

                        # Show rebuild results if any files were found
                        if stats["files_found"] > 0:
                            if stats["files_parsed"] > 0:
                                st.success(
                                    f"✓ Registry rebuilt: {stats['registry_entries']} location(s) "
                                    f"from {stats['files_parsed']} file(s)"
                                )
                            elif stats["files_skipped"] > 0:
                                st.info(
                                    f"ℹ Found {stats['files_skipped']} file(s) without encoding. "
                                    f"Upload new content to use registry rebuild feature."
                                )
                except Exception as e:
                    # Rebuild failed - fallback to local registry
                    st.warning(
                        f"⚠ Could not rebuild registry from API: {e}. Using local registry."
                    )

        except Exception as e:
            st.error(f"Failed to load registry: {e}")
            st.stop()

    if "logger" not in st.session_state:
        log_path = os.path.join(
            os.path.dirname(st.session_state.config.registry_path), "query_log.jsonl"
        )
        st.session_state.logger = QueryLogger(
            log_path, area="", site=""
        )  # Will be updated per query

    if "tracker" not in st.session_state:
        st.session_state.tracker = UploadTracker(
            st.session_state.config.upload_tracking_path
        )

    if "storage_backend" not in st.session_state:
        try:
            # Initialize storage backend (GCS or cached GCS)
            st.session_state.storage_backend = get_storage_backend(
                bucket_name=st.session_state.config.gcs_bucket_name,
                credentials_json=st.session_state.config.gcs_credentials_json,
                enable_cache=st.session_state.config.enable_local_cache,
            )
            st.success("✓ Using GCS storage backend")
        except Exception as e:
            # Graceful fallback to local filesystem storage
            st.session_state.storage_backend = None
            st.info(
                f"ℹ Using local filesystem storage (GCS unavailable: {e})"
            )
            st.info(
                "To enable GCS storage, configure credentials in .streamlit/secrets.toml"
            )

    if "image_storage" not in st.session_state:
        try:
            # Initialize image storage for signed URL generation
            from gemini.image_storage import ImageStorage
            st.session_state.image_storage = ImageStorage(
                bucket_name=st.session_state.config.gcs_bucket_name,
                credentials_json=st.session_state.config.gcs_credentials_json,
            )
        except Exception as e:
            st.session_state.image_storage = None

    if "upload_manager" not in st.session_state:
        st.session_state.upload_manager = UploadManager(
            st.session_state.config,
            st.session_state.client,
            st.session_state.registry,
            st.session_state.tracker,
            st.session_state.storage_backend,
        )

    if "selected_area" not in st.session_state:
        all_stores = st.session_state.registry.list_all()
        if all_stores:
            (area, site), _ = list(all_stores.items())[0]
            st.session_state.selected_area = area
            st.session_state.selected_site = site
        else:
            st.session_state.selected_area = None
            st.session_state.selected_site = None

    # Note: context and chunk_files no longer needed with File Search
    # File Search provides context automatically via metadata filtering
    if "context" not in st.session_state:
        st.session_state.context = ""  # Kept for backwards compatibility
        st.session_state.chunk_files = []

    # Initialize or reload topics for current location
    # Always reload topics if location is set to ensure they're fresh
    if st.session_state.selected_area and st.session_state.selected_site:
        area = st.session_state.selected_area
        site = st.session_state.selected_site

        # Only reload if topics are not set OR if we need to verify they match current location
        # Store the location for which topics were loaded to detect stale topics
        current_location = f"{area}:{site}"

        if ("topics" not in st.session_state or
            st.session_state.get("topics_location") != current_location):
            topics = load_topics(area, site, st.session_state.storage_backend, st.session_state.config)
            st.session_state.topics = topics
            st.session_state.topics_location = current_location
    else:
        if "topics" not in st.session_state:
            st.session_state.topics = []
            st.session_state.topics_location = None

    if "image_registry" not in st.session_state:
        try:
            st.session_state.image_registry = ImageRegistry(
                st.session_state.config.image_registry_path
            )
        except Exception as e:
            # Graceful fallback - images won't be displayed
            st.session_state.image_registry = None
            st.info(f"ℹ Image registry not available: {e}")


def extract_citations(response, top_k: int = 5) -> list[dict]:
    """
    Extract citation information from response grounding metadata

    Args:
        response: Gemini API response object
        top_k: Maximum number of citations to return

    Returns:
        List of dicts with keys: uri, title, text, metadata
    """
    if not response.candidates:
        return []

    grounding_metadata = response.candidates[0].grounding_metadata
    if not grounding_metadata or not grounding_metadata.grounding_chunks:
        return []

    chunks = grounding_metadata.grounding_chunks[:top_k]
    citations = []

    for chunk in chunks:
        retrieved_context = chunk.retrieved_context
        citation = {
            "uri": retrieved_context.uri,
            "title": retrieved_context.title,
            "text": retrieved_context.text[:200] if retrieved_context.text else "",  # Preview
        }

        # Include custom metadata if available
        if hasattr(retrieved_context, "metadata"):
            citation["metadata"] = retrieved_context.metadata

        citations.append(citation)

    return citations


def _get_image_mime_type(image_format: str) -> str:
    """
    Get correct MIME type for image format

    Args:
        image_format: Image format (jpg, png, webp, etc.)

    Returns:
        Correct MIME type string for Gemini API
    """
    mime_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
        "heic": "image/heic",
        "heif": "image/heif",
    }
    return mime_types.get(image_format.lower(), "image/jpeg")


def _should_display_images(text: str, image_captions: list[str]) -> bool:
    """
    Determine if images should be displayed based on query/response relevance

    Args:
        text: Query text or response text to check
        image_captions: List of image captions to check for mentions

    Returns:
        True if images are relevant and should be displayed
    """
    text_lower = text.lower()

    # Visual content keywords (English and Hebrew)
    visual_keywords = [
        # English
        "image", "picture", "photo", "show", "look", "see", "view", "appearance",
        "bird", "birds", "animal", "animals", "pelican", "wildlife", "flora", "fauna",
        # Hebrew
        "תמונ", "צילום", "תצלום", "להראות", "נראה", "מראה", "ציפור", "ציפורים",
        "חי", "שקנא", "פלמינגו", "עגור"
    ]

    # Check if query/response contains visual keywords
    for keyword in visual_keywords:
        if keyword in text_lower:
            return True

    # Check if any image captions are mentioned in the text
    for caption in image_captions:
        if caption and len(caption) > 3:  # Avoid very short captions
            # Check if caption appears in text (case-insensitive, partial match)
            caption_words = caption.lower().split()
            for word in caption_words:
                if len(word) > 3 and word in text_lower:  # Meaningful words only
                    return True

    return False


def _get_image_display_url(gcs_path: str, bucket_name: str, image_storage=None) -> str:
    """
    Convert GCS path to displayable URL (signed URL for private images or public URL)

    Args:
        gcs_path: GCS path (can be gs://bucket/path or relative path)
        bucket_name: GCS bucket name
        image_storage: Optional ImageStorage instance for generating signed URLs

    Returns:
        URL for image display (signed URL if image_storage provided, otherwise public URL)
    """
    # Normalize path to remove gs:// prefix if present
    if gcs_path.startswith("gs://"):
        # Remove gs://bucket/ prefix to get relative path
        parts = gcs_path[5:].split('/', 1)
        if len(parts) > 1:
            gcs_path = parts[1]  # Get path after bucket name

    # If image_storage is available, generate signed URL for private images
    if image_storage:
        try:
            return image_storage.get_signed_url(gcs_path, expiration_minutes=60)
        except Exception:
            # Fall back to public URL if signed URL generation fails
            pass

    # Fallback: construct public URL (will only work if bucket/object is public)
    return f"https://storage.googleapis.com/{bucket_name}/{gcs_path}"


def get_response(
    question: str, area: str, site: str, messages: list[dict] | None = None
) -> tuple[str, float, list, list]:
    """
    Get response from Gemini API using File Search for semantic retrieval

    Args:
        question: The user's current question
        area: The geographic area for context
        site: The specific site for context
        messages: Optional list of previous messages in format {"role": str, "content": str}

    Returns:
        Tuple of (response_text, response_time_seconds, citations, images)
    """
    config = st.session_state.config
    client = st.session_state.client
    topics = st.session_state.topics if "topics" in st.session_state else []

    # Format topics as bullet list for the prompt
    topics_text = (
        "\n".join([f"- {topic}" for topic in topics]) if topics else "אין נושאים זמינים"
    )

    # Load prompt configuration from YAML (cached)
    prompt_path = f"{config.prompts_dir}tourism_qa.yaml"
    prompt_config = PromptLoader.load(prompt_path)

    # Build metadata filter for this location (AIP-160 syntax)
    metadata_filter = f"area={area} AND site={site}"

    # Get File Search Store name from registry
    file_search_store_name = st.session_state.registry.get_file_search_store_name()
    if not file_search_store_name:
        st.error("File Search Store not initialized. Please upload content first.")
        return "Error: File Search Store not found.", 0.0, []

    # Build conversation history from previous messages
    if messages is None:
        messages = []

    # Convert messages to Gemini API format (handles sliding window, role mapping, etc.)
    conversation_history = convert_messages_to_gemini_format(messages)

    # Format system instruction (without context - File Search provides it)
    system_instruction = prompt_config.system_prompt.format(
        area=area, site=site, topics=topics_text
    )

    # Format user message
    user_message = prompt_config.user_prompt.format(question=question)

    # Query images for this location
    images = []
    user_parts = [types.Part.from_text(text=user_message)]

    if st.session_state.image_registry:
        try:
            images = st.session_state.image_registry.get_images_for_location(
                area=area, site=site, doc=None
            )
            # Add image URIs to the user message for multimodal context
            for image in images[:5]:  # Limit to 5 images per query
                user_parts.append(
                    types.Part.from_uri(
                        file_uri=image.file_api_uri,
                        mime_type=_get_image_mime_type(image.image_format)
                    )
                )
        except Exception as e:
            # Log error but continue without images
            print(f"Warning: Could not load images: {e}")

    # Append current question as the final user message (with optional images)
    conversation_history.append(types.Content(role="user", parts=user_parts))

    # Use model and temperature from YAML prompt configuration
    model_name = prompt_config.model_name
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    temperature = prompt_config.temperature

    start_time = time.time()

    # Generate with File Search tool and structured output
    response = client.models.generate_content(
        model=model_name,
        contents=conversation_history,
        config={
            "system_instruction": system_instruction,
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_json_schema": ImageAwareResponse.model_json_schema(),
            "tools": [
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[file_search_store_name],
                        metadata_filter=metadata_filter,
                    )
                ),
            ],
        },
    )

    response_time = time.time() - start_time

    # Extract citations from grounding metadata
    citations = extract_citations(response)

    # Parse structured output
    try:
        structured_response = json.loads(response.text)
        response_text = structured_response.get("response_text", response.text)
        should_include_images = structured_response.get("should_include_images", True)
        image_relevance = structured_response.get("image_relevance", {})
    except (json.JSONDecodeError, KeyError) as e:
        # Fallback to raw response if parsing fails
        print(f"Warning: Could not parse structured output: {e}")
        response_text = response.text
        should_include_images = True
        image_relevance = {}

    # Filter images based on LLM-provided relevance scores
    relevant_images = []
    if images and should_include_images:
        # Filter images with relevance score >= 60
        for image in images:
            relevance_score = image_relevance.get(image.file_api_uri, 0)
            if relevance_score >= 60:
                relevant_images.append(image)

    return response_text, response_time, citations, relevant_images


def main():
    st.set_page_config(
        page_title="Tourism Guide Q&A",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize session state
    initialize_session_state()

    # Sidebar
    with st.sidebar:
        st.title("🗺️ Tourism Guide")
        st.markdown("---")

        # Area/Site Selection
        st.subheader("📍 Location")

        all_stores = st.session_state.registry.list_all()
        if not all_stores:
            st.warning(
                "No content uploaded yet. Use the 'Manage Content' tab to upload."
            )
            area = None
            site = None
        else:
            # Create dropdown options
            location_options = {
                f"{area} / {site}": (area, site) for (area, site) in all_stores.keys()
            }
            selected_location = st.selectbox(
                "Select Area / Site",
                options=list(location_options.keys()),
                index=0,
            )

            # Update selected area/site
            area, site = location_options[selected_location]
            if (
                area != st.session_state.selected_area
                or site != st.session_state.selected_site
            ):
                st.session_state.selected_area = area
                st.session_state.selected_site = site
                st.session_state.messages = []  # Clear chat history on location change

                # Load topics for selected location
                topics = load_topics(
                    area, site, st.session_state.storage_backend, st.session_state.config
                )
                st.session_state.topics = topics
                st.session_state.topics_location = f"{area}:{site}"

            # Display location info
            registry_data = st.session_state.registry.registry.get(f"{area}:{site}", {})
            metadata = registry_data.get("metadata", {})

            # Get topic count
            topic_count = len(st.session_state.topics) if st.session_state.topics else 0

            st.info(
                f"""
                **Area:** {area}
                **Site:** {site}
                **Files:** {metadata.get('file_count', 'N/A')}
                **Topics:** {topic_count}
                """
            )

            # Display available topics
            if st.session_state.topics:
                st.markdown("---")
                with st.expander("📚 Available Topics", expanded=False):
                    st.markdown("Click a topic to ask about it:")
                    for i, topic in enumerate(st.session_state.topics):
                        if st.button(topic, key=f"topic_btn_{i}"):
                            # Set the query in session state to be used by chat input
                            st.session_state.topic_query = f"ספר לי על {topic}"
                            st.rerun()

            # Note: Topic extraction from chunks removed with File Search migration
            # Topics are now pre-generated during upload and stored in GCS
            # To regenerate topics, use CLI: python gemini/generate_topics.py --area <area> --site <site>
            st.markdown("---")
            st.caption(
                "ℹ️ Topics are generated during upload. "
                "To regenerate, use: `python gemini/generate_topics.py --area <area> --site <site>`"
            )

        st.markdown("---")

        # Settings
        st.subheader("⚙️ Settings")
        config = st.session_state.config

        # Model selection
        model_options = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-2.5-flash",
        ]
        current_model = config.model_name.replace("models/", "")
        selected_model = st.selectbox(
            "Model",
            options=model_options,
            index=(
                model_options.index(current_model)
                if current_model in model_options
                else 0
            ),
        )
        config.model_name = selected_model

        # Temperature
        config.temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=config.temperature,
            step=0.1,
        )

        st.markdown("---")

        # Statistics
        if st.button("📊 Show Statistics"):
            stats = st.session_state.logger.get_stats()
            st.write("**Query Statistics**")
            st.metric("Total Queries", stats["total_queries"])
            st.metric("Avg Response Time", f"{stats['avg_response_time_seconds']:.2f}s")

        # Clear chat button
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

    # Main content area
    st.title("🗺️ Tourism Guide Q&A")

    if area and site:
        st.markdown(f"**Current Location:** {area} / {site}")

    # Create tabs
    tab_chat, tab_manage = st.tabs(["💬 Chat", "⚙️ Manage Content"])

    # ===== CHAT TAB =====
    with tab_chat:
        if not area or not site:
            st.info(
                "📤 No content available. Please upload content using the 'Manage Content' tab."
            )
        else:
            # Check if location has content in File Search Store via registry
            registry_entry = st.session_state.registry.get_store(area, site)
            # Handle both dict format (with metadata) and string format (old store_id)
            if isinstance(registry_entry, dict):
                has_content = registry_entry.get("metadata", {}).get("file_count", 0) > 0
            elif isinstance(registry_entry, str):
                # Old format - assume it has content if there's a store_id
                has_content = True
            else:
                has_content = False

            if not has_content:
                st.warning(
                    f"⚠️ No content found for {area} / {site}. Please upload documents first."
                )
            else:
                # Display chat messages
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
                        if "time" in message:
                            st.caption(f"⏱️ {message['time']:.2f}s")
                        # Display citations for assistant messages
                        if message["role"] == "assistant" and message.get("citations"):
                            citations = message["citations"]
                            with st.expander("📚 Sources", expanded=False):
                                for i, citation in enumerate(citations, 1):
                                    st.markdown(f"**{i}. {citation.get('title', 'Unknown')}**")
                                    if citation.get("text"):
                                        st.caption(citation["text"] + "...")
                                    if citation.get("metadata"):
                                        metadata = citation["metadata"]
                                        tags = []
                                        if hasattr(metadata, "area"):
                                            tags.append(f"Area: {metadata.area}")
                                        if hasattr(metadata, "site"):
                                            tags.append(f"Site: {metadata.site}")
                                        if hasattr(metadata, "doc"):
                                            tags.append(f"Doc: {metadata.doc}")
                                        if tags:
                                            st.caption(" | ".join(tags))
                                    st.markdown("---")
                        # Display images for assistant messages
                        if message["role"] == "assistant" and message.get("images"):
                            images = message["images"]
                            with st.expander(f"🖼️ Images ({len(images)})", expanded=False):
                                for image in images:
                                    # Display image from GCS using helper function with signed URLs
                                    image_url = _get_image_display_url(
                                        image.gcs_path,
                                        st.session_state.config.gcs_bucket_name,
                                        st.session_state.image_storage
                                    )
                                    st.image(
                                        image_url,
                                        caption=image.caption,
                                        use_container_width=True
                                    )
                                    if image.context_before or image.context_after:
                                        with st.expander("Context", expanded=False):
                                            if image.context_before:
                                                st.caption(f"Before: {image.context_before}")
                                            if image.context_after:
                                                st.caption(f"After: {image.context_after}")

                # Chat input
                # Check if user clicked a topic button
                question = None
                if "topic_query" in st.session_state:
                    question = st.session_state.topic_query
                    del st.session_state.topic_query  # Clear the query after using it
                else:
                    question = st.chat_input("Ask a question about this location...")

                if question:
                    # Display user message
                    st.session_state.messages.append({"role": "user", "content": question})
                    with st.chat_message("user"):
                        st.markdown(question)

                    # Get and display assistant response
                    with st.chat_message("assistant"):
                        with st.spinner("Searching content..."):
                            try:
                                # Pass conversation history (excluding the current question we just added)
                                answer, response_time, citations, images = get_response(
                                    question, area, site, st.session_state.messages[:-1]
                                )

                                st.markdown(answer)
                                st.caption(f"⏱️ {response_time:.2f}s")

                                # Display citations if available
                                if citations:
                                    with st.expander("📚 Sources", expanded=False):
                                        for i, citation in enumerate(citations, 1):
                                            st.markdown(f"**{i}. {citation.get('title', 'Unknown')}**")
                                            if citation.get("text"):
                                                st.caption(citation["text"] + "...")
                                            if citation.get("metadata"):
                                                metadata = citation["metadata"]
                                                tags = []
                                                if hasattr(metadata, "area"):
                                                    tags.append(f"Area: {metadata.area}")
                                                if hasattr(metadata, "site"):
                                                    tags.append(f"Site: {metadata.site}")
                                                if hasattr(metadata, "doc"):
                                                    tags.append(f"Doc: {metadata.doc}")
                                                if tags:
                                                    st.caption(" | ".join(tags))
                                            st.markdown("---")

                                # Display images if available
                                if images:
                                    with st.expander(f"🖼️ Images ({len(images)})", expanded=False):
                                        for image in images:
                                            # Display image from GCS using helper function with signed URLs
                                            image_url = _get_image_display_url(
                                                image.gcs_path,
                                                st.session_state.config.gcs_bucket_name,
                                                st.session_state.image_storage
                                            )
                                            st.image(
                                                image_url,
                                                caption=image.caption,
                                                use_container_width=True
                                            )
                                            if image.context_before or image.context_after:
                                                with st.expander("Context", expanded=False):
                                                    if image.context_before:
                                                        st.caption(f"Before: {image.context_before}")
                                                    if image.context_after:
                                                        st.caption(f"After: {image.context_after}")

                                # Save to messages
                                st.session_state.messages.append(
                                    {
                                        "role": "assistant",
                                        "content": answer,
                                        "time": response_time,
                                        "citations": citations,
                                        "images": images,
                                    }
                                )

                                # Log the query
                                st.session_state.logger.area = area
                                st.session_state.logger.site = site
                                st.session_state.logger.log_query(
                                    query=question,
                                    answer=answer,
                                    model=config.model_name,
                                    context_chars=0,  # No context with File Search
                                    response_time_seconds=response_time,
                                    chunks_used=[],  # Citations tracked separately
                                )

                            except Exception as e:
                                st.error(f"Error: {e}")
                                import traceback

                                traceback.print_exc()

    # ===== MANAGE CONTENT TAB =====
    with tab_manage:
        st.subheader("📂 Uploaded Content")

        # View uploaded content
        summary = st.session_state.upload_manager.get_uploaded_content_summary()

        if not summary:
            st.info("No content uploaded yet.")
        else:
            # Display content with delete buttons
            import pandas as pd

            for idx, item in enumerate(summary):
                col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 1, 1, 1, 1])

                with col1:
                    st.write(f"**{item['area']}**")

                with col2:
                    st.write(item["site"])

                with col3:
                    # Show file count from metadata
                    file_count = item.get("file_count", 0)
                    st.metric("Files", file_count)

                with col4:
                    # Show topic count
                    topic_count = item.get("topic_count", 0)
                    st.metric("Topics", topic_count)

                with col5:
                    # Show image count
                    image_count = item.get("image_count", 0)
                    st.metric("Images", image_count)

                with col6:
                    if st.button(
                        "🗑️",
                        key=f"delete_{idx}",
                        help=f"Delete {item['area']}/{item['site']}",
                    ):
                        with st.spinner(f"Removing {item['area']}/{item['site']}..."):
                            success, message = (
                                st.session_state.upload_manager.remove_location(
                                    item["area"], item["site"]
                                )
                            )
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)

                st.divider()

        st.markdown("---")

        # Upload new content section
        st.subheader("📤 Upload Content")

        # Info about upload tracking and registry rebuild
        st.info(
            "ℹ️ **Note**: Upload tracking is session-based and resets on app restart. "
            "The registry auto-rebuilds from Gemini API on startup. "
            "Use 'Force Re-upload' if files were modified after a restart."
        )

        # Two upload options
        upload_tabs = st.tabs(["📁 From Folder Path", "📂 From Existing Content"])

        # Tab 1: Upload from folder path
        with upload_tabs[0]:
            st.write("Upload files from a specific folder on your system")

            col1, col2 = st.columns(2)

            with col1:
                folder_path = st.text_input(
                    "Folder Path",
                    placeholder="e.g., /path/to/your/content",
                    key="folder_path_input",
                    help="Enter the absolute path to the folder containing your content files",
                )

            with col2:
                st.write("")  # Spacing for alignment
                st.write("")
                browse_help = st.button(
                    "💡 How to find path?",
                    help="On Mac: right-click folder → hold Option → Copy as Pathname\nOn Linux: right-click → Properties → Location\nOn Windows: Shift+right-click → Copy as path",
                )

            if browse_help:
                st.info(
                    """
                    **Finding your folder path:**

                    - **Mac**: Right-click folder → Hold Option key → Select "Copy ... as Pathname"
                    - **Linux**: Right-click folder → Properties → Copy the Location
                    - **Windows**: Shift + Right-click folder → Select "Copy as path"
                    """
                )

            col3, col4 = st.columns(2)

            with col3:
                location_type = st.radio(
                    "Location Type",
                    ["Use Existing Location", "Create New Location"],
                    key="location_type",
                )

            with col4:
                if location_type == "Use Existing Location":
                    # Get existing locations
                    all_stores = st.session_state.registry.list_all()
                    if all_stores:
                        location_strs = [f"{a} / {s}" for (a, s) in all_stores.keys()]
                        selected_existing = st.selectbox(
                            "Select Location",
                            options=location_strs,
                            key="existing_location_select",
                        )
                        upload_area, upload_site = selected_existing.split(" / ")
                    else:
                        st.warning("No existing locations. Please create a new one.")
                        upload_area = None
                        upload_site = None
                else:
                    # Create new location
                    upload_area = st.text_input(
                        "Area Name",
                        placeholder="e.g., tel_aviv_district",
                        key="new_area_input",
                        help="Use lowercase with underscores (e.g., tel_aviv_district)",
                    )
                    upload_site = st.text_input(
                        "Site Name",
                        placeholder="e.g., jaffa_port",
                        key="new_site_input",
                        help="Use lowercase with underscores (e.g., jaffa_port)",
                    )

            force_upload_path = st.checkbox(
                "Force Re-upload (overwrite existing)",
                key="force_upload_path",
                help="Check this to re-upload files even if they haven't changed",
            )

            if st.button(
                "📤 Upload from Folder", type="primary", key="upload_folder_btn"
            ):
                # Validate inputs
                if not folder_path:
                    st.error("Please enter a folder path")
                elif not upload_area or not upload_site:
                    st.error("Please specify both area and site names")
                elif not os.path.exists(folder_path):
                    st.error(f"Folder not found: {folder_path}")
                elif not os.path.isdir(folder_path):
                    st.error(f"Path is not a directory: {folder_path}")
                else:
                    with st.spinner(f"Uploading content from {folder_path}..."):
                        # Temporarily set content_root to the specified folder
                        original_root = st.session_state.config.content_root
                        st.session_state.config.content_root = folder_path

                        try:
                            success, message, stats = (
                                st.session_state.upload_manager.upload_content(
                                    area=upload_area,
                                    site=upload_site,
                                    force=force_upload_path,
                                    flat_folder=True,
                                )
                            )

                            if success:
                                st.success(message)
                                if stats:
                                    st.json(stats)
                                st.rerun()
                            else:
                                st.error(message)
                        finally:
                            # Restore original content_root
                            st.session_state.config.content_root = original_root

        # Tab 2: Upload from existing content directory
        with upload_tabs[1]:
            st.write(
                f"Upload files from the configured content directory: `{st.session_state.config.content_root}`"
            )

            # Get available locations from content directory
            available_locations = (
                st.session_state.upload_manager.get_available_locations()
            )

            if not available_locations:
                st.warning(
                    f"No content found in {st.session_state.config.content_root}. Use the 'From Folder Path' tab to upload from a different location."
                )
            else:
                upload_col1, upload_col2, upload_col3, upload_col4 = st.columns(
                    [2, 2, 1, 1]
                )

                with upload_col1:
                    upload_option = st.radio(
                        "Upload Scope",
                        ["All Locations", "Specific Location"],
                        key="upload_scope",
                    )

                with upload_col2:
                    if upload_option == "Specific Location":
                        location_strs = [f"{a} / {s}" for a, s in available_locations]
                        selected_loc = st.selectbox(
                            "Select Location",
                            options=location_strs,
                            key="upload_location",
                        )
                        upload_area_existing, upload_site_existing = selected_loc.split(
                            " / "
                        )
                    else:
                        upload_area_existing, upload_site_existing = None, None

                with upload_col3:
                    force_upload_existing = st.checkbox(
                        "Force Re-upload", key="force_upload"
                    )

                with upload_col4:
                    st.write("")  # Spacing
                    st.write("")  # Spacing
                    if st.button(
                        "📤 Upload", type="primary", key="upload_existing_btn"
                    ):
                        with st.spinner("Uploading content..."):
                            success, message, stats = (
                                st.session_state.upload_manager.upload_content(
                                    area=upload_area_existing,
                                    site=upload_site_existing,
                                    force=force_upload_existing,
                                )
                            )

                            if success:
                                st.success(message)
                                if stats:
                                    st.json(stats)
                                st.rerun()
                            else:
                                st.error(message)


if __name__ == "__main__":
    main()
