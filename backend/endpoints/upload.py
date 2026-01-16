"""
Upload endpoint - Content upload and processing.

NOTE: This is a simplified placeholder implementation.
For MVP, uploads can be handled via the existing CLI uploader
or this endpoint can be enhanced to match main_upload.py logic.
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.auth import ApiKeyDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/{area}/{site}")
async def upload_content(
    area: str,
    site: str,
    api_key: ApiKeyDep,
    file: UploadFile = File(...),
) -> dict:
    """
    Upload content file for a location.

    NOTE: Simplified placeholder - for MVP, use CLI uploader instead.
    
    Full implementation would:
    - Save file to temporary storage
    - Process with FileSearchStoreManager
    - Extract images from DOCX
    - Upload images to GCS and File API
    - Update registries
    - Generate topics
    
    Args:
        area: Location area
        site: Location site
        api_key: API key
        file: Uploaded file

    Returns:
        Upload status
    """
    logger.info(f"Upload request: {area}/{site} - {file.filename}")
    
    raise HTTPException(
        status_code=501,
        detail="Upload endpoint not implemented - please use CLI uploader (gemini/main_upload.py) for MVP"
    )
