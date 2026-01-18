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
LOG_LEVEL=INFO  # Optional: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
```

**Logging configuration:**
- **Cloud Run**: Logs to stdout only (captured by Cloud Logging), no file handler
- **Local**: Logs to stdout + `backend.log` file (rotating, 10MB max, 5 backups)
- **LOG_LEVEL**: Controls verbosity (default: INFO)
  - Use DEBUG temporarily for troubleshooting
  - WARNING: DEBUG logging is verbose and increases Cloud Logging costs in production

### Post-Deployment
1. Copy service URL from deployment output
2. Update `.streamlit/secrets.toml`:
   ```toml
   backend_api_url = "https://tourism-rag-backend-xxxxx.me-west1.run.app"
   backend_api_key = "one-of-your-BACKEND_API_KEYS"
   ```
3. Test: `curl https://<service-url>/_internal_probe_3f9a2c1b`

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

## Logging and Monitoring

### Viewing Production Logs

**Cloud Logging (Application Logs):**
```bash
# Recent logs
gcloud run logs read tourism-rag-backend --region me-west1 --limit 50

# Follow logs in real-time
gcloud run logs tail tourism-rag-backend --region me-west1

# Filter by severity
gcloud run logs read tourism-rag-backend --region me-west1 --log-filter="severity>=ERROR"
```

**Query Logs (GCS):**
Query/response logs are stored in GCS at `query_logs/{YYYY-MM-DD}.jsonl`:
```bash
# Download today's logs
gsutil cp gs://tarasa_tourist_bot_content/query_logs/$(date +%Y-%m-%d).jsonl .

# View recent entries
gsutil cat gs://tarasa_tourist_bot_content/query_logs/$(date +%Y-%m-%d).jsonl | tail -n 10
```

See `CLAUDE.md` "Logging and Monitoring" section for complete documentation.

### Temporary DEBUG Logging

To enable DEBUG logging in production (use sparingly):
```bash
# Enable DEBUG
gcloud run services update tourism-rag-backend \
  --region me-west1 \
  --set-env-vars LOG_LEVEL=DEBUG

# Revert to INFO
gcloud run services update tourism-rag-backend \
  --region me-west1 \
  --set-env-vars LOG_LEVEL=INFO
```

## Troubleshooting

**Import errors:** Make sure you're in the project root and `backend/` is in PYTHONPATH

**Authentication fails:** Check `BACKEND_API_KEYS` is set correctly (comma-separated, no spaces)

**GCS errors:** Verify bucket exists and service account has read/write permissions

**Gemini API errors:** Check `GOOGLE_API_KEY` is valid and has File Search API enabled

**No logs appearing:** Check Cloud Run service logs for startup errors, verify K_SERVICE env var is set in Cloud Run

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
