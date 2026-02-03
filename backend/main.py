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
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth import ApiKeyDep
from backend.endpoints import conversations, locations, qa, topics, upload

# Load environment variables from .env file (for local development only)
# In Cloud Run, environment variables are set by the platform
if not os.getenv("K_SERVICE"):
    load_dotenv()


def configure_logging():
    """
    Configure logging based on environment.

    - Cloud Run (detected via K_SERVICE env var): stdout only, INFO level
    - Local: dual logging (stdout + rotating file), INFO level
    """
    # Detect environment
    is_cloud_run = bool(os.getenv("K_SERVICE"))
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Create root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    root_logger.handlers = []

    # Format for log messages
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Always add stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    # Add file handler for local development only
    if not is_cloud_run:
        try:
            file_handler = RotatingFileHandler(
                "backend.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Log error but don't fail startup
            root_logger.warning(f"Failed to create file handler: {e}")

    # Log configuration
    env_type = "Cloud Run" if is_cloud_run else "Local"
    handlers = "stdout only" if is_cloud_run else "stdout + file (backend.log)"
    root_logger.info(f"Logging configured for {env_type}: level={log_level_str}, handlers={handlers}")

    return root_logger


# Configure logging
configure_logging()
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
app.include_router(conversations.router)


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
            "conversations": {
                "delete_one": "/conversations/{conversation_id}",
                "delete_bulk": "/conversations?older_than_hours={hours}&prefix={prefix}",
            },
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
