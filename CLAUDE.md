# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo.

## Overview
- Tourism RAG system using Google Gemini File Search API with metadata filtering.
- Multimodal support: Automatically extracts, uploads, and displays images from MS Word documents.
- Streamlit UI for Q&A and content management; CLI uploader for batch loads.
- Content organized by area/site under data/locations/.
- Server-side chunking: Gemini handles all chunking automatically (no local chunks).
- Citations: Automatic source attribution via grounding metadata.

## Setup
- Python 3.11+; conda environment name: `tarasa`.
- Activate environment: `conda activate tarasa`, then install dependencies: `pip install -r requirements.txt`.
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`; set `GOOGLE_API_KEY` and GCS credentials.
- **GCS is mandatory**: Image and store registries are stored in GCS bucket (no local fallback).
- Adjust `config.yaml` for GCS paths, File Search Store name, chunking params, and model selection.
- First run: Automatic migration moves any local registry files to GCS.

## Running
- Web app: `streamlit run gemini/main_qa.py` (defaults to http://localhost:8501).
- CLI upload: `python gemini/main_upload.py [--area <area> --site <site> --force]`.

## Project Layout
- gemini/: core logic for File Search uploads, QA flow, registry, logging, topic extraction, image handling.
  - file_search_store.py: File Search Store management (create, upload with metadata).
  - main_qa.py: Streamlit UI with citation and image display.
  - main_upload.py: CLI uploader (whole files with metadata, no chunking, automatic image extraction).
  - store_registry.py: Maps locations to File Search Store name (GCS-backed).
  - image_extractor.py: Extracts images and metadata from DOCX files.
  - image_storage.py: Uploads images to GCS bucket.
  - file_api_manager.py: Uploads images to Gemini File API for multimodal context.
  - image_registry.py: Registry mapping images to metadata (GCS-backed, area/site/doc).
  - upload_tracker.py: Tracks uploaded files (temporary cache in .cache/).
- data/locations/: source content organized by area/site hierarchy.
- topics/: generated topic lists stored in GCS at `topics/<area>/<site>/topics.json`.
- prompts/: prompt YAMLs for the QA system (tourism_qa.yaml, topic_extraction.yaml).
- config.yaml: app settings including GCS paths for registries.
- .cache/: temporary build artifacts (upload tracking, excluded from git).
- .streamlit/secrets.toml: API keys (never commit).
- config/locations/: location-specific configuration overrides (optional).

## Location-Specific Configuration Overrides
- Hierarchical configuration system: global → area → site.
- Each location can override specific fields; all other fields inherited from parent level.
- **Partial overrides supported**: Override files only need to specify fields to change.
- Two types of overrides:
  1. **Config overrides**: `config/locations/<area>.yaml` or `config/locations/<area>/<site>.yaml`
  2. **Prompt overrides**: `config/locations/<area>/prompts/<prompt_name>.yaml` or `config/locations/<area>/<site>/prompts/<prompt_name>.yaml`

### File Structure
```
config/locations/
├── hefer_valley.yaml                    # Area-level config override (optional)
├── hefer_valley/
│   ├── agamon_hefer.yaml               # Site-level config override (optional)
│   └── agamon_hefer/
│       └── prompts/
│           └── tourism_qa.yaml         # Site-level prompt override (optional)
```

### Example: Config Override (temperature only)
```yaml
# config/locations/hefer_valley/agamon_hefer.yaml
# Only override temperature - all other fields inherited from global config.yaml
gemini_rag:
  temperature: 0.5  # Override: cooler temperature for this site
  # model, chunk_tokens, etc. inherited from global config
```

### Example: Prompt Override (custom guide persona)
```yaml
# config/locations/hefer_valley/agamon_hefer/prompts/tourism_qa.yaml
# Override temperature and system_prompt - model_name and user_prompt inherited
temperature: 0.4

system_prompt: |
  אתה דני, מדריך צפרות מומחה באגמון חפר...
  (custom bird-watching guide persona)

# model_name and user_prompt inherited from global prompts/tourism_qa.yaml
```

### Merge Behavior
- **Nested dicts**: Deep merge (child overrides parent, other fields preserved)
- **Lists**: Complete replacement (no smart merging)
- **Primitives**: Override value replaces base value
- **Missing override files**: Graceful fallback to parent level (no errors)

### Example Merge Flow
```
Global config.yaml:                     Site override (agamon_hefer.yaml):
  gemini_rag:                             gemini_rag:
    temperature: 0.7                        temperature: 0.5
    model: gemini-2.0-flash         →
    chunk_tokens: 400

Result for agamon_hefer:
  gemini_rag:
    temperature: 0.5    ← overridden from site
    model: gemini-2.0-flash    ← inherited from global
    chunk_tokens: 400    ← inherited from global
```

### API Usage
```python
# Load global config only
config = GeminiConfig.from_yaml()

# Load with area override
config = GeminiConfig.from_yaml(area="hefer_valley")

# Load with site override (inherits from area if exists, then global)
config = GeminiConfig.from_yaml(area="hefer_valley", site="agamon_hefer")

