"""
Pydantic models for API request/response schemas.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ImageAwareResponse(BaseModel):
    """
    Structured response from Gemini API with image relevance signals.

    Used with structured output to get both the text response and image metadata.
    """

    response_text: str = Field(
        description="Main response to user query in Hebrew or query language"
    )
    should_include_images: bool = Field(
        description="Whether images should be shown (false for initial greetings, true for substantive queries)"
    )
    image_relevance: Dict[str, int] = Field(
        default_factory=dict,
        description="Map of image URIs to relevance scores (0-100). Only images with score >= 60 should be displayed.",
    )


class QARequest(BaseModel):
    """Request schema for /qa endpoint."""

    conversation_id: Optional[str] = Field(
        None, description="Conversation ID (generates new if not provided)"
    )
    area: str = Field(..., description="Location area (e.g., 'hefer_valley')")
    site: str = Field(..., description="Location site (e.g., 'agamon_hefer')")
    query: str = Field(..., description="User query text")


class Citation(BaseModel):
    """Citation from grounding metadata."""

    source: str = Field(..., description="Source file name")
    chunk_id: Optional[str] = Field(None, description="Chunk ID")
    text: Optional[str] = Field(None, description="Cited text snippet")


class ImageMetadata(BaseModel):
    """Image metadata with relevance."""

    uri: str = Field(..., description="GCS URI of the image")
    file_api_uri: str = Field(..., description="Gemini File API URI")
    caption: str = Field(..., description="Image caption")
    context: Optional[str] = Field(None, description="Context text around image")
    relevance_score: int = Field(
        ..., ge=0, le=100, description="Relevance score (0-100)"
    )


class QAResponse(BaseModel):
    """Response schema for /qa endpoint."""

    conversation_id: str = Field(..., description="Conversation ID")
    response_text: str = Field(..., description="Assistant response text")
    citations: List[Citation] = Field(
        default_factory=list, description="List of citations"
    )
    images: List[ImageMetadata] = Field(
        default_factory=list, description="List of relevant images"
    )
    should_include_images: bool = Field(
        ..., description="Whether images should be displayed"
    )
    model_name: str = Field(..., description="Model used for response")
    temperature: float = Field(..., description="Temperature used")
    latency_ms: float = Field(..., description="Query latency in milliseconds")
