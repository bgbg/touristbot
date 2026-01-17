# Backend API - Tourism RAG System

FastAPI backend for tourism Q&A system with Gemini File Search RAG, deployed on Google Cloud Run.

## Deployment

### Quick Start
```bash
# From project root
cd backend
./deploy.sh  # Uses defaults: gen-lang-client-0860749390, me-west1 (Tel Aviv)
```

### Project Configuration
- **GCP Project**: `gen-lang-client-0860749390`
- **Region**: `me-west1` (Tel Aviv, Israel)
- **GCS Bucket**: `tarasa_tourist_bot_content`
- **Service**: `tourism-rag-backend`

### Prerequisites
1. Authenticate with GCP: `gcloud auth login`
2. Verify project: `gcloud config get-value project`
3. Ensure GCS bucket exists: `gsutil ls gs://tarasa_tourist_bot_content`

### Environment Variables
Set in Cloud Run console or via CLI:
```bash
BACKEND_API_KEYS=key1,key2,key3  # Comma-separated API keys (create secure keys)
GCS_BUCKET=tarasa_tourist_bot_content
GOOGLE_API_KEY=<your-gemini-api-key>  # Same as in .streamlit/secrets.toml
```

### Post-Deployment
1. Copy service URL from deployment output
2. Update `.streamlit/secrets.toml`:
   ```toml
   backend_api_url = "https://tourism-rag-backend-xxxxx.me-west1.run.app"
   backend_api_key = "one-of-your-BACKEND_API_KEYS"
   ```
3. Test: `curl https://<service-url>/health`

## Development

### Adding New Endpoints

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
