# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo.

## Overview
- Tourism RAG system using Google Gemini File Search API with metadata filtering.
- Streamlit UI for Q&A and content management; CLI uploader for batch loads.
- Content organized by area/site under data/locations/.
- Server-side chunking: Gemini handles all chunking automatically (no local chunks).
- Citations: Automatic source attribution via grounding metadata.

## Setup
- Python 3.11+; create `.venv` and install with `pip install -r requirements.txt`.
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`; set `GOOGLE_API_KEY` (and optional `TAVILY_API_KEY`).
- Adjust `config.yaml` for paths, File Search Store name, chunking params, and model selection.

## Running
- Web app: `streamlit run gemini/main_qa.py` (defaults to http://localhost:8501).
- CLI upload: `python gemini/main_upload.py [--area <area> --site <site> --force]`.

## Project Layout
- gemini/: core logic for File Search uploads, QA flow, registry, logging, topic extraction.
  - file_search_store.py: File Search Store management (create, upload with metadata).
  - main_qa.py: Streamlit UI with citation display.
  - main_upload.py: CLI uploader (whole files with metadata, no chunking).
  - store_registry.py: Maps locations to File Search Store name.
- data/locations/: source content organized by area/site hierarchy.
- topics/: generated topic lists stored in GCS at `topics/<area>/<site>/topics.json`.
- prompts/: prompt YAMLs for the QA system (tourism_qa.yaml, topic_extraction.yaml).
- config.yaml: app settings including file_search_store_name.
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

## Testing
- Use pytest.
- Do not skip tests. Retries are acceptable; skips are not.
- Any failing test blocks progress—either fix or ask the user how to proceed.
