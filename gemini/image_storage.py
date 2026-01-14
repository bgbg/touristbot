"""
Image Storage Module for GCS

Handles uploading images to Google Cloud Storage with proper content types
and public URL generation.
"""

import os
from typing import List, Optional, Tuple

from google.cloud import storage
from google.oauth2 import service_account

from gemini.image_extractor import ExtractedImage


class ImageStorage:
    """Manages image storage in Google Cloud Storage"""

    @staticmethod
    def _sanitize_path_component(value: str) -> str:
        """
        Sanitize path component to prevent path traversal attacks

        Args:
            value: Path component to sanitize

        Returns:
            Sanitized path component
        """
        # Remove path traversal sequences
        sanitized = value.replace('../', '').replace('..\\', '')
        # Replace path separators with underscores
        sanitized = sanitized.replace('/', '_').replace('\\', '_')
        # Remove any remaining dots at start
        sanitized = sanitized.lstrip('.')
        return sanitized

    def __init__(self, bucket_name: str, credentials_json: Optional[str] = None):
        """
        Initialize image storage

        Args:
            bucket_name: Name of the GCS bucket
            credentials_json: Optional service account JSON string
        """
        self.bucket_name = bucket_name

        # Initialize GCS client
        if credentials_json:
            import json
            credentials_dict = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict
            )
            project_id = credentials_dict.get("project_id")
            self.client = storage.Client(credentials=credentials, project=project_id)
        else:
            # Use default credentials
            self.client = storage.Client()

        self.bucket = self.client.bucket(bucket_name)

    def upload_image(
        self,
        image_data: bytes,
        gcs_path: str,
        content_type: str = "image/jpeg",
        make_public: bool = False,
    ) -> str:
        """
        Upload image binary data to GCS

        Args:
            image_data: Image binary data
            gcs_path: Path in GCS bucket (e.g., 'images/area/site/doc/image_001.jpg')
            content_type: MIME type (default: 'image/jpeg')
            make_public: Whether to make the image publicly accessible

        Returns:
            Public URL or GCS URI

        Raises:
            Exception: If upload fails
        """
        try:
            blob = self.bucket.blob(gcs_path)

            # Upload with proper content type
            blob.upload_from_string(image_data, content_type=content_type)

            # Make public if requested
            if make_public:
                blob.make_public()
                return blob.public_url
            else:
                # Return GCS URI
                return f"gs://{self.bucket_name}/{gcs_path}"

        except Exception as e:
            raise Exception(f"Failed to upload image to GCS: {e}")

    def upload_images_from_extraction(
        self,
        images: List[ExtractedImage],
        area: str,
        site: str,
        doc: str,
        make_public: bool = False,
    ) -> List[Tuple[str, str]]:
        """
        Upload multiple extracted images to GCS

        Args:
            images: List of ExtractedImage objects
            area: Area identifier
            site: Site identifier
            doc: Document identifier
            make_public: Whether to make images publicly accessible

        Returns:
            List of tuples: (gcs_path, public_url or gcs_uri)

        Raises:
            Exception: If any upload fails
        """
        uploaded = []

        # Sanitize path components to prevent path traversal
        area = self._sanitize_path_component(area)
        site = self._sanitize_path_component(site)
        doc = self._sanitize_path_component(doc)

        for i, image in enumerate(images, 1):
            # Construct GCS path
            gcs_path = f"images/{area}/{site}/{doc}/image_{i:03d}.{image.image_format}"

            # Determine content type
            content_type = self._get_content_type(image.image_format)

            # Upload
            url = self.upload_image(image.image_data, gcs_path, content_type, make_public)

            uploaded.append((gcs_path, url))

        return uploaded

    def get_signed_url(
        self, gcs_path: str, expiration_minutes: int = 60
    ) -> str:
        """
        Generate a signed URL for temporary public access

        Args:
            gcs_path: Path in GCS bucket
            expiration_minutes: URL expiration time in minutes

        Returns:
            Signed URL string

        Raises:
            Exception: If URL generation fails
        """
        try:
            from datetime import timedelta

            blob = self.bucket.blob(gcs_path)

            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET",
            )

            return url

        except Exception as e:
            raise Exception(f"Failed to generate signed URL: {e}")

    def image_exists(self, gcs_path: str) -> bool:
        """
        Check if image exists in GCS

        Args:
            gcs_path: Path in GCS bucket

        Returns:
            True if image exists, False otherwise
        """
        try:
            blob = self.bucket.blob(gcs_path)
            return blob.exists()
        except Exception:
            return False

    def list_images(self, prefix: str) -> List[str]:
        """
        List all images under a prefix

        Args:
            prefix: Path prefix (e.g., 'images/area/site/doc/')

        Returns:
            List of GCS paths
        """
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs if self._is_image(blob.name)]
        except Exception as e:
            print(f"Error listing images: {e}")
            return []

    def delete_image(self, gcs_path: str) -> bool:
        """
        Delete an image from GCS

        Args:
            gcs_path: Path in GCS bucket

        Returns:
            True on success, False on failure
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            return True
        except Exception as e:
            print(f"Error deleting image: {e}")
            return False

    @staticmethod
    def _get_content_type(image_format: str) -> str:
        """
        Get MIME type for image format

        Args:
            image_format: Image format (jpg, png, webp, etc.)

        Returns:
            MIME type string
        """
        content_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
            "heic": "image/heic",
            "heif": "image/heif",
        }

        return content_types.get(image_format.lower(), "image/jpeg")

    @staticmethod
    def _is_image(filename: str) -> bool:
        """
        Check if filename is an image

        Args:
            filename: Filename to check

        Returns:
            True if filename has image extension
        """
        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
        ext = os.path.splitext(filename)[1].lower()
        return ext in image_extensions


def get_image_storage(bucket_name: str, credentials_json: Optional[str] = None) -> ImageStorage:
    """
    Convenience function to get ImageStorage instance

    Args:
        bucket_name: GCS bucket name
        credentials_json: Optional service account JSON

    Returns:
        ImageStorage instance
    """
    return ImageStorage(bucket_name, credentials_json)
