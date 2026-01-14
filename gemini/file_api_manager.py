"""
Gemini File API Manager

Handles uploading files (especially images) to Gemini File API
and obtaining URIs for use in multimodal contexts.
"""

import time
from typing import List, Optional, Tuple

import google.genai as genai
from google.genai import types

from gemini.image_extractor import ExtractedImage


class FileAPIManager:
    """Manages uploads to Gemini File API"""

    # Maximum wait time for file processing (5 minutes)
    MAX_WAIT_SECONDS = 300

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

    def __init__(self, client: genai.Client):
        """
        Initialize File API manager

        Args:
            client: Gemini API client
        """
        self.client = client

    def upload_image(
        self, image_path: str, display_name: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Upload image file to Gemini File API

        Args:
            image_path: Path to image file (local or temp)
            display_name: Optional display name for the file

        Returns:
            Tuple of (file_uri, file_name)

        Raises:
            Exception: If upload fails
        """
        try:
            # Prepare upload config
            if display_name:
                config = types.UploadFileConfig(display_name=display_name)
                file = self.client.files.upload(file=image_path, config=config)
            else:
                file = self.client.files.upload(file=image_path)

            # Wait for file to be active with timeout
            elapsed = 0
            while file.state.name == "PROCESSING" and elapsed < self.MAX_WAIT_SECONDS:
                time.sleep(1)
                elapsed += 1
                file = self.client.files.get(name=file.name)

            if file.state.name == "PROCESSING":
                # Clean up stuck file
                try:
                    self.client.files.delete(name=file.name)
                except Exception:
                    pass
                raise Exception(
                    f"File upload timeout after {self.MAX_WAIT_SECONDS}s. "
                    f"File stuck in PROCESSING state: {file.name}"
                )

            if file.state.name != "ACTIVE":
                raise Exception(f"File upload failed with state: {file.state.name}")

            return file.uri, file.name

        except Exception as e:
            raise Exception(f"Failed to upload image to File API: {e}")

    def upload_image_from_bytes(
        self,
        image_data: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
        display_name: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Upload image from binary data to Gemini File API

        Args:
            image_data: Image binary data
            filename: Filename to use for upload
            mime_type: MIME type of the image
            display_name: Optional display name

        Returns:
            Tuple of (file_uri, file_name)

        Raises:
            Exception: If upload fails
        """
        import tempfile
        import os

        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(filename)[1]
            ) as tmp_file:
                tmp_file.write(image_data)
                tmp_path = tmp_file.name

            try:
                # Upload from temp file
                uri, name = self.upload_image(tmp_path, display_name)
                return uri, name
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        except Exception as e:
            raise Exception(f"Failed to upload image from bytes: {e}")

    def upload_images_from_extraction(
        self, images: List[ExtractedImage], area: str, site: str, doc: str
    ) -> List[Tuple[int, str, str, str]]:
        """
        Upload multiple extracted images to File API

        Args:
            images: List of ExtractedImage objects
            area: Area identifier
            site: Site identifier
            doc: Document identifier

        Returns:
            List of tuples: (image_index, file_uri, file_name, caption)

        Raises:
            Exception: If any upload fails
        """
        uploaded = []

        # Sanitize path components to prevent path traversal
        area = self._sanitize_path_component(area)
        site = self._sanitize_path_component(site)
        doc = self._sanitize_path_component(doc)

        for i, image in enumerate(images, 1):
            # Create display name
            display_name = f"{area}_{site}_{doc}_image_{i:03d}"

            # Create filename
            filename = f"image_{i:03d}.{image.image_format}"

            # Determine MIME type
            mime_type = self._get_mime_type(image.image_format)

            try:
                # Upload from bytes
                file_uri, file_name = self.upload_image_from_bytes(
                    image_data=image.image_data,
                    filename=filename,
                    mime_type=mime_type,
                    display_name=display_name,
                )

                uploaded.append((i, file_uri, file_name, image.caption))

                print(f"  ✓ Uploaded image {i}: {file_uri}")

            except Exception as e:
                print(f"  ❌ Failed to upload image {i}: {e}")
                raise

        return uploaded

    def delete_file(self, file_name: str) -> bool:
        """
        Delete a file from File API

        Args:
            file_name: File name (e.g., 'files/abc123')

        Returns:
            True on success, False on failure
        """
        try:
            self.client.files.delete(name=file_name)
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False

    def get_file(self, file_name: str):
        """
        Get file metadata from File API

        Args:
            file_name: File name (e.g., 'files/abc123')

        Returns:
            File object

        Raises:
            Exception: If file not found
        """
        try:
            return self.client.files.get(name=file_name)
        except Exception as e:
            raise Exception(f"Failed to get file: {e}")

    def list_files(self, page_size: int = 100):
        """
        List files in File API

        Args:
            page_size: Number of files per page

        Returns:
            List of file objects
        """
        try:
            return list(self.client.files.list(page_size=page_size))
        except Exception as e:
            print(f"Error listing files: {e}")
            return []

    @staticmethod
    def _get_mime_type(image_format: str) -> str:
        """
        Get MIME type for image format

        Args:
            image_format: Image format (jpg, png, webp, etc.)

        Returns:
            MIME type string
        """
        mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
            "heic": "image/heic",
            "heif": "image/heif",
        }

        return mime_types.get(image_format.lower(), "image/jpeg")
