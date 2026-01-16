# Prompt Configurations

This directory contains YAML-based prompt configurations for LLM API calls.

## YAML Schema

Each YAML file should contain the following fields:

```yaml
model_name: <string>      # Gemini model name (e.g., "gemini-2.0-flash", "gemini-1.5-pro")
temperature: <float>      # Temperature parameter (0.0 to 2.0)
system_prompt: |          # System instruction with variable placeholders
  <multi-line system prompt>
user_prompt: |            # User prompt template with variable placeholders
  <multi-line user prompt>
```

## Variable Interpolation

Use Python format string placeholders in prompts:
- `{area}` - Geographic area/region
- `{site}` - Specific site within the area
- `{context}` - Source material/context for RAG
- `{question}` - User's question
- `{conversation_history}` - Previous conversation messages
- `{bot_name}` - Bot name/persona
- `{bot_personality}` - Bot personality description

## Example

See [tourism_qa.yaml](tourism_qa.yaml) for a working example of a tourism guide assistant prompt configuration.

## Creating New Prompt Configurations

1. Copy an existing YAML file as a template
2. Modify `model_name` and `temperature` as needed
3. Update `system_prompt` and `user_prompt` with your desired prompts
4. Use `{variable_name}` placeholders where dynamic content should be inserted
5. Save the file with a descriptive name (e.g., `museum_qa.yaml`, `historical_site_qa.yaml`)

## Usage in Code

```python
from gemini.prompt_loader import PromptLoader

# Load prompt configuration
prompt_config = PromptLoader.load('config/prompts/tourism_qa.yaml')

# Interpolate variables
system_prompt, user_prompt = prompt_config.format(
    area="Galilee",
    site="Capernaum",
    context="Historical information...",
    question="What is the significance of this site?"
)
```
