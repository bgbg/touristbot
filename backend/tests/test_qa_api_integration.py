"""
Integration test for QA endpoint with actual backend API.
"""
import os
import pytest
import requests


@pytest.fixture
def backend_url():
    """Get backend URL from environment or use deployed URL."""
    return os.getenv(
        "BACKEND_URL", "https://tourism-rag-backend-347968285860.me-west1.run.app"
    )


@pytest.fixture
def api_key():
    """Get API key from environment."""
    key = os.getenv("BACKEND_API_KEY", "00dcc37da36b4467fb7f9b78ab6f775c1c762af6d376e330d68f0affcf9fbb2f")
    if not key:
        pytest.skip("BACKEND_API_KEY not set")
    return key


@pytest.fixture
def auth_headers(api_key):
    """Get authentication headers."""
    return {"Authorization": f"Bearer {api_key}"}


def test_qa_endpoint_simple_query(backend_url, auth_headers):
    """
    Test QA endpoint with a simple query.

    This test verifies:
    1. API authentication works
    2. Request schema is valid
    3. Response schema is compatible with Gemini API
    4. No schema validation errors occur
    """
    # Simple query
    request_data = {
        "area": "hefer_valley",
        "site": "agamon_hefer",
        "query": "hi"
    }

    # Call API
    response = requests.post(
        f"{backend_url}/qa",
        headers={**auth_headers, "Content-Type": "application/json"},
        json=request_data,
        timeout=60
    )

    # Check response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()

    # Verify response structure
    assert "conversation_id" in data
    assert "response_text" in data
    assert "citations" in data
    assert "images" in data
    assert "should_include_images" in data
    assert "model_name" in data
    assert "temperature" in data
    assert "latency_ms" in data

    # Verify types
    assert isinstance(data["response_text"], str)
    assert isinstance(data["should_include_images"], bool)
    assert isinstance(data["citations"], list)
    assert isinstance(data["images"], list)

    print(f"✓ Query successful: {data['response_text'][:100]}")
    print(f"✓ Model: {data['model_name']}, Latency: {data['latency_ms']:.0f}ms")


def test_qa_endpoint_with_conversation(backend_url, auth_headers):
    """
    Test QA endpoint with conversation continuity.

    This test verifies:
    1. Conversation ID persists across queries
    2. Second query succeeds with conversation history
    3. No "INVALID_ARGUMENT: Please use a valid role" error occurs
    """
    # First query
    request1 = {
        "area": "hefer_valley",
        "site": "agamon_hefer",
        "query": "What birds can I see here?"
    }

    response1 = requests.post(
        f"{backend_url}/qa",
        headers={**auth_headers, "Content-Type": "application/json"},
        json=request1,
        timeout=60
    )

    assert response1.status_code == 200
    data1 = response1.json()
    conversation_id = data1["conversation_id"]

    # Follow-up query
    request2 = {
        "area": "hefer_valley",
        "site": "agamon_hefer",
        "query": "Tell me more about them",
        "conversation_id": conversation_id
    }

    response2 = requests.post(
        f"{backend_url}/qa",
        headers={**auth_headers, "Content-Type": "application/json"},
        json=request2,
        timeout=60
    )

    # Verify no role validation error
    assert response2.status_code == 200, f"Expected 200, got {response2.status_code}: {response2.text}"

    # Verify error message doesn't contain role validation error
    assert "valid role" not in response2.text.lower(), \
        f"Got role validation error: {response2.text}"

    data2 = response2.json()

    # Should use same conversation
    assert data2["conversation_id"] == conversation_id

    print(f"✓ Conversation continuity working")
    print(f"✓ Q1: {request1['query']}")
    print(f"✓ A1: {data1['response_text'][:100]}...")
    print(f"✓ Q2: {request2['query']}")
    print(f"✓ A2: {data2['response_text'][:100]}...")
