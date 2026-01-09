"""
Unit tests for topic_extractor module
"""

import json
import pytest
from unittest.mock import Mock, patch

from gemini.topic_extractor import extract_topics_from_chunks


@pytest.fixture
def mock_client():
    """Create a mock Gemini client"""
    client = Mock()
    return client


@pytest.fixture
def mock_prompt_loader():
    """Create a mock PromptLoader"""
    mock_config = Mock()
    mock_config.model_name = "gemini-2.0-flash"
    mock_config.temperature = 0.3
    mock_config.format = Mock(return_value=(
        "System instruction",
        "User message"
    ))
    return mock_config


@pytest.fixture
def sample_chunks():
    """Sample chunk content for testing"""
    return """
    === chunk_1.txt ===
    הכותל המערבי הוא אחד האתרים המקודשים ביהדות.
    הוא נמצא בירושלים העתיקה.

    === chunk_2.txt ===
    ההיסטוריה של הכותל מתחילה בתקופת בית שני.
    המקום משמש לתפילה ולביקור תיירים רבים.
    """


def test_extract_topics_success(mock_client, sample_chunks):
    """Test successful topic extraction"""
    # Mock the API response
    mock_response = Mock()
    mock_response.text = '["ההיסטוריה של הכותל", "תפילה וקדושה", "תיירות בירושלים"]'
    mock_client.models.generate_content = Mock(return_value=mock_response)

    # Mock PromptLoader
    with patch('gemini.topic_extractor.PromptLoader') as MockPromptLoader:
        mock_config = Mock()
        mock_config.model_name = "gemini-2.0-flash"
        mock_config.temperature = 0.3
        mock_config.format = Mock(return_value=(
            "System instruction",
            "User message"
        ))
        MockPromptLoader.load = Mock(return_value=mock_config)

        # Call the function
        topics = extract_topics_from_chunks(
            chunks=sample_chunks,
            area="Jerusalem",
            site="Western Wall",
            model="gemini-2.0-flash",
            client=mock_client
        )

        # Verify results
        assert len(topics) == 3
        assert "ההיסטוריה של הכותל" in topics
        assert "תפילה וקדושה" in topics
        assert "תיירות בירושלים" in topics


def test_extract_topics_with_markdown_code_block(mock_client, sample_chunks):
    """Test topic extraction when response includes markdown code blocks"""
    # Mock API response with markdown code block
    mock_response = Mock()
    mock_response.text = '```json\n["נושא 1", "נושא 2", "נושא 3"]\n```'
    mock_client.models.generate_content = Mock(return_value=mock_response)

    with patch('gemini.topic_extractor.PromptLoader') as MockPromptLoader:
        mock_config = Mock()
        mock_config.model_name = "gemini-2.0-flash"
        mock_config.temperature = 0.3
        mock_config.format = Mock(return_value=("System", "User"))
        MockPromptLoader.load = Mock(return_value=mock_config)

        topics = extract_topics_from_chunks(
            chunks=sample_chunks,
            area="Test Area",
            site="Test Site",
            model="gemini-2.0-flash",
            client=mock_client
        )

        assert len(topics) == 3
        assert "נושא 1" in topics


def test_extract_topics_truncates_too_many(mock_client, sample_chunks):
    """Test that topics are truncated to 10 if more than 15 returned"""
    # Mock API response with 20 topics
    many_topics = [f"נושא {i}" for i in range(1, 21)]
    mock_response = Mock()
    mock_response.text = json.dumps(many_topics)
    mock_client.models.generate_content = Mock(return_value=mock_response)

    with patch('gemini.topic_extractor.PromptLoader') as MockPromptLoader:
        mock_config = Mock()
        mock_config.model_name = "gemini-2.0-flash"
        mock_config.temperature = 0.3
        mock_config.format = Mock(return_value=("System", "User"))
        MockPromptLoader.load = Mock(return_value=mock_config)

        topics = extract_topics_from_chunks(
            chunks=sample_chunks,
            area="Test",
            site="Test",
            model="gemini-2.0-flash",
            client=mock_client
        )

        # Should be truncated to 10
        assert len(topics) == 10


def test_extract_topics_too_few_raises_error(mock_client, sample_chunks):
    """Test that fewer than 3 topics raises Exception"""
    # Mock API response with only 2 topics
    mock_response = Mock()
    mock_response.text = '["נושא 1", "נושא 2"]'
    mock_client.models.generate_content = Mock(return_value=mock_response)

    with patch('gemini.topic_extractor.PromptLoader') as MockPromptLoader:
        mock_config = Mock()
        mock_config.model_name = "gemini-2.0-flash"
        mock_config.temperature = 0.3
        mock_config.format = Mock(return_value=("System", "User"))
        MockPromptLoader.load = Mock(return_value=mock_config)

        with pytest.raises(Exception, match="Expected at least 3 topics"):
            extract_topics_from_chunks(
                chunks=sample_chunks,
                area="Test",
                site="Test",
                model="gemini-2.0-flash",
                client=mock_client
            )


def test_extract_topics_invalid_json_raises_error(mock_client, sample_chunks):
    """Test that invalid JSON raises ValueError"""
    # Mock API response with invalid JSON
    mock_response = Mock()
    mock_response.text = 'This is not valid JSON'
    mock_client.models.generate_content = Mock(return_value=mock_response)

    with patch('gemini.topic_extractor.PromptLoader') as MockPromptLoader:
        mock_config = Mock()
        mock_config.model_name = "gemini-2.0-flash"
        mock_config.temperature = 0.3
        mock_config.format = Mock(return_value=("System", "User"))
        MockPromptLoader.load = Mock(return_value=mock_config)

        with pytest.raises(ValueError, match="Failed to parse topic extraction response"):
            extract_topics_from_chunks(
                chunks=sample_chunks,
                area="Test",
                site="Test",
                model="gemini-2.0-flash",
                client=mock_client
            )


def test_extract_topics_non_list_raises_error(mock_client, sample_chunks):
    """Test that non-list JSON raises Exception"""
    # Mock API response with object instead of array
    mock_response = Mock()
    mock_response.text = '{"topics": ["topic1", "topic2"]}'
    mock_client.models.generate_content = Mock(return_value=mock_response)

    with patch('gemini.topic_extractor.PromptLoader') as MockPromptLoader:
        mock_config = Mock()
        mock_config.model_name = "gemini-2.0-flash"
        mock_config.temperature = 0.3
        mock_config.format = Mock(return_value=("System", "User"))
        MockPromptLoader.load = Mock(return_value=mock_config)

        with pytest.raises(Exception, match="Expected JSON array"):
            extract_topics_from_chunks(
                chunks=sample_chunks,
                area="Test",
                site="Test",
                model="gemini-2.0-flash",
                client=mock_client
            )


def test_extract_topics_api_error_propagates(mock_client, sample_chunks):
    """Test that API errors are propagated as Exception"""
    # Mock API call to raise an exception
    mock_client.models.generate_content = Mock(side_effect=Exception("API Error"))

    with patch('gemini.topic_extractor.PromptLoader') as MockPromptLoader:
        mock_config = Mock()
        mock_config.model_name = "gemini-2.0-flash"
        mock_config.temperature = 0.3
        mock_config.format = Mock(return_value=("System", "User"))
        MockPromptLoader.load = Mock(return_value=mock_config)

        with pytest.raises(Exception, match="Topic extraction failed"):
            extract_topics_from_chunks(
                chunks=sample_chunks,
                area="Test",
                site="Test",
                model="gemini-2.0-flash",
                client=mock_client
            )
