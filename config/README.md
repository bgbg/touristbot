# Configuration System

This directory contains all configuration files for the Tourism RAG system, including prompts and location-specific overrides.

## Directory Structure

```
config/
├── prompts/                    # Global prompt configurations
│   ├── tourism_qa.yaml         # Tourism Q&A prompt
│   └── topic_extraction.yaml   # Topic extraction prompt
└── locations/                  # Location-specific overrides
    └── <area>/
        ├── <site>.yaml         # Site-level config override
        └── <site>/
            └── prompts/        # Site-level prompt overrides
                └── <prompt>.yaml
```

## Prompt Configurations

### YAML Schema

Prompt files in `config/prompts/` define LLM behavior and must contain:

```yaml
model: <string>           # Gemini model (e.g., "gemini-2.0-flash")
temperature: <float>      # Temperature (0.0 to 2.0)
system_prompt: |          # System instruction with variable placeholders
  <multi-line system prompt>
user_prompt: |            # User prompt template with variable placeholders
  <multi-line user prompt>
```

### Variable Interpolation

Use Python format string placeholders in prompts:
- `{area}` - Geographic area/region
- `{site}` - Specific site within the area
- `{context}` - Source material/context for RAG
- `{question}` - User's question
- `{conversation_history}` - Previous conversation messages
- `{topics}` - Available topics for the location
- `{bot_name}` - Bot name/persona
- `{bot_personality}` - Bot personality description

### Creating New Prompts

1. Copy an existing YAML file as a template
2. Modify `model` and `temperature` as needed
3. Update `system_prompt` and `user_prompt`
4. Use `{variable_name}` placeholders for dynamic content
5. Save with a descriptive name (e.g., `museum_qa.yaml`)

### Usage in Code

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

## Location-Specific Overrides

### Overview

The system supports hierarchical configuration with location-specific overrides:
- **Global**: `config.yaml` (project root) + `config/prompts/`
- **Area**: `config/locations/<area>.yaml`
- **Site**: `config/locations/<area>/<site>.yaml`
- **Site Prompts**: `config/locations/<area>/<site>/prompts/<prompt>.yaml`

### Merge Hierarchy

```
Global config.yaml → Area override → Site override
Global prompt → Site prompt override
```

Each level inherits from the parent and can override specific fields.

### Partial Overrides

Override files only need to specify fields to change. All other fields are inherited from the parent level.

**Example: Site-level config override**
```yaml
# config/locations/hefer_valley/agamon_hefer.yaml
gemini_rag:
  temperature: 0.5  # Override temperature only
  # model, chunk_tokens, etc. inherited from global config.yaml
```

**Example: Site-level prompt override**
```yaml
# config/locations/hefer_valley/agamon_hefer/prompts/tourism_qa.yaml
temperature: 0.4

system_prompt: |
  אתה דני, מדריך צפרות מומחה באגמון חפר...
  (custom bird-watching guide persona)

# model and user_prompt inherited from global config/prompts/tourism_qa.yaml
```

### Merge Behavior

- **Nested dicts**: Deep merge (child overrides parent, other fields preserved)
- **Lists**: Complete replacement (no smart merging)
- **Primitives**: Override value replaces base value
- **Missing override files**: Graceful fallback to parent level (no errors)

### Loading Overrides in Code

```python
from gemini.config import GeminiConfig
from gemini.prompt_loader import PromptLoader

# Load config with location-specific overrides
config = GeminiConfig.from_yaml(area="hefer_valley", site="agamon_hefer")

# Load prompt with location-specific overrides
prompt = PromptLoader.load(
    "config/prompts/tourism_qa.yaml",
    area="hefer_valley",
    site="agamon_hefer"
)
```

### Common Use Cases

1. **Custom guide personas per site**:
   - Different character/personality for each location
   - Site-specific tone, language, or focus areas
   - Example: bird-watching expert for wetlands, archaeologist for historical sites

2. **Model selection per location**:
   - More powerful model for complex content
   - Faster model for simple locations
   - Example: `model: "gemini-2.5-flash"` for detailed sites

3. **Temperature tuning**:
   - Cooler for factual/technical content (0.3-0.5)
   - Warmer for creative/engaging content (0.7-0.9)
   - Example: 0.4 for nature reserves, 0.8 for cultural sites

### Creating Location Overrides

**Step 1: Create area-level override (optional)**
```bash
# config/locations/hefer_valley.yaml
gemini_rag:
  temperature: 0.6  # Override for entire area
```

**Step 2: Create site-level config override (optional)**
```bash
# config/locations/hefer_valley/agamon_hefer.yaml
gemini_rag:
  temperature: 0.5  # Override for specific site
```

**Step 3: Create site-level prompt override (optional)**
```bash
mkdir -p config/locations/hefer_valley/agamon_hefer/prompts
# config/locations/hefer_valley/agamon_hefer/prompts/tourism_qa.yaml
temperature: 0.4
system_prompt: |
  Custom prompt for this site...
```

### Validation and Error Handling

- Override files must use identical schema to base configuration
- Invalid field names cause explicit errors (no silent failures)
- Malformed YAML fails with clear error messages
- Missing override files are graceful (no errors, use parent config)

### Cache Behavior

- Configurations cached by `lru_cache` with location parameters in cache key
- Different locations get different cached configs
- Config changes require application restart (existing limitation)

### Troubleshooting

**Issue**: Override not being applied
- Check file paths: `config/locations/<area>.yaml` or `config/locations/<area>/<site>.yaml`
- Verify YAML syntax (use YAML validator)
- Check that override field names match base config schema exactly
- Restart application to clear cache

**Issue**: "Field not found" error
- Override field name typo - must match base config exactly
- Nested fields use same structure as base config (e.g., `gemini_rag.temperature`)

**Issue**: List not merging as expected
- Lists are replaced entirely, not merged (by design)
- To add items, must specify complete list with all desired items

## Examples

See existing configurations for reference:
- Global prompt: [prompts/tourism_qa.yaml](prompts/tourism_qa.yaml)
- Site config override: [locations/hefer_valley/agamon_hefer.yaml](locations/hefer_valley/agamon_hefer.yaml)
- Site prompt override: [locations/hefer_valley/agamon_hefer/prompts/tourism_qa.yaml](locations/hefer_valley/agamon_hefer/prompts/tourism_qa.yaml)
