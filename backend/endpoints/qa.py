"""
QA endpoint - Chat queries with File Search and multimodal images.

Main endpoint for conversational queries using:
- Gemini API with File Search tool
- Metadata filtering by area/site
- Structured output for image relevance
- Citation extraction from grounding metadata
- Conversation history management
"""

import json
import logging
import time
from typing import List, Optional

import google.genai as genai
from fastapi import APIRouter, Depends, HTTPException

from backend.auth import ApiKeyDep
from backend.config import GeminiConfig
from backend.conversation_storage.conversations import ConversationStore
from backend.dependencies import (
    get_conversation_store,
    get_image_registry,
    get_query_logger,
    get_store_registry,
)
from backend.image_registry import ImageRegistry
from backend.query_logging.query_logger import QueryLogger
from backend.models import Citation, ImageMetadata, QARequest, QAResponse
from backend.prompt_loader import PromptLoader
from backend.store_registry import StoreRegistry
from backend.utils import get_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["qa"])


def get_citations_from_grounding(grounding_metadata) -> List[Citation]:
    """
    Extract citations from Gemini API grounding metadata.

    Args:
        grounding_metadata: Grounding metadata from API response

    Returns:
        List of Citation objects
    """
    citations = []

    if not grounding_metadata:
        return citations

    try:
        # Parse grounding chunks
        if hasattr(grounding_metadata, "grounding_chunks"):
            for chunk in grounding_metadata.grounding_chunks:
                # Extract source from web or file
                source = "unknown"
                if hasattr(chunk, "web") and chunk.web:
                    source = chunk.web.uri
                elif hasattr(chunk, "file") and chunk.file:
                    source = chunk.file.name

                # Extract text snippet if available
                text = None
                if hasattr(chunk, "text"):
                    text = chunk.text

                citations.append(
                    Citation(
                        source=source,
                        chunk_id=getattr(chunk, "chunk_id", None),
                        text=text,
                    )
                )

    except Exception as e:
        logger.warning(f"Error parsing grounding metadata: {e}")

    return citations


def query_images_for_location(
    image_registry: ImageRegistry, area: str, site: str
) -> List[dict]:
    """
    Get all images for a location from image registry.

    Args:
        image_registry: Image registry
        area: Location area
        site: Location site

    Returns:
        List of image records (dicts with uri, caption, context, etc.)
    """
    try:
        images = image_registry.get_images_for_location(area, site)
        logger.info(f"Found {len(images)} images for {area}/{site}")
        return images
    except Exception as e:
        logger.error(f"Error querying images: {e}")
        return []


def filter_images_by_relevance(
    images: List[dict], image_relevance: List, min_score: int = 60
) -> List[ImageMetadata]:
    """
    Filter images by relevance scores from LLM.

    Args:
        images: List of image records from registry
        image_relevance: List of ImageRelevanceScore objects from LLM
        min_score: Minimum relevance score (default: 60)

    Returns:
        List of ImageMetadata objects for relevant images
    """
    relevant_images = []

    # Convert list of scores to dict for lookup
    relevance_dict = {item.uri: item.score for item in image_relevance}

    for img in images:
        file_api_uri = img.file_api_uri
        if not file_api_uri:
            continue

        # Get relevance score from LLM output
        score = relevance_dict.get(file_api_uri, 0)

        if score >= min_score:
            # Build context from before/after text
            context = ""
            if img.context_before:
                context += img.context_before
            if img.context_after:
                if context:
                    context += " "
                context += img.context_after

            relevant_images.append(
                ImageMetadata(
                    uri=img.gcs_uri,
                    file_api_uri=file_api_uri,
                    caption=img.caption or "",
                    context=context,
                    relevance_score=score,
                )
            )

    # Sort by relevance score (descending)
    relevant_images.sort(key=lambda x: x.relevance_score, reverse=True)

    logger.info(
        f"Filtered to {len(relevant_images)} relevant images (>= {min_score})"
    )
    return relevant_images


