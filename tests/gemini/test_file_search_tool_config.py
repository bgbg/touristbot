"""
Test File Search Tool configuration to catch proto serialization issues

These tests validate that the Tool object is correctly configured BEFORE
being sent to the API, catching proto validation errors early.
"""

import pytest
from google.genai import types
import json


class TestFileSearchToolConfiguration:
    """Test that File Search Tool is properly configured for proto serialization"""

    def test_file_search_tool_structure(self):
        """Test that Tool object has correct structure for File Search"""
        # Create the exact same tool as main_qa.py
        file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        metadata_filter = "area=tel_aviv_district AND site=jaffa_port"

        # Create FileSearch object
        file_search = types.FileSearch(
            file_search_store_names=[file_search_store_name],
            metadata_filter=metadata_filter,
        )

        # Create Tool with file_search
        tool = types.Tool(file_search=file_search)

        # Verify the tool has file_search attribute
        assert tool.file_search is not None
        assert tool.file_search.file_search_store_names == [file_search_store_name]
        assert tool.file_search.metadata_filter == metadata_filter

    def test_tool_model_dump_shows_file_search(self):
        """Test that tool.model_dump() properly shows file_search as initialized"""
        file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        metadata_filter = "area=tel_aviv_district AND site=jaffa_port"

        file_search = types.FileSearch(
            file_search_store_names=[file_search_store_name],
            metadata_filter=metadata_filter,
        )
        tool = types.Tool(file_search=file_search)

        # Dump the model to see what will be serialized
        tool_dict = tool.model_dump()

        # Print for debugging
        print("\n=== Tool model_dump() ===")
        print(json.dumps(tool_dict, indent=2))

        # Verify file_search is in the dump
        assert "file_search" in tool_dict
        assert tool_dict["file_search"] is not None
        assert tool_dict["file_search"]["file_search_store_names"] == [
            file_search_store_name
        ]

    def test_tool_model_dump_exclude_none(self):
        """Test tool serialization with exclude_none to see proto structure"""
        file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        metadata_filter = "area=tel_aviv_district AND site=jaffa_port"

        file_search = types.FileSearch(
            file_search_store_names=[file_search_store_name],
            metadata_filter=metadata_filter,
        )
        tool = types.Tool(file_search=file_search)

        # Dump with exclude_none to see what would actually be sent
        tool_dict = tool.model_dump(exclude_none=True)

        print("\n=== Tool model_dump(exclude_none=True) ===")
        print(json.dumps(tool_dict, indent=2))

        # Check that only file_search is present (other tool types should be excluded)
        assert "file_search" in tool_dict
        assert tool_dict["file_search"] is not None

        # Count how many tool types are present (should only be file_search)
        tool_types_present = [
            k
            for k in tool_dict.keys()
            if k
            in [
                "function_declarations",
                "retrieval",
                "google_search_retrieval",
                "file_search",
                "code_execution",
            ]
            and tool_dict[k] is not None
        ]

        print(f"\n=== Tool types present: {tool_types_present} ===")
        assert len(tool_types_present) == 1, (
            f"Expected exactly 1 tool type, got {len(tool_types_present)}: {tool_types_present}"
        )
        assert tool_types_present[0] == "file_search"

    def test_generate_content_config_with_tool(self):
        """Test that GenerateContentConfig properly includes the tool"""
        file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        metadata_filter = "area=tel_aviv_district AND site=jaffa_port"

        file_search = types.FileSearch(
            file_search_store_names=[file_search_store_name],
            metadata_filter=metadata_filter,
        )
        tool = types.Tool(file_search=file_search)

        # Create config like main_qa.py does
        config = types.GenerateContentConfig(
            system_instruction="You are a tour guide",
            temperature=0.6,
            tools=[tool],
        )

        # Verify config has the tool
        assert config.tools is not None
        assert len(config.tools) == 1
        assert config.tools[0].file_search is not None

        # Dump the config
        config_dict = config.model_dump(exclude_none=True)
        print("\n=== GenerateContentConfig model_dump ===")
        print(json.dumps(config_dict, indent=2))

        # Verify tools[0] has file_search
        assert "tools" in config_dict
        assert len(config_dict["tools"]) == 1
        assert "file_search" in config_dict["tools"][0]

    def test_tool_serialization_to_json(self):
        """Test JSON serialization of Tool to see if it matches API expectations"""
        file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        metadata_filter = "area=tel_aviv_district AND site=jaffa_port"

        file_search = types.FileSearch(
            file_search_store_names=[file_search_store_name],
            metadata_filter=metadata_filter,
        )
        tool = types.Tool(file_search=file_search)

        # Try to serialize to JSON (what would be sent to API)
        tool_json = tool.model_dump_json(exclude_none=True)
        print("\n=== Tool JSON (exclude_none=True) ===")
        print(tool_json)

        # Parse back and verify
        tool_data = json.loads(tool_json)
        assert "file_search" in tool_data

        # Check the actual field names used in JSON
        print(f"\n=== file_search fields: {tool_data['file_search'].keys()} ===")

        # Python SDK uses snake_case in JSON
        assert "file_search_store_names" in tool_data["file_search"]
        assert "metadata_filter" in tool_data["file_search"]

    def test_tool_serialization_with_by_alias(self):
        """Test if model_dump with by_alias produces correct API format"""
        file_search_store_name = "fileSearchStores/tarasatourismrag-yhh2ivs2lpq4"
        metadata_filter = "area=tel_aviv_district AND site=jaffa_port"

        file_search = types.FileSearch(
            file_search_store_names=[file_search_store_name],
            metadata_filter=metadata_filter,
        )
        tool = types.Tool(file_search=file_search)

        # Try serialization with by_alias (which might produce camelCase)
        tool_dict_alias = tool.model_dump(by_alias=True, exclude_none=True)
        print("\n=== Tool model_dump(by_alias=True, exclude_none=True) ===")
        print(json.dumps(tool_dict_alias, indent=2))

        # Verify file_search is present
        assert "file_search" in tool_dict_alias or "fileSearch" in tool_dict_alias
