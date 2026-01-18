"""
Pydantic models for API request/response schemas.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic.json_schema import GenerateJsonSchema


class GeminiJsonSchema(GenerateJsonSchema):
    """
    Custom JSON schema generator for Gemini API compatibility.

    Removes 'additionalProperties' from schema as it's not supported by
    the google-genai SDK client-side validation (Issue #1815).
    """

    def generate(self, schema: Any, mode: str = "validation") -> Dict[str, Any]:
        json_schema = super().generate(schema, mode=mode)
        return self._remove_additional_properties(json_schema)

    def _remove_additional_properties(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively remove additionalProperties from schema."""
        if isinstance(schema, dict):
            # Remove from current level
            schema.pop("additionalProperties", None)

            # Remove from nested properties
            if "properties" in schema:
                for prop_schema in schema["properties"].values():
                    if isinstance(prop_schema, dict):
                        self._remove_additional_properties(prop_schema)

            # Remove from definitions/defs
            for key in ["$defs", "definitions"]:
                if key in schema:
                    for def_schema in schema[key].values():
                        if isinstance(def_schema, dict):
                            self._remove_additional_properties(def_schema)

        return schema


class ImageRelevanceScore(BaseModel):
    """Single image relevance score entry."""

    uri: str = Field(description="Image File API URI")
    score: int = Field(ge=0, le=100, description="Relevance score (0-100)")


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
    image_relevance: List["ImageRelevanceScore"] = Field(
        default_factory=list,
        description="List of image URIs with relevance scores (0-100). Only images with score >= 60 should be displayed.",
    )

    @classmethod
    def get_gemini_schema(cls) -> Dict[str, Any]:
        """
        Get JSON schema compatible with Gemini API.

        Returns schema without 'additionalProperties' which causes
        client-side validation errors in google-genai SDK.
        """
        return cls.model_json_schema(schema_generator=GeminiJsonSchema)


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