@router.post("")
async def chat_query(
    request: QARequest,
    api_key: ApiKeyDep,
    store_registry: StoreRegistry = Depends(get_store_registry),
    image_registry: ImageRegistry = Depends(get_image_registry),
    conversation_store: ConversationStore = Depends(get_conversation_store),
    query_logger: QueryLogger = Depends(get_query_logger),
) -> QAResponse:
    """
    Process a chat query with File Search and multimodal images.

    Args:
        request: QA request (conversation_id, area, site, query)
        api_key: API key (from auth dependency)
        store_registry: Store registry (injected)
        image_registry: Image registry (injected)
        conversation_store: Conversation store (injected)
        query_logger: Query logger (injected)

    Returns:
        QAResponse with response text, citations, relevant images
    """
    start_time = time.time()
    logger.info(f"QA request: {request.area}/{request.site} - {request.query[:50]}...")

    try:
        # Load config and prompts with location overrides
        config = GeminiConfig.from_yaml(area=request.area, site=request.site)
        prompt_config = PromptLoader.load(
            "config/prompts/tourism_qa.yaml", area=request.area, site=request.site
        )

        # Get or create conversation
        if request.conversation_id:
            conversation = conversation_store.get_conversation(request.conversation_id)
            if not conversation:
                logger.warning(
                    f"Conversation not found: {request.conversation_id}, creating new"
                )
                conversation = conversation_store.create_conversation(
                    request.area, request.site, request.conversation_id
                )
        else:
            conversation = conversation_store.create_conversation(
                request.area, request.site
            )

        # Add user message to conversation
        conversation = conversation_store.add_message(
            conversation, "user", request.query
        )

        # Get File Search Store name
        store_name = store_registry.get_store(request.area, request.site)
        if not store_name:
            raise HTTPException(
                status_code=404,
                detail=f"Location not found: {request.area}/{request.site}",
            )

        # Query images for location
        location_images = query_images_for_location(
            image_registry, request.area, request.site
        )

        # Build Gemini API request
        # Create client
        client = genai.Client(api_key=get_secret("GOOGLE_API_KEY"))

        # Build conversation history for context
        history_messages = []
        for msg in conversation.messages[:-1]:  # Exclude current query
            # Convert "assistant" role to "model" for Gemini API
            role = "model" if msg.role == "assistant" else msg.role
            history_messages.append({"role": role, "parts": [{"text": msg.content}]})

        # Format system prompt
        system_instruction = prompt_config.system_prompt

        # Build user message with images
        user_parts = [{"text": request.query}]

        # Add image URIs to user message (up to 5 images for context)
        if location_images:
            for img in location_images[:5]:
                file_api_uri = img.file_api_uri
                if file_api_uri:
                    user_parts.append({"file_data": {"file_uri": file_api_uri}})

        # Create File Search tool with metadata filter
        from google.genai import types

        tools = [
            types.Tool(
                file_search=types.FileSearch(
                    file_search_store_names=[store_name],
                    metadata_filter=f'area="{request.area}" AND site="{request.site}"',
                )
            )
        ]

        # Call Gemini API
        try:
            response = client.models.generate_content(
                model=prompt_config.model_name,
                contents=[*history_messages, {"role": "user", "parts": user_parts}],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                    temperature=prompt_config.temperature,
                ),
            )

            # Get response text
            response_text = response.text

            # Try to parse as JSON if the model returned structured output
            # (happens when system prompt requests JSON format)
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict) and "response_text" in parsed:
                    response_text = parsed["response_text"]
                    logger.info("Parsed structured JSON response from Gemini")
            except (json.JSONDecodeError, KeyError):
                # Not JSON or doesn't have expected structure, use as-is
                pass

            # Extract citations from grounding metadata
            citations = get_citations_from_grounding(
                getattr(response, "grounding_metadata", None)
            )

            # For MVP: show all images if there are any
            # TODO: Implement LLM-based image relevance filtering
            relevant_images = []
            should_include_images = len(location_images) > 0
            if should_include_images:
                # Convert all images to ImageMetadata format
                for img in location_images[:5]:  # Limit to 5 images
                    context = ""
                    if img.context_before:
                        context += img.context_before
                    if img.context_after:
                        if context:
                            context += " "
                        context += img.context_after

                    relevant_images.append(
                        ImageMetadata(
                            uri=img.gcs_path,
                            file_api_uri=img.file_api_uri,
                            caption=img.caption or "",
                            context=context,
                            relevance_score=100,  # Default score
                        )
                    )

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            # Fallback: error response
            response_text = f"Error processing query: {str(e)}"
            citations = []
            relevant_images = []
            should_include_images = False

        # Add assistant message to conversation
        conversation = conversation_store.add_message(
            conversation,
            "assistant",
            response_text,
            citations=[c.model_dump() for c in citations],
            images=[img.model_dump() for img in relevant_images],
        )

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Log query
        query_logger.log_query(
            conversation_id=conversation.conversation_id,
            area=request.area,
            site=request.site,
            query=request.query,
            response_text=response_text,
            latency_ms=latency_ms,
            citations_count=len(citations),
            images_count=len(relevant_images),
            model_name=prompt_config.model_name,
            temperature=prompt_config.temperature,
        )

        logger.info(
            f"QA response: {conversation.conversation_id} - "
            f"{len(citations)} citations, {len(relevant_images)} images, {latency_ms:.0f}ms"
        )

        return QAResponse(
            conversation_id=conversation.conversation_id,
            response_text=response_text,
            citations=citations,
            images=relevant_images,
            should_include_images=should_include_images,
            model_name=prompt_config.model_name,
            temperature=prompt_config.temperature,
            latency_ms=latency_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing QA request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to process query: {str(e)}"
        )
