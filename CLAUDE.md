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
- config/: unified configuration directory.
  - prompts/: prompt YAMLs for the QA system (tourism_qa.yaml, topic_extraction.yaml).
  - locations/: location-specific configuration overrides (optional).
- config.yaml: app settings including GCS paths for registries (at project root).
- tests/: all test files organized by module (tests/, tests/gemini/).
- .cache/: temporary build artifacts (upload tracking, excluded from git).
- .streamlit/secrets.toml: API keys (never commit).

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

### Merge Behavior
- **Nested dicts**: Deep merge (child overrides parent, other fields preserved)
- **Lists**: Complete replacement (no smart merging)
- **Primitives**: Override value replaces base value
- **Missing override files**: Graceful fallback to parent level (no errors)

### API Usage
```python
# Load global config only
config = GeminiConfig.from_yaml()

# Load with area override
config = GeminiConfig.from_yaml(area="hefer_valley")

# Load with site override (inherits from area if exists, then global)
config = GeminiConfig.from_yaml(area="hefer_valley", site="agamon_hefer")

# Same pattern for prompts
prompt = PromptLoader.load("config/prompts/tourism_qa.yaml", area="hefer_valley", site="agamon_hefer")
```

### Common Use Cases
- Custom guide personas per site (primary use case): different personality/language per location
- Model selection per location: e.g. `model: "gemini-2.5-flash"` for complex sites
- Temperature tuning: cooler (0.4) for factual content, warmer (0.8) for cultural sites

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

