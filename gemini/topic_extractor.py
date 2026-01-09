"""
Topic extraction module for generating key topics from location content chunks.

Uses Gemini LLM to analyze content and extract 5-10 relevant topics that represent
the main themes and subjects available for each location/site.
"""

import json
from typing import List

import google.genai as genai
from google.genai import types

from gemini.prompt_loader import PromptLoader


def extract_topics_from_chunks(
    chunks: str, area: str, site: str, model: str, client: genai.Client
) -> List[str]:
    """
    Extract key topics from location content chunks using Gemini LLM.

    Args:
        chunks: Combined content chunks for the location
        area: Geographic area name (e.g., "Old City")
        site: Specific site name (e.g., "Western Wall")
        model: Gemini model name to use (e.g., "gemini-2.0-flash")
        client: Initialized Gemini client

    Returns:
        List of 5-10 topic strings extracted from the content

    Raises:
        ValueError: If topic extraction fails or returns invalid format
        Exception: If Gemini API call fails
    """
    # Load topic extraction prompt configuration
    prompt_path = "prompts/topic_extraction.yaml"
    prompt_config = PromptLoader.load(prompt_path)

    # Format prompts with variables
    system_instruction, user_message = prompt_config.format(
        area=area, site=site, chunks=chunks
    )

    # Ensure model name has correct prefix
    model_name = model if model.startswith("models/") else f"models/{model}"

    try:
        # Call Gemini API to extract topics
        response = client.models.generate_content(
            model=model_name,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=prompt_config.temperature,
            ),
        )

        # Parse response as JSON array
        response_text = response.text.strip()

        # Handle markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove trailing ```
        response_text = response_text.strip()

        # Parse JSON
        topics = json.loads(response_text)

        # Validate response format
        if not isinstance(topics, list):
            raise ValueError(f"Expected JSON array, got {type(topics).__name__}")

        if not all(isinstance(topic, str) for topic in topics):
            raise ValueError("All topics must be strings")

        if len(topics) < 3:
            raise ValueError(f"Expected at least 3 topics, got {len(topics)}")

        if len(topics) > 15:
            # Truncate to 10 if too many topics returned
            topics = topics[:10]

        return topics

    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse topic extraction response as JSON: {e}") from e
    except Exception as e:
        raise Exception(f"Topic extraction failed for {area}/{site}: {e}") from e
