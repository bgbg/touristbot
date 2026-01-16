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


# Create FastAPI app
app = FastAPI(
    title="Tourism RAG Backend",
    description="Serverless backend for tourism Q&A system using Google Gemini File Search API",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware (allow all origins for MVP)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify Streamlit URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {
        "status": "healthy",
        "service": "tourism-rag-backend",
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Tourism RAG Backend",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "qa": "/qa",
            "topics": "/topics/{area}/{site}",
            "locations": "/locations",
            "upload": "/upload/{area}/{site}",
        },
        "documentation": "/docs",
    }


@app.get("/protected-test")
async def protected_test(api_key: ApiKeyDep):
    """Test endpoint demonstrating API key authentication."""
    return {
        "message": "Authentication successful",
        "api_key_prefix": api_key[:8] + "..." if len(api_key) > 8 else api_key,
    }
