"""
Unit tests for PromptLoader
"""

import pytest
import yaml

from gemini.prompt_loader import PromptConfig, PromptLoader


def test_prompt_config_format():
    """Test variable interpolation in PromptConfig"""
    config = PromptConfig(
        model_name="gemini-2.0-flash",
        temperature=0.7,
        system_prompt="You are {bot_name} for {area}.",
        user_prompt="Question: {question}",
    )

    system, user = config.format(
        bot_name="TourGuide", area="Galilee", question="What to see?"
    )

    assert system == "You are TourGuide for Galilee."
    assert user == "Question: What to see?"


def test_prompt_config_format_missing_variable():
    """Test that missing variables raise KeyError"""
    config = PromptConfig(
        model_name="gemini-2.0-flash",
        temperature=0.7,
        system_prompt="You are {bot_name}.",
        user_prompt="Question: {question}",
    )

    with pytest.raises(KeyError, match="Missing required variable"):
        config.format(bot_name="TourGuide")  # Missing 'question'


def test_prompt_loader_load_valid_yaml(tmp_path):
    """Test loading a valid YAML configuration"""
    yaml_file = tmp_path / "test_prompt.yaml"
    yaml_content = {
        "model_name": "gemini-2.0-flash",
        "temperature": 0.5,
        "system_prompt": "System prompt with {variable}",
        "user_prompt": "User prompt",
    }

    with open(yaml_file, "w") as f:
        yaml.dump(yaml_content, f)

    config = PromptLoader.load(str(yaml_file))

    assert config.model_name == "gemini-2.0-flash"
    assert config.temperature == 0.5
    assert config.system_prompt == "System prompt with {variable}"
    assert config.user_prompt == "User prompt"


def test_prompt_loader_load_missing_file():
    """Test that loading non-existent file raises FileNotFoundError"""
    with pytest.raises(FileNotFoundError, match="not found"):
        PromptLoader.load("nonexistent_file.yaml")


def test_prompt_loader_load_invalid_yaml(tmp_path):
    """Test that invalid YAML raises YAMLError"""
    yaml_file = tmp_path / "invalid.yaml"
    with open(yaml_file, "w") as f:
        f.write("invalid: yaml: content: [")

    with pytest.raises(yaml.YAMLError):
        PromptLoader.load(str(yaml_file))


def test_prompt_loader_load_missing_required_fields(tmp_path):
    """Test that missing required fields raises ValueError"""
    yaml_file = tmp_path / "incomplete.yaml"
    yaml_content = {
        "model_name": "gemini-2.0-flash",
        # Missing temperature, system_prompt, user_prompt
    }

    with open(yaml_file, "w") as f:
        yaml.dump(yaml_content, f)

    with pytest.raises(ValueError, match="missing required fields"):
        PromptLoader.load(str(yaml_file))


def test_prompt_loader_load_invalid_types(tmp_path):
    """Test that invalid field types raise ValueError"""
    yaml_file = tmp_path / "invalid_types.yaml"
    yaml_content = {
        "model_name": 123,  # Should be string
        "temperature": 0.7,
        "system_prompt": "System",
        "user_prompt": "User",
    }

    with open(yaml_file, "w") as f:
        yaml.dump(yaml_content, f)

    with pytest.raises(ValueError, match="Invalid type"):
        PromptLoader.load(str(yaml_file))


def test_prompt_loader_load_empty_yaml(tmp_path):
    """Test that empty YAML file raises ValueError"""
    yaml_file = tmp_path / "empty.yaml"
    with open(yaml_file, "w") as f:
        f.write("")  # Empty file

    with pytest.raises(ValueError, match="empty or does not contain a valid configuration"):
        PromptLoader.load(str(yaml_file))


def test_prompt_loader_load_invalid_temperature_bounds(tmp_path):
    """Test that temperature outside valid bounds raises ValueError"""
    # Test temperature too high
    yaml_file_high = tmp_path / "temp_high.yaml"
    yaml_content_high = {
        "model_name": "gemini-2.0-flash",
        "temperature": 3.0,  # Too high (max is 2.0)
        "system_prompt": "System",
        "user_prompt": "User",
    }
    with open(yaml_file_high, "w") as f:
        yaml.dump(yaml_content_high, f)

    with pytest.raises(ValueError, match="Invalid temperature value.*Must be between 0.0 and 2.0"):
        PromptLoader.load(str(yaml_file_high))

    # Test temperature too low
    yaml_file_low = tmp_path / "temp_low.yaml"
    yaml_content_low = {
        "model_name": "gemini-2.0-flash",
        "temperature": -0.5,  # Too low (min is 0.0)
        "system_prompt": "System",
        "user_prompt": "User",
    }
    with open(yaml_file_low, "w") as f:
        yaml.dump(yaml_content_low, f)

    with pytest.raises(ValueError, match="Invalid temperature value.*Must be between 0.0 and 2.0"):
        PromptLoader.load(str(yaml_file_low))


def test_prompt_loader_load_relative_path():
    """Test loading with relative path from project root"""
    # This assumes prompts/tourism_qa.yaml exists in the project
    config = PromptLoader.load("prompts/tourism_qa.yaml")

    assert config.model_name == "gemini-2.0-flash"
    assert config.temperature == 0.6
    assert "{area}" in config.system_prompt
    assert "{site}" in config.system_prompt
    assert "{context}" in config.user_prompt
    assert "{question}" in config.user_prompt


def test_end_to_end_tourism_qa():
    """Test full workflow with tourism_qa.yaml"""
    config = PromptLoader.load("prompts/tourism_qa.yaml")

    system, user = config.format(
        area="Galilee",
        site="Capernaum",
        context="Ancient fishing village...",
        question="What is significant about this site?",
    )

    # System prompt should have area and site
    assert "Galilee" in system
    assert "Capernaum" in system

    # User prompt should have context and question
    assert "Ancient fishing village" in user
    assert "What is significant about this site?" in user
