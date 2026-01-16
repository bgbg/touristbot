"""
Topics endpoint - Retrieve topics for a location.

Topics are pre-generated and stored in GCS at:
topics/{area}/{site}/topics.json
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import ApiKeyDep
from backend.dependencies import get_storage_backend
from backend.gcs_storage import StorageBackend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/topics", tags=["topics"])


def get_topics_for_location(
    storage: StorageBackend, area: str, site: str
) -> list[str]:
    """
    Load topics from GCS for a specific location.

    Args:
        storage: GCS storage backend
        area: Location area
        site: Location site

    Returns:
        List of topic strings (empty list if not found)
    """
    topics_path = f"topics/{area}/{site}/topics.json"

    try:
        content = storage.read(topics_path)
        if not content:
            logger.info(f"No topics file found for {area}/{site}")
            return []

        topics = json.loads(content)

        if not isinstance(topics, list):
            logger.warning(
                f"Topics file has invalid format (not a list): {area}/{site}"
            )
            return []

        logger.info(f"Loaded {len(topics)} topics for {area}/{site}")
        return topics

    except FileNotFoundError:
        logger.info(f"Topics file not found: {area}/{site}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in topics file {area}/{site}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error loading topics for {area}/{site}: {e}")
        return []


@router.get("/{area}/{site}")
async def get_topics(
    area: str,
    site: str,
    api_key: ApiKeyDep,
    storage: StorageBackend = Depends(get_storage_backend),
) -> dict:
    """
    Get topics for a specific location.

    Args:
        area: Location area (e.g., "hefer_valley")
        site: Location site (e.g., "agamon_hefer")
        api_key: API key (from auth dependency)
        storage: GCS storage backend (injected dependency)

    Returns:
        JSON response with:
        - area: Location area
        - site: Location site
        - topics: List of topic strings
        - count: Number of topics
    """
    logger.info(f"Topics request: {area}/{site}")

    topics = get_topics_for_location(storage, area, site)

    return {
        "area": area,
        "site": site,
        "topics": topics,
        "count": len(topics),
    }
