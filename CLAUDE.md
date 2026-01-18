# CLAUDE.md

Guidance for Claude Code when working in this repo.

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

## Development Policy
- **NEVER commit .env files** - secrets must stay in `.streamlit/secrets.toml` or `.env` (both gitignored).
- **GCS is mandatory** - All registries stored in Google Cloud Storage (no local fallback).
- **Config overrides** - Use hierarchical config system: `config/locations/<area>.yaml` or `config/locations/<area>/<site>.yaml`.
- **Prompt overrides** - Use `config/locations/<area>/<site>/prompts/<prompt_name>.yaml` for location-specific personas.
- **Deep merge** - Config overrides merge deeply; only specify fields to change.

## Overview
- Tourism RAG system using Google Gemini File Search API with metadata filtering.
- Multimodal support: Extracts images from DOCX, uploads to GCS + Gemini File API, displays with LLM-based relevance.
- FastAPI backend on Cloud Run (production: `https://tourism-rag-backend-347968285860.me-west1.run.app`).
- Streamlit UI for Q&A; CLI uploader for batch loads.
- Content organized by area/site under `data/locations/`.

## Setup
- Python 3.11+; conda environment: `tarasa`.
- Install: `conda activate tarasa && pip install -r requirements.txt`
- Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`; set `GOOGLE_API_KEY`, `backend_api_url`, `backend_api_key`.
- Adjust `config.yaml` for GCS paths and File Search Store name.

## Running
- Web app: `streamlit run gemini/main_qa.py` (http://localhost:8501)
- CLI upload: `python gemini/main_upload.py --area <area> --site <site> [--force]`
- Backend local: `python -m uvicorn backend.main:app --reload --port 8080`
- Tests: `pytest` (backend: `pytest backend/tests/`)

## Project Layout
```
gemini/                      # Core logic: File Search, QA, registries, images, topics
backend/                     # FastAPI backend (Cloud Run)
  endpoints/qa.py            # Chat endpoint with RAG + image relevance
  dependencies.py            # Singleton dependency injection
  conversation_storage/      # GCS conversation management
  query_logging/             # Query analytics (JSONL to GCS)
data/locations/              # Source content (area/site hierarchy)
config/                      # Config + prompts (with location overrides)
  prompts/                   # Global prompts (tourism_qa.yaml, topic_extraction.yaml)
  locations/                 # Location-specific overrides
tests/                       # All test files
.streamlit/secrets.toml      # API keys (NEVER commit)
config.yaml                  # App settings (GCS paths, model, chunking)
```

## Key Architecture Decisions
- **Server-side chunking**: Gemini handles chunking (400 tokens/chunk, 15% overlap).
- **Metadata filtering**: Queries use `area="..." AND site="..."` (AIP-160 syntax).
- **Image relevance**: LLM returns JSON with relevance scores; only images ≥60 displayed.
- **Stateless backend**: All state in GCS (conversations, logs, registries).
- **Two-layer auth**: Cloud Run requires GCP IAM + API keys (`Authorization: Bearer <key>`).

## Backend Deployment
```bash
cd backend
./deploy.sh  # Uses .env for secrets (gen-lang-client-0860749390, me-west1)
```

**Environment variables (Cloud Run):**
- `BACKEND_API_KEYS`: Comma-separated API keys
- `GCS_BUCKET`: `tarasa_tourist_bot_content`
- `GOOGLE_API_KEY`: Gemini API key

**Test deployment:**
```bash
curl -H "Authorization: Bearer <api-key>" \
  https://tourism-rag-backend-347968285860.me-west1.run.app/locations
```

## Critical Fixes (Backend Revision 00018)
1. **Metadata filter mismatch**: Changed filter to `area="..." AND site="..."` ([qa.py:261](backend/endpoints/qa.py#L261))
2. **Role validation**: Convert "assistant" → "model" for Gemini API ([qa.py:237](backend/endpoints/qa.py#L237))
3. **Module shadowing**: Renamed `backend/logging/` → `backend/query_logging/`
4. **Schema validation**: Custom GeminiJsonSchema removes `additionalProperties` ([models.py:11](backend/models.py#L11))
5. **Structured output**: Parse JSON manually (Gemini 2.5 doesn't support File Search + response_schema together)

## Common Operations
- **Add location**: Create `data/locations/<area>/<site>/`, upload with CLI, optionally add config/prompt overrides.
- **Custom persona**: Create `config/locations/<area>/<site>/prompts/tourism_qa.yaml` with `system_prompt` override.
- **Regenerate topics**: `python gemini/generate_topics.py --area <area> --site <site>`
- **Force re-upload**: `python gemini/main_upload.py --area <area> --site <site> --force`

## API Endpoints
- `POST /qa`: Chat queries (request: `{conversation_id?, area, site, query}`)
- `GET /topics/{area}/{site}`: Retrieve topics
- `GET /locations`: List all areas/sites
- `GET /locations/{area}/{site}/content`: Location metadata
