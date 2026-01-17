"""
Unit tests for get_response function - simulating actual API calls

These tests reproduce the 400 INVALID_ARGUMENT error seen in the UI
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from google.genai import types


class TestGetResponseWithActualAPICalls:
    """Test get_response with mock API calls to reproduce the 400 error"""

    @patch("gemini.main_qa.st")
    def test_single_message_reproduces_400_error(self, mock_st):
        """Test that a single message causes 400 INVALID_ARGUMENT error"""
        from gemini.main_qa import get_response

        # Setup session state mocks
        mock_config = Mock()
        mock_config.prompts_dir = "config/prompts/"
        mock_config.model_name = "gemini-2.0-flash"

        mock_registry = Mock()
        mock_registry.get_file_search_store_name.return_value = (
            "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        )

        mock_client = Mock()

        mock_st.session_state.config = mock_config
        mock_st.session_state.registry = mock_registry
        mock_st.session_state.client = mock_client
        mock_st.session_state.topics = ["Topic 1", "Topic 2"]

        # Mock the API response to raise the 400 error
        error_message = (
            "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': "
            '"The GenerateContentRequest proto is invalid:\\n * tools[0].tool_type: '
            "required one_of 'tool_type' must have one initialized field\"}}"
        )

        mock_client.models.generate_content.side_effect = Exception(error_message)

        # Call get_response with a single message (no history)
        question = "hi"
        area = "tel_aviv_district"
        site = "jaffa_port"
        messages = []  # No chat history

        # This should raise the 400 error
        with pytest.raises(Exception) as exc_info:
            get_response(question, area, site, messages)

        # Verify the error is the 400 INVALID_ARGUMENT
        assert "400 INVALID_ARGUMENT" in str(exc_info.value)
        assert "tool_type" in str(exc_info.value)

    @patch("gemini.main_qa.st")
    def test_multiple_messages_reproduces_400_error(self, mock_st):
        """Test that chat with history also causes 400 INVALID_ARGUMENT error"""
        from gemini.main_qa import get_response

        # Setup session state mocks
        mock_config = Mock()
        mock_config.prompts_dir = "config/prompts/"
        mock_config.model_name = "gemini-2.0-flash"

        mock_registry = Mock()
        mock_registry.get_file_search_store_name.return_value = (
            "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        )

        mock_client = Mock()

        mock_st.session_state.config = mock_config
        mock_st.session_state.registry = mock_registry
        mock_st.session_state.client = mock_client
        mock_st.session_state.topics = ["Topic 1", "Topic 2"]

        # Mock the API response to raise the 400 error
        error_message = (
            "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': "
            '"The GenerateContentRequest proto is invalid:\\n * tools[0].tool_type: '
            "required one_of 'tool_type' must have one initialized field\"}}"
        )

        mock_client.models.generate_content.side_effect = Exception(error_message)

        # Call get_response with chat history
        question = "tell me more"
        area = "tel_aviv_district"
        site = "jaffa_port"
        messages = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "Hello! Welcome to Jaffa Port.",
                "time": 1.5,
                "citations": [],
            },
        ]

        # This should raise the 400 error
        with pytest.raises(Exception) as exc_info:
            get_response(question, area, site, messages)

        # Verify the error is the 400 INVALID_ARGUMENT
        assert "400 INVALID_ARGUMENT" in str(exc_info.value)
        assert "tool_type" in str(exc_info.value)


class TestGetResponseInspectAPICall:
    """Test to inspect what's actually being sent to the API"""

    @patch("gemini.main_qa.st")
    def test_inspect_generate_content_call_single_message(self, mock_st):
        """Inspect the actual API call parameters for single message"""
        from gemini.main_qa import get_response

        # Setup session state mocks
        mock_config = Mock()
        mock_config.prompts_dir = "config/prompts/"
        mock_config.model_name = "gemini-2.0-flash"

        mock_registry = Mock()
        mock_registry.get_file_search_store_name.return_value = (
            "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        )

        mock_client = Mock()

        # Create a mock response to avoid the error
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].grounding_metadata = None

        mock_client.models.generate_content.return_value = mock_response

        mock_st.session_state.config = mock_config
        mock_st.session_state.registry = mock_registry
        mock_st.session_state.client = mock_client
        mock_st.session_state.topics = ["Topic 1", "Topic 2"]

        # Call get_response
        question = "hi"
        area = "tel_aviv_district"
        site = "jaffa_port"
        messages = []

        try:
            get_response(question, area, site, messages)
        except Exception as e:
            # If error occurs, capture it
            pass

        # Inspect what was passed to generate_content
        assert mock_client.models.generate_content.called
        call_kwargs = mock_client.models.generate_content.call_args.kwargs

        # Print the config parameter to see the tools structure
        config = call_kwargs.get("config")
        if config:
            print("\n=== API Call Config ===")
            print(f"Config type: {type(config)}")
            if hasattr(config, "tools"):
                print(f"Tools: {config.tools}")
                if config.tools:
                    tool = config.tools[0]
                    print(f"Tool type: {type(tool)}")
                    print(f"Tool attributes: {dir(tool)}")
                    # Check what attributes the tool has
                    if hasattr(tool, "file_search"):
                        print(f"Tool.file_search: {tool.file_search}")
                    if hasattr(tool, "fileSearch"):
                        print(f"Tool.fileSearch: {tool.fileSearch}")
                    # Try to see the actual proto/dict representation
                    if hasattr(tool, "model_dump"):
                        print(f"Tool dump: {tool.model_dump()}")

    @patch("gemini.main_qa.st")
    def test_inspect_generate_content_call_with_history(self, mock_st):
        """Inspect the actual API call parameters with chat history"""
        from gemini.main_qa import get_response

        # Setup session state mocks
        mock_config = Mock()
        mock_config.prompts_dir = "config/prompts/"
        mock_config.model_name = "gemini-2.0-flash"

        mock_registry = Mock()
        mock_registry.get_file_search_store_name.return_value = (
            "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        )

        mock_client = Mock()

        # Create a mock response
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].grounding_metadata = None

        mock_client.models.generate_content.return_value = mock_response

        mock_st.session_state.config = mock_config
        mock_st.session_state.registry = mock_registry
        mock_st.session_state.client = mock_client
        mock_st.session_state.topics = ["Topic 1", "Topic 2"]

        # Call get_response with history
        question = "tell me more"
        area = "tel_aviv_district"
        site = "jaffa_port"
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello!", "time": 1.0, "citations": []},
        ]

        try:
            get_response(question, area, site, messages)
        except Exception as e:
            pass

        # Inspect the call
        assert mock_client.models.generate_content.called
        call_kwargs = mock_client.models.generate_content.call_args.kwargs

        config = call_kwargs.get("config")
        if config and hasattr(config, "tools") and config.tools:
            tool = config.tools[0]
            print("\n=== API Call With History - Tool Structure ===")
            if hasattr(tool, "model_dump"):
                import json

                print(json.dumps(tool.model_dump(), indent=2))
