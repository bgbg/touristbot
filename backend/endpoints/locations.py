"""
Locations endpoint - Content management for areas and sites.

Provides listing and metadata for available locations.
"""

import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import ApiKeyDep
from backend.dependencies import get_storage_backend, get_store_registry
from backend.endpoints.topics import get_topics_for_location
from backend.gcs_storage import StorageBackend
from backend.store_registry import StoreRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("")
async def list_locations(
    api_key: ApiKeyDep,
    store_registry: StoreRegistry = Depends(get_store_registry),
) -> dict:
    """
    List all available locations (areas and sites).

    Args:
        api_key: API key (from auth dependency)
        store_registry: Store registry (injected dependency)

    Returns:
        JSON response with:
        - locations: List of location objects (area, site, store_name)
        - count: Total number of locations
        - areas: List of unique areas
    """
    logger.info("Listing all locations")

    try:
        # Get all locations from store registry
        locations_map = store_registry.list_all()

        # Convert to list format
        locations = []
        areas_set = set()

        for (area, site), store_name in locations_map.items():
            locations.append({
                "area": area,
                "site": site,
                "store_name": store_name,
            })
            areas_set.add(area)

        # Sort by area, then site
        locations.sort(key=lambda x: (x["area"], x["site"]))

        logger.info(f"Found {len(locations)} locations across {len(areas_set)} areas")

        return {
            "locations": locations,
            "count": len(locations),
            "areas": sorted(list(areas_set)),
        }

    except Exception as e:
        logger.error(f"Error listing locations: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list locations: {str(e)}"
        )


@router.get("/{area}/{site}/content")
async def get_location_content(
    area: str,
    site: str,
    api_key: ApiKeyDep,
    store_registry: StoreRegistry = Depends(get_store_registry),
    storage: StorageBackend = Depends(get_storage_backend),
) -> dict:
    """
    Get content metadata for a specific location.

    Args:
        area: Location area
        site: Location site
        api_key: API key (from auth dependency)
        store_registry: Store registry (injected dependency)
        storage: GCS storage backend (injected dependency)

    Returns:
        JSON response with:
        - area: Location area
        - site: Location site
        - store_name: File Search Store name
        - has_topics: Whether topics are available
        - topics_count: Number of topics
    """
    logger.info(f"Getting content metadata for {area}/{site}")

    try:
        # Check if location exists in store registry
        store_name = store_registry.get_store(area, site)
        if not store_name:
            raise HTTPException(
                status_code=404,
                detail=f"Location not found: {area}/{site}",
            )

        # Get topics count
        topics = get_topics_for_location(storage, area, site)
        topics_count = len(topics)

        return {
            "area": area,
            "site": site,
            "store_name": store_name,
            "has_topics": topics_count > 0,
            "topics_count": topics_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting location content: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get location content: {str(e)}",
        )
