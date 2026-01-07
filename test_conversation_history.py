#!/usr/bin/env python3
"""
Unit test for conversation history conversion logic
Tests the message format conversion without requiring API calls
"""

from google.genai import types


def convert_messages_to_gemini_format(messages):
    """
    Convert messages from session state format to Gemini API format
    This is the core logic extracted from get_response() for testing
    """
    # Implement sliding window: keep only last 10 messages
    recent_messages = messages[-10:] if len(messages) > 10 else messages

    # Convert messages to Gemini API format
    conversation_history = []
    for msg in recent_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Skip messages with empty content
        if not content:
            continue

        # Map "assistant" to "model" for Gemini API compatibility
        if role == "assistant":
            role = "model"
        elif role not in ["user", "model"]:
            # Skip messages with invalid roles
            continue

        # Strip metadata fields (time, etc.) and only pass role and content
        conversation_history.append(
            types.Content(role=role, parts=[types.Part.from_text(text=content)])
        )

    return conversation_history


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

    print("✓ Basic conversation test passed")


def test_sliding_window():
    """Test that sliding window keeps only last 10 messages"""
    messages = [
        {"role": "user", "content": f"Question {i}"} for i in range(15)
    ]

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 10
    assert result[0].parts[0].text == "Question 5"  # First kept message
    assert result[-1].parts[0].text == "Question 14"  # Last message

    print("✓ Sliding window test passed")


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

    print("✓ Role mapping test passed")


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

    print("✓ Metadata stripping test passed")


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

    print("✓ Invalid roles skipped test passed")


def test_empty_messages():
    """Test handling of empty message list"""
    messages = []

    result = convert_messages_to_gemini_format(messages)

    assert len(result) == 0

    print("✓ Empty messages test passed")


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

    print("✓ Empty content skipped test passed")


if __name__ == "__main__":
    print("Running conversation history conversion tests...\n")

    test_basic_conversation()
    test_sliding_window()
    test_role_mapping()
    test_metadata_stripping()
    test_invalid_roles_skipped()
    test_empty_messages()
    test_empty_content_skipped()

    print("\n✅ All tests passed!")
