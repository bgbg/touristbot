"""
Integration tests for QA endpoint with signed URLs

NOTE: These tests require GCS credentials and make real API calls.
Skip by not setting GCS_CREDENTIALS_JSON environment variable.
"""
import os
import pytest


# Skip all tests in this module if GCS credentials not available
pytestmark = pytest.mark.skipif(
    "GCS_CREDENTIALS_JSON" not in os.environ,
    reason="GCS_CREDENTIALS_JSON not set - skipping integration tests"
)


@pytest.fixture(scope="module")
def setup_env():
    """Setup environment variables before importing app"""
    # Set required environment variables
    os.environ["GCS_BUCKET"] = "tarasa_tourist_bot_content"
    os.environ["BACKEND_API_KEYS"] = "test-key-123"

    # GOOGLE_API_KEY should already be set externally
    if "GOOGLE_API_KEY" not in os.environ:
        pytest.skip("GOOGLE_API_KEY not set")

    yield

    # Cleanup
    os.environ.pop("GCS_BUCKET", None)
    os.environ.pop("BACKEND_API_KEYS", None)


@pytest.fixture(scope="module")
def client(setup_env):
    """Create test client with environment already configured"""
    from fastapi.testclient import TestClient
    from backend.main import app

    return TestClient(app)


def test_qa_endpoint_with_images(client):
    """Test QA endpoint returns proper response with signed URLs"""
    response = client.post(
        "/qa",
        headers={"Authorization": "Bearer test-key-123"},
        json={
            "area": "hefer_valley",
            "site": "agamon_hefer",
            "query": "hi"
        }
    )

    # Should return 200 OK
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()

    # Check required fields
    assert "response_text" in data
    assert "conversation_id" in data
    assert "citations" in data
    assert "images" in data

    # Check images have signed URLs if present
    if data["images"]:
        for img in data["images"]:
            assert "uri" in img
            # Signed URLs should contain X-Goog-Signature parameter
            assert "X-Goog-Signature" in img["uri"] or "storage.googleapis.com" in img["uri"]
            assert "caption" in img
            assert "context" in img


def test_qa_endpoint_conversation_history(client):
    """Test conversation history is maintained"""
    # First query
    response1 = client.post(
        "/qa",
        headers={"Authorization": "Bearer test-key-123"},
        json={
            "area": "hefer_valley",
            "site": "agamon_hefer",
            "query": "hello"
        }
    )

    assert response1.status_code == 200
    data1 = response1.json()
    conversation_id = data1["conversation_id"]

    # Second query with conversation ID
    response2 = client.post(
        "/qa",
        headers={"Authorization": "Bearer test-key-123"},
        json={
            "area": "hefer_valley",
            "site": "agamon_hefer",
            "query": "what else?",
            "conversation_id": conversation_id
        }
    )

    assert response2.status_code == 200
    data2 = response2.json()

    # Should maintain same conversation ID
    assert data2["conversation_id"] == conversation_id
