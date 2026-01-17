# Backend Development Guide

## Adding New Endpoints

1. Create endpoint file in `backend/endpoints/`
2. Define router with `APIRouter(prefix="/path", tags=["tag"])`
3. Add endpoints with Pydantic models
4. Register router in `main.py`: `app.include_router(module.router)`
5. Add tests in `backend/tests/`

### Code Style

- Use type hints
- Document with docstrings
- Follow FastAPI conventions
- Keep endpoints stateless
- Use dependency injection

## Troubleshooting

**Import errors:** Make sure you're in the project root and `backend/` is in PYTHONPATH

**Authentication fails:** Check `BACKEND_API_KEYS` is set correctly (comma-separated, no spaces)

**GCS errors:** Verify bucket exists and service account has read/write permissions

**Gemini API errors:** Check `GOOGLE_API_KEY` is valid and has File Search API enabled

## MVP Scope

**Implemented:**
- All core API endpoints
- Authentication and logging
- Conversation management
- File Search RAG with citations
- Image relevance filtering
- Hebrew support
- Unit tests

**Future Enhancements** (out of MVP scope):
- Full `/upload` endpoint (currently uses CLI uploader)
- Rate limiting per API key
- Caching layer (Redis)
- Async job processing (Cloud Tasks)
- Frontend API client (Streamlit)
- CI/CD pipeline

See main `CLAUDE.md` for full documentation.
