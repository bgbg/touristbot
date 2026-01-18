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
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`; set backend API credentials (`backend_api_key`, `backend_api_url_cloud`/`backend_api_url_local`), `GOOGLE_API_KEY` (for CLI tools), and GCS credentials.
- **GCS is mandatory**: Image and store registries are stored in GCS bucket (no local fallback).
- Adjust `config.yaml` for GCS paths, File Search Store name, chunking params, and model selection.
- First run: Automatic migration moves any local registry files to GCS.

## Running
- **Backend API** (local development): `python -m uvicorn backend.main:app --reload --port 8080` (see Backend API section for deployment)
- **Web UI**: `streamlit run gemini/main_qa.py` (defaults to http://localhost:8501, requires backend API running or deployed)
- **CLI upload**: `python gemini/main_upload.py [--area <area> --site <site> --force]` (uses direct Gemini API, not backend)

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

## Backend API (Serverless Architecture)

**Status**: Backend API implemented and tested (40 unit tests passing). Deployed on Cloud Run. **Streamlit frontend fully integrated** (issues #34 and #37 complete).

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

**Health:**
- `GET /health`: Health check for Cloud Run

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
│   └── upload.py              # Upload placeholder
├── conversation_storage/      # GCS conversation management
│   └── conversations.py       # ConversationStore class
├── logging/                   # Query logging
│   └── query_logger.py        # QueryLogger (JSONL to GCS)
├── gcs_storage.py             # GCS storage backend
├── store_registry.py          # File Search Store registry
├── image_registry.py          # Image metadata registry
└── tests/                     # Unit tests (40 tests, all passing)
```

**Storage in GCS:**
- `conversations/{conversation_id}.json`: Conversation history
- `query_logs/{YYYY-MM-DD}.jsonl`: Query analytics logs
- `metadata/store_registry.json`: Location → Store name mapping
- `metadata/image_registry.json`: Image metadata
- `topics/{area}/{site}/topics.json`: Pre-generated topics

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
./deploy.sh  # Uses defaults: gen-lang-client-0860749390, me-west1

# Or with custom project/region:
./deploy.sh <project-id> <region>
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
1. Copy the service URL from deployment output (e.g., `https://tourism-rag-backend-xxxxx.me-west1.run.app`)
2. Grant Streamlit service account access to invoke Cloud Run:
   ```bash
   gcloud run services add-iam-policy-binding tourism-rag-backend \
     --region=me-west1 \
     --member='serviceAccount:<streamlit-sa>@<project>.iam.gserviceaccount.com' \
     --role='roles/run.invoker'
   ```
   Or for local development, grant your own account:
   ```bash
   gcloud run services add-iam-policy-binding tourism-rag-backend \
     --region=me-west1 \
     --member='user:<your-email>@gmail.com' \
     --role='roles/run.invoker'
   ```
3. Configure `.streamlit/secrets.toml` with backend endpoints (see Streamlit Frontend Integration section below)
4. Verify deployment (requires GCP auth):
   ```bash
   curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
     https://<service-url>/health
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

### Streamlit Frontend Integration

**Status**: Fully integrated (issues #34 and #37 complete). The Streamlit UI (`gemini/main_qa.py`) now uses the backend REST API instead of direct Gemini API calls.

**Endpoint Selector Feature**:
The UI supports flexible backend configuration with an optional endpoint selector:

**Configuration Options** (in `.streamlit/secrets.toml`):

1. **Dual Endpoints** (Cloud + Local) - Shows selector:
   ```toml
   backend_api_key = "your-backend-api-key"
   backend_api_url_cloud = "https://tourism-rag-backend-xxxxx.me-west1.run.app"
   backend_api_url_local = "http://localhost:8080"
   ```
   - Endpoint selector appears in sidebar (🌐 Cloud Run / 💻 Local Development)
   - User can switch between endpoints during session
   - Conversation resets when switching (different backends = separate storage)
   - Default: Cloud Run

2. **Single Endpoint** (Cloud or Local) - No selector:
   ```toml
   backend_api_key = "your-backend-api-key"
   backend_api_url_cloud = "https://tourism-rag-backend-xxxxx.me-west1.run.app"
   ```
   OR
   ```toml
   backend_api_key = "your-backend-api-key"
   backend_api_url_local = "http://localhost:8080"
   ```
   - Auto-uses the configured endpoint
   - No selector shown (cleaner production UI)

3. **Legacy Format** (Backward Compatible):
   ```toml
   backend_api_key = "your-backend-api-key"
   backend_api_url = "https://tourism-rag-backend-xxxxx.me-west1.run.app"
   ```
   - Treats `backend_api_url` as cloud endpoint
   - No selector shown

**Development Workflow**:
- Configure both `backend_api_url_cloud` and `backend_api_url_local` for development
- Easily switch between testing Cloud Run deployment and local backend
- No need to edit secrets file or restart app to switch

**Production Deployment**:
- Only configure `backend_api_url_cloud` for security
- Do NOT expose local development endpoints in production secrets

**UI Features**:
- Active endpoint displayed in sidebar (e.g., "Active: `https://...`")
- Clear error messages for unreachable backends or auth failures
- Conversation history managed by backend (via `conversation_id`)
- Citations and images use backend response format (`source`/`text`, `uri`/`file_api_uri`)
- Full feature parity with previous direct Gemini API integration

**Running the UI**:
```bash
streamlit run gemini/main_qa.py
```

**Troubleshooting**:
- **"Missing backend_api_key"**: Add `backend_api_key` to `.streamlit/secrets.toml`
- **"No backend endpoints configured"**: Add at least one of `backend_api_url_cloud`, `backend_api_url_local`, or `backend_api_url`
- **"Cannot connect to backend"**:
  - For Cloud Run: Verify deployment, check GCP IAM permissions
  - For local: Ensure backend is running (`python -m uvicorn backend.main:app --port 8080`)
  - Check API key is correct
- **401 Unauthorized**: API key doesn't match backend's `BACKEND_API_KEYS` environment variable
- **Conversation resets unexpectedly**: Normal when switching endpoints (separate storage)

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
# Total: 40 tests, all passing
```

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
