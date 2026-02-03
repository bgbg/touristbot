"""
Real API call tests to reproduce the 400 INVALID_ARGUMENT error

These tests make actual API calls (not mocked) to reproduce the exact error
"""

import pytest
from google import genai
from google.genai import types
import os
import tomllib
from pathlib import Path


def get_api_key():
    """Get API key from environment or secrets.toml file"""
    # First try environment variable
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        return api_key

    # Try loading from .streamlit/secrets.toml
    secrets_path = Path(__file__).parent.parent.parent / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
            return secrets.get("GOOGLE_API_KEY")

    return None


@pytest.mark.integration
def test_file_search_tool_with_real_client_single_message():
    """
    Test that reproduces the 400 INVALID_ARGUMENT error with a real API client
    This test calls the actual Gemini API
    """
    # Get API key from environment or secrets.toml
    api_key = get_api_key()
    if api_key is None:
        pytest.skip("GOOGLE_API_KEY not available (requires environment variable or .streamlit/secrets.toml)")

    # Create real client
    client = genai.Client(api_key=api_key)

    # Create the exact same configuration as main_qa.py
    file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
    metadata_filter = "area=tel_aviv_district AND site=jaffa_port"
    model_name = "models/gemini-2.5-flash"

    # Create conversation history (single message)
    conversation_history = [
        types.Content(role="user", parts=[types.Part.from_text(text="hi")])
    ]

    # Create system instruction
    system_instruction = "You are a tour guide at tel_aviv_district / jaffa_port."

    # This should work without error once the bug is fixed
    response = client.models.generate_content(
        model=model_name,
        contents=conversation_history,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.6,
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[file_search_store_name],
                        metadata_filter=metadata_filter,
                    )
                ),
            ],
        ),
    )

    # Verify we got a valid response
    assert response is not None
    assert hasattr(response, "text") or hasattr(response, "candidates")
    print(f"\n=== SUCCESS: Got response from API ===")
    if hasattr(response, "text"):
        print(f"Response text preview: {response.text[:100]}...")


@pytest.mark.integration
def test_file_search_tool_with_real_client_multiple_messages():
    """
    Test with chat history to reproduce the 400 error
    """
    api_key = get_api_key()
    if api_key is None:
        pytest.skip("GOOGLE_API_KEY not available (requires environment variable or .streamlit/secrets.toml)")

    client = genai.Client(api_key=api_key)

    file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
    metadata_filter = "area=tel_aviv_district AND site=jaffa_port"
    model_name = "models/gemini-2.5-flash"

    # Create conversation with history
    conversation_history = [
        types.Content(role="user", parts=[types.Part.from_text(text="hi")]),
        types.Content(
            role="model", parts=[types.Part.from_text(text="Hello! Welcome.")]
        ),
        types.Content(role="user", parts=[types.Part.from_text(text="tell me more")]),
    ]

    system_instruction = "You are a tour guide at tel_aviv_district / jaffa_port."

    # This should work without error once the bug is fixed
    response = client.models.generate_content(
        model=model_name,
        contents=conversation_history,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.6,
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[file_search_store_name],
                        metadata_filter=metadata_filter,
                    )
                ),
            ],
        ),
    )

    # Verify we got a valid response
    assert response is not None
    assert hasattr(response, "text") or hasattr(response, "candidates")
    print(f"\n=== SUCCESS: Got response with chat history ===")
    if hasattr(response, "text"):
        print(f"Response text preview: {response.text[:100]}...")
