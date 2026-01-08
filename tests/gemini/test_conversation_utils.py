#!/usr/bin/env python3
"""
Unit tests for conversation history conversion logic
Tests the message format conversion without requiring API calls
"""

import pytest
from gemini.conversation_utils import convert_messages_to_gemini_format


@pytest.mark.unit
def test_basic_conversation():
    """Test basic user-assistant conversation"""
    messages = [
        {"role": "user", "content": "What attractions are available?"},
        {"role": "assistant", "content": "There are many attractions...", "time": 1.5},
        {"role": "user", "content": "Tell me more about the first one"},
    ]

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 3
    assert result[0].role == "user"
    assert result[0].parts[0].text == "What attractions are available?"
    assert result[1].role == "model"  # assistant mapped to model
    assert result[1].parts[0].text == "There are many attractions..."
    assert result[2].role == "user"
    assert result[2].parts[0].text == "Tell me more about the first one"


@pytest.mark.unit
def test_sliding_window():
    """Test that sliding window keeps only last 10 messages"""
    messages = [
        {"role": "user", "content": f"Question {i}"} for i in range(15)
    ]

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 10
    assert result[0].parts[0].text == "Question 5"  # First kept message
    assert result[-1].parts[0].text == "Question 14"  # Last message


@pytest.mark.unit
def test_role_mapping():
    """Test that assistant role is mapped to model"""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "model", "content": "Also valid"},
    ]

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 3
    assert result[0].role == "user"
    assert result[1].role == "model"  # assistant mapped to model
    assert result[2].role == "model"  # model stays as model


@pytest.mark.unit
def test_metadata_stripping():
    """Test that metadata fields like 'time' are stripped"""
    messages = [
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1", "time": 2.3, "extra": "data"},
    ]

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 2
    # Verify only role and content are in the result (time is stripped)
    assert result[1].role == "model"
    assert result[1].parts[0].text == "Answer 1"
    # No way to check for absence of time field in Content object,
    # but it's not included in the Content construction


@pytest.mark.unit
def test_invalid_roles_skipped():
    """Test that messages with invalid roles are skipped"""
    messages = [
        {"role": "user", "content": "Valid message"},
        {"role": "system", "content": "Invalid role - should be skipped"},
        {"role": "assistant", "content": "Valid message"},
        {"role": "invalid", "content": "Also skipped"},
    ]

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 2  # Only user and assistant messages
    assert result[0].role == "user"
    assert result[1].role == "model"


@pytest.mark.unit
def test_empty_messages():
    """Test handling of empty message list"""
    messages = []

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 0


@pytest.mark.unit
def test_empty_content_skipped():
    """Test that messages with empty content are skipped"""
    messages = [
        {"role": "user", "content": "Valid message"},
        {"role": "assistant", "content": ""},  # Empty content
        {"role": "user", "content": "Another valid message"},
        {"role": "assistant"},  # Missing content key
    ]

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 2  # Only messages with content
    assert result[0].parts[0].text == "Valid message"
    assert result[1].parts[0].text == "Another valid message"


if __name__ == "__main__":
    # Allow running tests directly with python for convenience
    pytest.main([__file__, "-v"])