## Image Support (Text-Only Mode)
- Automatically extracts images from DOCX files during upload.
- Image extraction: python-docx library extracts inline images with captions and context.
- **Storage**: Images stored in GCS bucket, uploaded to Gemini File API (for potential future use), tracked in GCS image registry.
- Image registry: JSON-based system mapping area/site/doc → image metadata (GCS URIs, File API URIs, captions, context).
- Sequential naming: image_001.jpg, image_002.jpg, etc. within each document.
- Hebrew support: Full UTF-8 support for captions and context text.
- **Text-only mode (since #77)**: LLM does NOT receive images directly (no multimodal context sent to API).
- **Caption-based relevance**: LLM scores images based ONLY on captions found in File Search documents.
- UI display: Images shown in expandable sections with captions and context (before/after text) via GCS signed URLs.
- Upload process: DOCX text → File Search Store → extract images → upload to GCS & File API → register metadata with captions.
- Query process: query images by area/site → LLM scores captions from File Search → caption-based matching → display relevant images in UI.
- Note: File Search API does NOT extract images from DOCX (text-only), hence separate image pipeline.
- **File API URIs**: Kept in registry for backward compatibility and potential future multimodal use, but NOT sent to LLM in current text-only mode.

### LLM-Based Image Relevance (Issue #18, #40, #77)
- **Status**: Fully implemented and active (text-only mode since #77)
- **Mode**: TEXT-ONLY - LLM scores images based on captions in File Search documents without seeing images directly
- **Note**: Gemini 2.5 doesn't support File Search tool + structured output simultaneously
- System prompt instructs model to return JSON with image relevance signals
- JSON response parsed manually from text (not using response_schema)
- Response fields:
  - `response_text`: Main response to user query (Hebrew or query language)
  - `should_include_images`: Boolean indicating if images should be shown (false for initial greetings, true for substantive queries)
  - `image_relevance`: List of `{caption, relevance_score}` objects with relevance scores (0-100)
- **Implementation flow (caption-based matching)**:
  1. LLM receives text-only user prompt (no image URIs, no multimodal context)
  2. LLM finds image captions in File Search documents and scores them by relevance
  3. JSON parsing extracts `should_include_images` and `image_relevance` from Gemini response
  4. If `should_include_images=false`, no images displayed (greeting/abstract question detection)
  5. If `should_include_images=true` and relevance data available, `filter_images_by_relevance()` matches captions and filters images with score >= 85 ([qa.py:112-186](backend/endpoints/qa.py#L112-L186))
  6. Caption matching uses normalization (strip whitespace, lowercase) for fuzzy matching
  7. Filtered images sorted by relevance score (descending)
  8. If no relevance data is available, no images are shown (no fallback to showing all images)
- Initial greeting detection: LLM detects greeting context and sets `should_include_images=false` (no hardcoded history checks)
- Image filtering: Only images with relevance score >= 85 are displayed (strict threshold)
- Commentary generation: System prompt guides LLM to add natural commentary when showing images
- Single API call: All logic (response generation, greeting detection, relevance scoring) handled in one Gemini API call

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

## Backend API (Serverless Architecture)

**Status**: Backend API deployed to Google Cloud Run (revision 00018). 44+ unit tests passing. Production-ready.

### Architecture
- **FastAPI** backend deployed on Google Cloud Run
- **REST API** for all operations (chat, topics, locations, uploads)
- **Stateless design**: All state in GCS (conversations, logs, registries)
- **Two-layer authentication**:
  1. **Cloud Run**: Deployed with `--allow-unauthenticated` (publicly accessible)
  2. **API keys**: Application-level auth via `Authorization: Bearer <key>` header
- **Single storage backend**: GCS for everything (no Firestore/BigQuery/Redis)

### API Endpoints

- `POST /qa`: Chat query with File Search RAG. Body: `{conversation_id?, area, site, query}`. Returns response, citations, images, latency.
- `GET /topics/{area}/{site}`: Topics for location.
- `GET /locations`: List all areas/sites.
- `GET /locations/{area}/{site}/content`: Location metadata.
- `POST /upload/{area}/{site}`: Placeholder (501 — use CLI uploader).
- `DELETE /conversations/{conversation_id}`: Delete specific conversation (admin, API key required).
- `DELETE /conversations?older_than_hours=N&prefix=X`: Bulk delete old conversations.
- `GET /_internal_probe_3f9a2c1b`: Cloud Run health check (no API key required).

### Backend Components

**Directory structure:**
```
backend/
├── main.py                    # FastAPI app with router registration
├── dependencies.py            # Singleton dependency injection
├── auth.py                    # API key authentication middleware
├── models.py                  # Pydantic request/response schemas
├── config.py                  # GeminiConfig with location overrides
├── prompt_loader.py           # Prompt loading with overrides
├── endpoints/                 # API endpoint modules
│   ├── qa.py                  # Chat endpoint with RAG
│   ├── topics.py              # Topics retrieval
│   ├── locations.py           # Location management
│   ├── upload.py              # Upload placeholder
│   └── conversations.py       # Conversation deletion endpoints (administrative)
├── conversation_storage/      # GCS conversation management
│   └── conversations.py       # ConversationStore class with expiration logic
├── query_logging/             # Query logging (renamed to avoid shadowing Python's logging)
│   └── query_logger.py        # QueryLogger (JSONL to GCS)
├── gcs_storage.py             # GCS storage backend
├── store_registry.py          # File Search Store registry
├── image_registry.py          # Image metadata registry
└── tests/                     # Unit tests (44+ tests, all passing)
```

**Storage in GCS:**
- `conversations/{conversation_id}.json`: Conversation history
- `query_logs/{YYYY-MM-DD}.jsonl`: Query analytics logs
- `metadata/store_registry.json`: Location → Store name mapping
- `metadata/image_registry.json`: Image metadata
- `topics/{area}/{site}/topics.json`: Pre-generated topics

### Conversation Expiration

**Automatic Expiration (3-Hour Timeout):**
- Messages older than 3 hours are automatically filtered from conversation history
- Expiration occurs at read-time when `ConversationStore.get_conversation()` is called (default behavior)
- Conversation files remain in GCS with full history intact (no automatic deletion)
- Configuration: `CONVERSATION_TIMEOUT_HOURS = 3` in `backend/conversation_storage/conversations.py`

**Behavior:**
1. When loading conversation, old messages are filtered out transparently (unless disabled)
2. User experiences seamless fresh-start after 3-hour timeout
3. No user notifications (silent filtering)
4. Full conversation history preserved in GCS for audit purposes
5. WhatsApp bot logs when all messages are expired: "Starting fresh conversation after expiration"

**Admin UI Viewing:**
- Admin UI uses `get_conversation(conversation_id, apply_expiration=False)` to view ALL messages
- This bypasses expiration filter for administrative viewing and debugging
- Allows admins to see complete conversation history regardless of age

**Manual Deletion (Administrative):**
- API endpoints available for administrative cleanup only
- `DELETE /conversations/{id}`: Delete specific conversation file
- `DELETE /conversations?older_than_hours=N`: Bulk delete old conversations
- Manual deletions permanently remove conversation files from GCS
- Require API key authentication


### Deployment

**Project Configuration:**
- **GCP Project**: `gen-lang-client-0860749390`
- **Region**: `me-west1` (Tel Aviv, Israel - closest to customers)
- **GCS Bucket**: `tarasa_tourist_bot_content`
- **Service Name**: `tourism-rag-backend`

**Deploy:**
```bash
cd backend && ./deploy.sh  # reads from .env (NEVER commit .env)
```

Env vars: `GOOGLE_API_KEY` (required). `GCS_BUCKET` defaults to hardcoded bucket in script; `BACKEND_API_KEYS` is auto-generated if not set.

**Post-deployment:** Use the service URL printed by `./deploy.sh` as `backend_api_url`. All API endpoints require `Authorization: Bearer <api-key>` header. Add `backend_api_url` and `backend_api_key` to `.streamlit/secrets.toml`.

**Local:** `python -m uvicorn backend.main:app --reload --port 8080`

### Configuration Overrides

Backend fully supports location-specific config/prompt overrides:
- Config loaded with: `GeminiConfig.from_yaml(area=area, site=site)`
- Prompts loaded with: `PromptLoader.load(..., area=area, site=site)`
- Verified working: agamon_hefer temperature (0.5) and custom דני persona

### Testing

```bash
pytest backend/tests/ -v
pytest backend/tests/test_qa_api_integration.py -v  # integration tests against deployed backend
```


## Logging and Monitoring

The backend uses two separate logging systems optimized for their respective purposes:

### Application Logs (Cloud Logging)

- Local: stdout + rotating `backend.log` (10MB, 5 backups). Cloud Run: stdout only (captured by Cloud Logging, 30-day retention).
- Log level: `LOG_LEVEL` env var (default: INFO). Set to DEBUG temporarily via `gcloud run services update tourism-rag-backend --region me-west1 --set-env-vars LOG_LEVEL=DEBUG`.
- Access: `gcloud run logs read tourism-rag-backend --region me-west1 --limit 50` or Cloud Console → Cloud Run → LOGS tab.

### Query/Response Logs (GCS)

- Storage: `gs://tarasa_tourist_bot_content/query_logs/{YYYY-MM-DD}.jsonl`
- Format: JSONL. Fields include: `timestamp`, `conversation_id`, `area`, `site`, `query`, `response_text`, `latency_ms`, `citations`, `images`, `image_relevance`, `should_include_images`, `error`.
- Access via `gsutil cp gs://tarasa_tourist_bot_content/query_logs/<date>.jsonl .` or `QueryLogger` in `backend/query_logging/query_logger.py`.
- Retention: indefinite (GCS bucket lifecycle policy).

### WhatsApp Bot Timing Logs (GCS)

- Storage: `gs://tarasa_tourist_bot_content/whatsapp_query_logs/{YYYY-MM-DD}.jsonl`
- Format: JSONL, extends backend query log schema with `timing_breakdown` dict of named millisecond timestamps covering the full webhook-to-completion pipeline.
- Delivery status events logged separately via `EventLogger` when WhatsApp status webhooks arrive.
