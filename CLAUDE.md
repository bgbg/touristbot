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

# model_name and user_prompt inherited from global config/prompts/tourism_qa.yaml
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
prompt = PromptLoader.load("config/prompts/tourism_qa.yaml", area="hefer_valley", site="agamon_hefer")
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

### LLM-Based Image Relevance (Issue #18, #40)
- **Status**: Fully implemented and active
- **Note**: Gemini 2.5 doesn't support File Search tool + structured output simultaneously
- System prompt instructs model to return JSON with image relevance signals
- JSON response parsed manually from text (not using response_schema)
- Response fields:
  - `response_text`: Main response to user query (Hebrew or query language)
  - `should_include_images`: Boolean indicating if images should be shown (false for initial greetings, true for substantive queries)
  - `image_relevance`: List of `{image_uri, relevance_score}` objects with relevance scores (0-100)
- **Implementation flow**:
  1. JSON parsing extracts `should_include_images` and `image_relevance` from Gemini response ([qa.py:294-308](backend/endpoints/qa.py#L294-L308))
  2. If `should_include_images=false`, no images displayed (greeting/abstract question detection)
  3. If `should_include_images=true` and relevance data available, `filter_images_by_relevance()` filters images with score >= 60 ([qa.py:109-174](backend/endpoints/qa.py#L109-L174))
  4. Filtered images sorted by relevance score (descending)
  5. Fallback: if no relevance data, shows all images (backward compatibility)
- Initial greeting detection: LLM detects greeting context and sets `should_include_images=false` (no hardcoded history checks)
- Image filtering: Only images with relevance score >= 60 are displayed
- Commentary generation: System prompt guides LLM to add natural commentary when showing images (e.g., "שימו לב כמה יפים השקנאים האלה!")
- Single API call: All logic (response generation, greeting detection, relevance scoring) handled in one Gemini API call
- Comprehensive logging: tracks JSON parsing, image filtering, and relevance scores for debugging

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
  1. **GCP IAM**: Cloud Run requires GCP authentication (not publicly accessible)
  2. **API keys**: Application-level auth via `Authorization: Bearer <key>` header
- **Single storage backend**: GCS for everything (no Firestore/BigQuery/Redis)

### API Endpoints

**Chat & Query:**
- `POST /qa`: Chat queries with File Search RAG pipeline
  - Request: `{conversation_id?, area, site, query}`
  - Response: `{conversation_id, response_text, citations[], images[], latency_ms}`
  - Features: Conversation history, structured output, image relevance, Hebrew support

**Content Management:**
- `GET /topics/{area}/{site}`: Retrieve topics for location
- `GET /locations`: List all areas and sites
- `GET /locations/{area}/{site}/content`: Location metadata (store name, topics count)

**Uploads** (MVP uses CLI):
- `POST /upload/{area}/{site}`: Placeholder (returns 501 - use CLI uploader instead)

**Conversations** (Administrative):
- `DELETE /conversations/{conversation_id}`: Delete specific conversation
  - Requires API key authentication
  - Returns: `{status, conversation_id, message}`
  - Returns 404 if conversation not found
- `DELETE /conversations?older_than_hours=N&prefix=X`: Bulk delete old conversations
  - `older_than_hours`: Delete conversations where ALL messages are older than N hours (default: 3)
  - `prefix`: Optional filter (e.g., `whatsapp_` for WhatsApp conversations only)
  - Returns: `{status, count, older_than_hours, prefix, message}`
  - Example: `DELETE /conversations?older_than_hours=24&prefix=whatsapp_`

**Health:**
- `GET /_internal_probe_3f9a2c1b`: Internal health check for Cloud Run (obscured path for security)

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
- Expiration occurs at read-time when `ConversationStore.get_conversation()` is called
- Conversation files remain in GCS with full history intact (no automatic deletion)
- Configuration: `CONVERSATION_TIMEOUT_HOURS = 3` in `backend/conversation_storage/conversations.py`

**Behavior:**
1. When loading conversation, old messages are filtered out transparently
2. User experiences seamless fresh-start after 3-hour timeout
3. No user notifications (silent filtering)
4. Full conversation history preserved in GCS for audit purposes
5. WhatsApp bot logs when all messages are expired: "Starting fresh conversation after expiration"

**Manual Deletion (Administrative):**
- API endpoints available for administrative cleanup only
- `DELETE /conversations/{id}`: Delete specific conversation file
- `DELETE /conversations?older_than_hours=N`: Bulk delete old conversations
- Manual deletions permanently remove conversation files from GCS
- Require API key authentication

**Key Design Principles:**
- **On-demand filtering**: No background jobs or cron tasks needed
- **Zero data loss**: Expiration only affects what's returned, not what's stored
- **Serverless-friendly**: Lazy evaluation minimizes performance impact
- **Backward compatible**: Gracefully handles messages without timestamps

### Deployment

**Project Configuration:**
- **GCP Project**: `gen-lang-client-0860749390`
- **Region**: `me-west1` (Tel Aviv, Israel - closest to customers)
- **GCS Bucket**: `tarasa_tourist_bot_content`
- **Service Name**: `tourism-rag-backend`

**Prerequisites:**
- GCP project with Cloud Run and GCS enabled
- GCS bucket created (`tarasa_tourist_bot_content`)
- Google API key for Gemini API
- Authenticated gcloud CLI: `gcloud auth login`

**Environment Variables (Cloud Run):**
```bash
BACKEND_API_KEYS=key1,key2,key3   # Comma-separated API keys (create secure keys)
GCS_BUCKET=tarasa_tourist_bot_content  # GCS bucket for storage
GOOGLE_API_KEY=your-google-key     # Gemini API key (from .streamlit/secrets.toml)
```

**Deploy to Cloud Run:**
```bash
cd backend
./deploy.sh  # Uses defaults from .env: gen-lang-client-0860749390, me-west1

# Deployment reads secrets from .env file (NEVER commit .env to git)
# Creates .env.yaml temporarily for Cloud Run environment variables
# Deploys with --no-allow-unauthenticated (requires GCP auth + API key)
```

**Manual deployment:**
```bash
# Build image
gcloud builds submit --tag gcr.io/gen-lang-client-0860749390/tourism-rag-backend \
  --project gen-lang-client-0860749390

# Deploy to Cloud Run
gcloud run deploy tourism-rag-backend \
  --image gcr.io/gen-lang-client-0860749390/tourism-rag-backend \
  --region me-west1 \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 10 \
  --project gen-lang-client-0860749390 \
  --set-env-vars GCS_BUCKET=tarasa_tourist_bot_content,GOOGLE_API_KEY=<key>,BACKEND_API_KEYS=<keys>
```

**Post-deployment:**
1. Service URL: `https://tourism-rag-backend-347968285860.me-west1.run.app` (deployed revision 00018)
2. **Authentication**: Service uses `--no-allow-unauthenticated` requiring both GCP IAM and API keys
   - API endpoints require `Authorization: Bearer <api-key>` header
   - Health probe (`/_internal_probe_3f9a2c1b`) is unauthenticated for Cloud Run monitoring
3. Add to `.streamlit/secrets.toml`:
   ```toml
   backend_api_url = "https://tourism-rag-backend-347968285860.me-west1.run.app"
   backend_api_key = "<one-of-your-BACKEND_API_KEYS>"
   ```
4. Test deployment:
   ```bash
   curl -H "Authorization: Bearer <api-key>" \
     https://tourism-rag-backend-347968285860.me-west1.run.app/locations
   ```

**Local Testing:**
```bash
# Set environment variables
export BACKEND_API_KEYS="test-key-123"
export GCS_BUCKET="your-bucket"
export GOOGLE_API_KEY="your-key"

# Run with uvicorn
python -m uvicorn backend.main:app --reload --port 8080

# Test endpoint
curl -H "Authorization: Bearer test-key-123" \
  http://localhost:8080/locations
```

### Configuration Overrides

Backend fully supports location-specific config/prompt overrides:
- Config loaded with: `GeminiConfig.from_yaml(area=area, site=site)`
- Prompts loaded with: `PromptLoader.load(..., area=area, site=site)`
- Verified working: agamon_hefer temperature (0.5) and custom דני persona

### Testing

Run backend tests:
```bash
pytest backend/tests/ -v
# 11 tests: auth
# 17 tests: conversation storage
# 12 tests: query logger
# 4 tests: QA endpoint (schema validation, API integration)
# Total: 44+ tests, all passing

# Integration tests against deployed backend:
pytest tests/test_qa_api_integration.py -v
```

### Known Issues & Fixes

**Critical fixes applied (revision 00018):**
1. **Metadata filter mismatch** (Issue: File Search returning no results)
   - Problem: Upload adds `area` and `site` metadata, query used `location="area/site"`
   - Fix: Changed filter to `area="..." AND site="..."` in [backend/endpoints/qa.py:261](backend/endpoints/qa.py#L261)

2. **Role validation error** (Issue: "Please use a valid role: user, model")
   - Problem: Conversation store uses "assistant" role, Gemini API requires "model"
   - Fix: Convert "assistant" → "model" when building history in [backend/endpoints/qa.py:237](backend/endpoints/qa.py#L237)

3. **Module shadowing** (Issue: `logging.getLogger` not found)
   - Problem: `backend/logging/` directory shadowed Python's built-in logging module
   - Fix: Renamed to `backend/query_logging/`

4. **Schema validation** (Issue: "additionalProperties is not supported")
   - Problem: Pydantic v2 generates schemas with additionalProperties
   - Fix: Custom GeminiJsonSchema generator removes additionalProperties in [backend/models.py:11](backend/models.py#L11)

5. **Structured output compatibility** (Issue: Tools + structured output conflict)
   - Problem: Gemini 2.5 doesn't support File Search tool + response_schema together
   - Fix: Removed structured output, parse JSON from text response manually
   - System prompt instructs model to return JSON format

6. **LRU cache staleness** (Issue: Registry changes not reflected)
   - Problem: Singleton dependencies cached, new locations not appearing
   - Fix: Force Cloud Run restart with cache-busting env var or new deployment

### Limitations & Future Work

**Current MVP approach:**
- Uploads via CLI tool (`gemini/main_upload.py`) - no API upload endpoint implemented
- No rate limiting (rely on API key control + Gemini API limits)
- No caching layer (direct GCS reads)
- Synchronous processing (60min Cloud Run timeout sufficient)

**Future enhancements** (if needed):
- Implement full `/upload` endpoint with DOCX processing
- Add Streamlit frontend API client
- Add rate limiting (per API key)
- Add caching (Redis) if performance becomes an issue
- Async job processing (Cloud Tasks) for long uploads
- Monitoring dashboards (Cloud Monitoring)

## Logging and Monitoring

The backend uses two separate logging systems optimized for their respective purposes:

### Application Logs (Cloud Logging)

**Purpose**: Real-time application monitoring, debugging, error tracking

**Local development**:
- Logs written to both stdout and `backend.log` file (rotating, 10MB max, 5 backups)
- File location: project root directory
- Immediate access for debugging

**Cloud Run production**:
- Logs written to stdout only (automatically captured by Cloud Logging)
- No file-based logging (ephemeral filesystem)
- 30-day retention by default

**Log level**:
- Configurable via `LOG_LEVEL` environment variable (default: INFO)
- Supported levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

**Accessing production logs**:

Via gcloud CLI:
```bash
# Recent logs (last 50 entries)
gcloud run logs read tourism-rag-backend --region me-west1 --limit 50

# Follow logs in real-time
gcloud run logs tail tourism-rag-backend --region me-west1

# Filter by severity
gcloud run logs read tourism-rag-backend --region me-west1 --log-filter="severity>=ERROR"

# Specific time range
gcloud run logs read tourism-rag-backend --region me-west1 \
  --log-filter="timestamp>=\"2024-01-01T00:00:00Z\""
```

Via Cloud Console:
1. Navigate to Cloud Run: https://console.cloud.google.com/run
2. Select service: `tourism-rag-backend`
3. Click "LOGS" tab
4. Use filters: severity, time range, search text

**Log retention**: 30 days in Cloud Logging (default)

### Query/Response Logs (GCS)

**Purpose**: Long-term analytics, quality monitoring, training data

**Storage location**: `gs://tarasa_tourist_bot_content/query_logs/{YYYY-MM-DD}.jsonl`

**Format**: JSONL (one JSON object per line, newline-delimited)

**Schema**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "conversation_id": "uuid-string",
  "area": "hefer_valley",
  "site": "agamon_hefer",
  "query": "שאלה של המשתמש",
  "response_text": "תשובת הבוט",
  "response_length": 150,
  "latency_ms": 1234.56,
  "citations_count": 3,
  "images_count": 2,
  "model_name": "gemini-2.5-flash",
  "temperature": 0.6,
  "error": null,
  "should_include_images": true,
  "image_relevance": [
    {
      "image_uri": "https://generativelanguage.googleapis.com/...",
      "relevance_score": 85
    }
  ],
  "citations": [
    {
      "source": "document-name.docx",
      "chunk_id": "chunk-123",
      "text": "קטע מהמסמך המקורי"
    }
  ],
  "images": [
    {
      "uri": "https://storage.googleapis.com/...",
      "file_api_uri": "https://generativelanguage.googleapis.com/...",
      "caption": "תיאור התמונה",
      "context": "הקשר מהמסמך",
      "relevance_score": 85
    }
  ]
}
```

**Field descriptions**:
- `timestamp`: UTC timestamp in ISO 8601 format
- `conversation_id`: Unique conversation identifier
- `area`, `site`: Location hierarchy
- `query`: Full user question text
- `response_text`: Full bot response text (extracted from JSON if structured output)
- `response_length`: Character count of response
- `latency_ms`: Total query processing time in milliseconds
- `citations_count`: Number of citations (legacy field)
- `images_count`: Number of images displayed (legacy field)
- `model_name`: Gemini model used
- `temperature`: Temperature parameter
- `error`: Error message if query failed (null on success)
- `should_include_images`: Boolean flag from LLM structured output
- `image_relevance`: Raw relevance scores from LLM for all candidate images
- `citations`: Full citation objects with source documents and text snippets
- `images`: Full metadata for displayed images (after relevance filtering)

**Accessing query logs**:

Via gsutil CLI:
```bash
# Download specific date
gsutil cp gs://tarasa_tourist_bot_content/query_logs/2024-01-15.jsonl .

# Download date range
gsutil -m cp gs://tarasa_tourist_bot_content/query_logs/2024-01-*.jsonl .

# View recent logs
gsutil cat gs://tarasa_tourist_bot_content/query_logs/2024-01-15.jsonl | tail -n 10
```

Via Python (programmatic access):
```python
from backend.query_logging.query_logger import QueryLogger
from backend.gcs_storage import StorageBackend

storage = StorageBackend("tarasa_tourist_bot_content")
logger = QueryLogger(storage)

# Get logs for specific date
logs = logger.get_logs("2024-01-15")

# Get logs for date range
logs = logger.get_logs_range("2024-01-01", "2024-01-31")
```

**Log retention**: Indefinite (controlled by GCS bucket lifecycle policy)

### Searching and Filtering Best Practices

**Application logs (Cloud Logging)**:
- Use severity filters to focus on errors: `severity>=ERROR`
- Filter by log name: `logName=~"tourism-rag-backend"`
- Search text in messages: `textPayload=~"query failed"`
- Combine filters: `severity>=ERROR AND textPayload=~"GCS"`

**Query logs (GCS)**:
- Use `jq` for JSON parsing: `cat logs.jsonl | jq 'select(.latency_ms > 5000)'`
- Filter by location: `jq 'select(.area == "hefer_valley")'`
- Aggregate statistics: `jq -s 'map(.latency_ms) | add/length'` (average latency)
- Count errors: `jq -s 'map(select(.error != null)) | length'`
- Extract specific fields: `jq '{query, response_text, latency_ms}'`

**Monitoring key metrics**:
- **Latency**: Track `latency_ms` for performance issues (>5s is slow)
- **Error rate**: Count queries with non-null `error` field
- **Image inclusion**: Analyze `should_include_images` distribution
- **Citation usage**: Track `citations_count` to verify retrieval quality
- **Model performance**: Compare metrics across different `model_name` values

### Environment Detection

The backend automatically detects its environment:
- **Cloud Run**: Detected via `K_SERVICE` environment variable (set by GCP)
- **Local**: No `K_SERVICE` variable present

Logging configuration adapts accordingly:
- Cloud Run: stdout only (no file handler)
- Local: dual logging (stdout + rotating file)

### Temporary Debugging in Production

To enable DEBUG logging temporarily in Cloud Run:

```bash
# Update environment variable
gcloud run services update tourism-rag-backend \
  --region me-west1 \
  --set-env-vars LOG_LEVEL=DEBUG

# Revert to INFO after debugging
gcloud run services update tourism-rag-backend \
  --region me-west1 \
  --set-env-vars LOG_LEVEL=INFO
```

**Warning**: DEBUG logging is verbose and increases Cloud Logging costs. Use sparingly in production.
