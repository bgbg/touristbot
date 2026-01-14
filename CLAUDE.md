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
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`; set `GOOGLE_API_KEY` (and optional `TAVILY_API_KEY`).
- Adjust `config.yaml` for paths, File Search Store name, chunking params, and model selection.

## Running
- Web app: `streamlit run gemini/main_qa.py` (defaults to http://localhost:8501).
- CLI upload: `python gemini/main_upload.py [--area <area> --site <site> --force]`.

## Project Layout
- gemini/: core logic for File Search uploads, QA flow, registry, logging, topic extraction, image handling.
  - file_search_store.py: File Search Store management (create, upload with metadata).
  - main_qa.py: Streamlit UI with citation and image display.
  - main_upload.py: CLI uploader (whole files with metadata, no chunking, automatic image extraction).
  - store_registry.py: Maps locations to File Search Store name.
  - image_extractor.py: Extracts images and metadata from DOCX files.
  - image_storage.py: Uploads images to GCS bucket.
  - file_api_manager.py: Uploads images to Gemini File API for multimodal context.
  - image_registry.py: JSON-based registry mapping images to metadata (area/site/doc).
- data/locations/: source content organized by area/site hierarchy.
- topics/: generated topic lists stored in GCS at `topics/<area>/<site>/topics.json`.
- prompts/: prompt YAMLs for the QA system (tourism_qa.yaml, topic_extraction.yaml).
- config.yaml: app settings including file_search_store_name, image_registry_path.
- image_registry.json: image metadata registry (area/site/doc → image URIs and captions).
- .streamlit/secrets.toml: API keys (never commit).

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
- Triple storage: Images stored in GCS bucket, uploaded to Gemini File API, tracked in image_registry.json.
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
