"""
FastAPI backend for Tourism RAG system.

Provides REST API endpoints for:
- Chat queries with File Search and multimodal images
- Topic retrieval
- Location management
- Content uploads

Authentication via API key in Authorization header.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth import ApiKeyDep
from backend.endpoints import locations, qa, topics, upload

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    logger.info("Starting Tourism RAG Backend")

    # Load environment variables
    api_keys = os.getenv("BACKEND_API_KEYS", "")
    if not api_keys:
        logger.warning("BACKEND_API_KEYS not set - authentication will reject all requests")

    gcs_bucket = os.getenv("GCS_BUCKET", "")
    if not gcs_bucket:
        logger.error("GCS_BUCKET not set - backend will not function correctly")

    google_api_key = os.getenv("GOOGLE_API_KEY", "")
    if not google_api_key:
        logger.error("GOOGLE_API_KEY not set - Gemini API calls will fail")

    logger.info(f"Backend initialized with GCS bucket: {gcs_bucket}")

    yield

    logger.info("Shutting down Tourism RAG Backend")


# Create FastAPI app with disabled default docs (we'll add protected versions)
app = FastAPI(
    title="Tourism RAG Backend",
    description="Serverless backend for tourism Q&A system using Google Gemini File Search API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # Disable default /docs
    redoc_url=None,  # Disable default /redoc
    openapi_url=None,  # Disable default /openapi.json
)

# Add CORS middleware (allow all origins for MVP)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify Streamlit URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoint routers
app.include_router(qa.router)
app.include_router(topics.router)
app.include_router(locations.router)
app.include_router(upload.router)


@app.get("/_internal_probe_3f9a2c1b")
async def health_check():
    """
    Internal health check endpoint for Cloud Run monitoring.
    Obscured path to reduce exposure.
    """
    return {
        "status": "healthy",
        "service": "tourism-rag-backend",
        "version": "1.0.0",
    }


@app.get("/")
async def root(api_key: ApiKeyDep):
    """Root endpoint with API information (requires authentication)."""
    return {
        "service": "Tourism RAG Backend",
        "version": "1.0.0",
        "endpoints": {
            "qa": "/qa",
            "topics": "/topics/{area}/{site}",
            "locations": "/locations",
            "upload": "/upload/{area}/{site}",
        },
        "documentation": "/docs",
    }


@app.get("/docs", include_in_schema=False)
async def get_documentation(api_key: ApiKeyDep):
    """Protected API documentation (requires authentication)."""
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - API Documentation",
    )


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_schema(api_key: ApiKeyDep):
    """Protected OpenAPI schema (requires authentication)."""
    return app.openapi()
