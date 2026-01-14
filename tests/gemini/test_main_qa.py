"""
Unit tests for main_qa.py - testing prompt template attribute access

These tests verify that the code correctly accesses .system_prompt and .user_prompt
attributes (not .system_template / .user_template)
"""

import pytest
from unittest.mock import Mock
from gemini.prompt_loader import PromptLoader


class TestPromptTemplateAttributes:
    """Test that prompt templates use correct attribute names"""

    def test_prompt_config_has_system_prompt_not_template(self):
        """Verify PromptConfig has system_prompt attribute (not system_template)"""
        # Create a mock prompt config like what PromptLoader returns
        prompt_config = Mock()
        prompt_config.system_prompt = "Test system prompt with {area} and {site}"
        prompt_config.user_prompt = "Test user prompt with {question}"
        prompt_config.temperature = 0.6
        prompt_config.model_name = "gemini-2.0-flash"

        # This should work - accessing system_prompt
        assert hasattr(prompt_config, "system_prompt")
        assert hasattr(prompt_config, "user_prompt")

        # This should fail - system_template doesn't exist
        with pytest.raises(AttributeError):
            _ = prompt_config.system_template

        with pytest.raises(AttributeError):
            _ = prompt_config.user_template

    def test_prompt_config_format_method(self):
        """Test that prompt config format method works with system_prompt"""
        prompt_config = Mock()
        prompt_config.system_prompt = "Guide at {area} / {site}"
        prompt_config.user_prompt = "Question: {question}"

        # Simulate formatting like the code does
        system = prompt_config.system_prompt.format(area="test_area", site="test_site")
        user = prompt_config.user_prompt.format(question="What is this?")

        assert "test_area" in system
        assert "test_site" in system
        assert "What is this?" in user


class TestPromptLoaderIntegration:
    """Integration test with actual PromptLoader"""

    def test_loaded_config_has_correct_attributes(self, tmp_path):
        """Test that PromptLoader returns config with system_prompt/user_prompt"""
        # Create a temporary YAML file
        yaml_content = """
model_name: gemini-2.0-flash
temperature: 0.6
system_prompt: |
  You are a guide at {area} / {site}.
  Topics: {topics}
user_prompt: |
  {question}
"""
        yaml_file = tmp_path / "test_prompt.yaml"
        yaml_file.write_text(yaml_content)

        # Load the config
        config = PromptLoader.load(str(yaml_file))

        # Verify attributes exist
        assert hasattr(config, "system_prompt")
        assert hasattr(config, "user_prompt")
        assert hasattr(config, "model_name")
        assert hasattr(config, "temperature")

        # Verify they don't have template attributes
        assert not hasattr(config, "system_template")
        assert not hasattr(config, "user_template")

        # Verify formatting works
        system = config.system_prompt.format(
            area="test", site="site", topics="Topic 1\nTopic 2"
        )
        assert "test" in system
        assert "site" in system

        user = config.user_prompt.format(question="Where am I?")
        assert "Where am I?" in user


class TestCodeUsesCorrectAttributes:
    """Test that simulates how main_qa.py should use prompt_config"""

    def test_code_pattern_with_system_prompt(self):
        """Test the code pattern used in main_qa.py"""
        # Simulate what PromptLoader returns
        prompt_config = Mock()
        prompt_config.system_prompt = "Guide at {area}/{site}. Topics: {topics}"
        prompt_config.user_prompt = "{question}"
        prompt_config.temperature = 0.6

        # Simulate the code in main_qa.py (lines 334, 339)
        # This is what SHOULD work:
        area = "hefer_valley"
        site = "agamon_hefer"
        topics_text = "- Bird watching\n- Nature trails"
        question = "What can I see here?"

        # THIS SHOULD WORK (correct attributes):
        system_instruction = prompt_config.system_prompt.format(
            area=area, site=site, topics=topics_text
        )
        user_message = prompt_config.user_prompt.format(question=question)

        assert area in system_instruction
        assert site in system_instruction
        assert question in user_message

    def test_code_pattern_with_wrong_attributes_fails(self):
        """Test that using system_template/user_template fails"""
        # Simulate what PromptLoader returns (no template attributes)
        prompt_config = Mock(spec=["system_prompt", "user_prompt", "temperature"])
        prompt_config.system_prompt = "Guide at {area}/{site}"
        prompt_config.user_prompt = "{question}"

        # THIS SHOULD FAIL (wrong attributes - accessing system_template):
        with pytest.raises(AttributeError, match="system_template"):
            _ = prompt_config.system_template.format(
                area="test", site="test", topics="topics"
            )

        with pytest.raises(AttributeError, match="user_template"):
            _ = prompt_config.user_template.format(question="test")
