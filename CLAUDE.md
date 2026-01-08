# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo.

## Overview
- Tourism RAG system using Google Gemini File Search.
- Streamlit UI for Q&A and content management; CLI uploader for batch loads.
- Content organized by area/site under data/locations with generated chunks in data/chunks.

## Setup
- Python 3.11+; create `.venv` and install with `pip install -r requirements.txt`.
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`; set `GOOGLE_API_KEY` (and optional `TAVILY_API_KEY`).
- Adjust `config.yaml` for paths, chunking, and model selection.

## Running
- Web app: `streamlit run gemini/main_qa.py` (defaults to http://localhost:8501).
- CLI upload: `python gemini/main_upload.py [--area <area> --site <site> --force]`.

## Project Layout
- gemini/: core logic for chunking, uploads, QA flow, registry, logging.
- data/locations/: source content organized by area/site hierarchy.
- data/chunks/: generated chunks; rebuilt by upload tasks.
- prompts/: prompt YAMLs for the QA system.
- config.yaml: app settings; requirements.txt: dependencies.
- .streamlit/secrets.toml: API keys (never commit).

## Testing
- Use pytest.
- Do not skip tests. Retries are acceptable; skips are not.
- Any failing test blocks progress—either fix or ask the user how to proceed.