# Same pattern for prompts
prompt = PromptLoader.load("prompts/tourism_qa.yaml", area="hefer_valley", site="agamon_hefer")
```

### Common Use Cases
1. **Custom guide personas per site** (primary use case):
   - Different character/personality for each location
   - Site-specific tone, language, or focus areas
   - Example: bird-watching expert for wetlands, archaeology expert for historical sites

2. **Model selection per location**:
   - More powerful model for complex content
   - Faster model for simple locations
   - Example: `model: "gemini-2.5-flash"` for detailed sites

3. **Temperature tuning**:
   - Cooler for factual/technical content
   - Warmer for creative/engaging content
   - Example: 0.4 for nature reserves, 0.8 for cultural sites

### Validation and Error Handling
- Override files must use identical schema to base configuration
- Invalid field names will cause explicit errors (no silent failures)
- Malformed YAML will fail with clear error messages
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

## Topic Generation Feature
- Automatically extracts 5-10 key topics from location content during upload.
- Topics stored in GCS at `topics/<area>/<site>/topics.json` as JSON array.
- Bot proactively suggests uncovered topics during conversation:
  - On greeting
  - On "what else?" questions
  - In first response
  - Once every 4-5 subsequent responses
- Streamlit UI displays clickable topics in sidebar "Available Topics" section.
- CLI tool for regeneration: `python gemini/generate_topics.py --area <area> --site <site>`.
- Topics are independent of File Search - pre-generated and stored in GCS.

## File Search API Integration
- Single File Search Store for all locations (name in config: file_search_store_name).
- Files uploaded whole with metadata: area, site, doc (no local chunking).
- Server-side chunking: 400 tokens/chunk with 15% overlap (configurable in config.yaml).
- Metadata filtering: queries use "area=X AND site=Y" (AIP-160 syntax).
- Citations extracted from grounding_metadata in responses.
- Upload process: whole files → File Search Store → metadata tags → server chunks.
- Query process: metadata filter → File Search retrieval → Gemini response → citations.

## Multimodal Image Support
- Automatically extracts images from DOCX files during upload (Phase 2B hybrid approach).
- Image extraction: python-docx library extracts inline images with captions and context.
- Triple storage: Images stored in GCS bucket, uploaded to Gemini File API, tracked in GCS image registry.
- Image registry: JSON-based system mapping area/site/doc → image metadata (URIs, captions, context).
- Sequential naming: image_001.jpg, image_002.jpg, etc. within each document.
- Hebrew support: Full UTF-8 support for captions and context text.
- Multimodal context: Image URIs included in user messages for Gemini API (up to 5 images per query).
- UI display: Images shown in expandable sections with captions and context (before/after text).
- Upload process: DOCX text → File Search Store → extract images → upload to GCS & File API → register metadata.
- Query process: query images by area/site → include URIs in API call → LLM assesses relevance → display relevant images in UI.
- Note: File Search API does NOT extract images from DOCX (text-only), hence separate image pipeline.

### LLM-Based Image Relevance (Issue #18)
- Gemini API returns structured output (JSON) with image relevance signals via Pydantic schema `ImageAwareResponse`.
- Structured output fields:
  - `response_text`: Main response to user query (Hebrew or query language).
  - `should_include_images`: Boolean indicating if images should be shown (false for initial greetings, true for substantive queries).
  - `image_relevance`: Dict mapping image URIs to relevance scores (0-100).
- Initial greeting detection: LLM detects greeting context and sets `should_include_images=false` (no hardcoded history checks).
- Image filtering: Only images with relevance score >= 60 are displayed.
- Commentary generation: System prompt guides LLM to add natural commentary when showing images (e.g., "שימו לב כמה יפים השקנאים האלה!").
- Single API call: All logic (response generation, greeting detection, relevance scoring) handled in one Gemini API call.
- Fallback: If structured output parsing fails, defaults to showing all images (backward compatibility).

## Data Storage Architecture
- **GCS is mandatory**: All registries stored in Google Cloud Storage (no local fallback).
- **Registry files** (GCS paths in `config.yaml`):
  - `metadata/image_registry.json`: Image metadata registry (area/site/doc → image URIs, captions, context).
  - `metadata/store_registry.json`: Store registry mapping locations to File Search Store IDs.
- **Temporary files** (local, gitignored):
  - `.cache/upload_tracking.json`: Upload tracking cache (file hashes, modification times).
- **Automatic migration**: On first run after upgrade, local registry files are automatically uploaded to GCS and deleted locally.
- **In-memory caching**: Registries cached in memory during session lifetime for performance.
- **Fail-fast**: Application fails with clear error if GCS is unavailable (intentional design).

## Web Scraping (Scrapy)
- Scrapy-based web scraper in `scraper/` directory for downloading academic website content.
- **sapir.ac.il scraper**: Downloads HTML pages, PDFs, and images from Sapir Academic College website.
- Features:
  - Domain-restricted crawling (sapir.ac.il only)
  - Exponential backoff retry with randomization (0-3s max delay)
  - HTTP caching to avoid re-downloads
  - Hebrew UTF-8 text support
  - Polite crawling: obeys robots.txt, conservative concurrency (4 requests), delays
- Output: `data/sapir/html/`, `data/sapir/pdf/`, `data/sapir/images/`
- Usage: `python scraper/run_sapir_scraper.py [--clear-cache | --resume | --debug]`
- Tests: `pytest scraper/tests/`
- Documentation: See `scraper/README.md` for detailed usage and configuration
- Note: Scraped content is stored separately from tourism RAG data (data/locations/).

## Testing Policy (CRITICAL)
- Use pytest to run the full test suite.
- **100% of tests MUST pass when running the test suite.**
- **NEVER skip tests.** If a test is not relevant anymore, remove it entirely.
- **NEVER ignore failing tests** under the premise that they are unrelated to current changes.
- Retries are acceptable if tests are flaky, but persistent failures must be addressed.
- **When user asks for clean tests:**
  - ALL failures MUST be reported immediately.
  - Either fix the failure OR ask the user how to proceed.
  - Do NOT proceed with "tests pass except for X" - that means tests do NOT pass.
- Any failing test blocks all progress until resolved or user provides guidance.
