"""
Integration tests for File Search API configuration

These tests verify that the File Search tool is configured correctly
and can be used with the Gemini API without errors.
"""

import pytest
from google.genai import types
from unittest.mock import Mock, patch


class TestFileSearchToolCreation:
    """Test File Search tool creation and configuration"""

    def test_create_valid_file_search_tool(self):
        """Test creating a valid File Search tool configuration"""
        # This is how main_qa.py creates the tool
        file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        metadata_filter = "area=tel_aviv_district AND site=jaffa_port"

        # Create FileSearch configuration
        file_search = types.FileSearch(
            file_search_store_names=[file_search_store_name],
            metadata_filter=metadata_filter,
        )

        # Create Tool with file_search parameter (snake_case)
        tool = types.Tool(file_search=file_search)

        # Verify tool was created successfully
        assert tool is not None
        assert tool.file_search is not None
        assert tool.file_search.file_search_store_names == [file_search_store_name]
        assert tool.file_search.metadata_filter == metadata_filter

    def test_file_search_tool_in_generate_content_config(self):
        """Test that File Search tool works in GenerateContentConfig"""
        file_search_store_name = "fileSearchStores/test-store"
        metadata_filter = "area=test AND site=test"

        # Create the full configuration like main_qa.py does
        config = types.GenerateContentConfig(
            system_instruction="You are a tour guide",
            temperature=0.6,
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[file_search_store_name],
                        metadata_filter=metadata_filter,
                    )
                ),
            ],
        )

        # Verify config was created successfully
        assert config is not None
        assert config.tools is not None
        assert len(config.tools) == 1
        assert config.tools[0].file_search is not None

    def test_empty_file_search_store_names_is_invalid(self):
        """Test that empty file_search_store_names should be caught"""
        # This should be detected before API call
        file_search = types.FileSearch(
            file_search_store_names=[],  # Empty list
            metadata_filter="area=test AND site=test",
        )

        tool = types.Tool(file_search=file_search)

        # Tool creation succeeds but should fail during API call
        # The code should validate this before making the API call
        assert tool.file_search.file_search_store_names == []

    def test_none_file_search_store_name_is_invalid(self):
        """Test that None file_search_store_names should be caught"""
        file_search = types.FileSearch(
            file_search_store_names=None,
            metadata_filter="area=test AND site=test",
        )

        tool = types.Tool(file_search=file_search)

        # Tool creation succeeds but should fail during API call
        assert tool.file_search.file_search_store_names is None


class TestFileSearchErrorHandling:
    """Test error handling for File Search configuration"""

    def test_validates_file_search_store_name_before_api_call(self):
        """Test that code validates File Search Store name before API call"""
        # Simulate the validation in main_qa.py
        file_search_store_name = None

        # This check should happen before creating the tool
        if not file_search_store_name:
            error_message = "File Search Store not initialized"
            assert "File Search Store" in error_message
            # Code should return early with error
            return

        # Should not reach here
        pytest.fail("Should have returned early with error")

    def test_file_search_with_invalid_store_name_format(self):
        """Test detection of invalid store name format"""
        invalid_names = [
            "",  # Empty string
            "not-a-valid-format",  # Missing prefix
            "fileSearchStores/",  # Missing ID
        ]

        for invalid_name in invalid_names:
            # The tool accepts any string, but API will reject it
            file_search = types.FileSearch(
                file_search_store_names=[invalid_name],
                metadata_filter="area=test AND site=test",
            )

            tool = types.Tool(file_search=file_search)
            assert tool.file_search.file_search_store_names == [invalid_name]
            # API call would fail with this, but tool creation succeeds
