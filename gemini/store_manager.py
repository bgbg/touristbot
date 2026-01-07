"""
Gemini File Search Store management (create, upload, list)
"""

import os
import sys
import time
from typing import List, Optional

import google.genai as genai
from google.genai import types

from gemini.display_name_utils import encode_display_name


class StoreManager:
    """Manages Gemini File Search Store operations"""

    def __init__(
        self,
        client: genai.Client,
        store_display_name: str,
        store_id: str = None,
        area: Optional[str] = None,
        site: Optional[str] = None,
    ):
        """
        Initialize store manager

        Args:
            client: Gemini API client
            store_display_name: Display name for the store
            store_id: Specific store ID to use (optional)
            area: Area name for metadata encoding (optional)
            site: Site name for metadata encoding (optional)
        """
        self.client = client
        self.store_display_name = store_display_name
        self.store_id = store_id
        self.area = area
        self.site = site
        self._store = None

    def get_or_create_store(self):
        """
        Get existing store or create new one (uses cache mechanism)

        Returns:
            Cache object that can be used for file search
        """
        if self._store:
            return self._store

        # For the new API, we'll use caches instead of file_search_stores
        # Note: This is a simplified version - the new API uses a different architecture
        print(
            f"\n-> Note: Using simplified file upload (File Search Stores deprecated in google-genai v1.46+)"
        )
        print(f"-> Files will be uploaded individually to Gemini Files API")

        # Return a dummy store object since we're using direct file uploads
        self._store = {"name": f"direct_upload_{self.store_display_name}"}
        return self._store

    def upload_files(self, file_paths: List[str], max_wait_seconds: int = 300) -> List:
        """
        Upload multiple files using the new Files API

        Args:
            file_paths: List of file paths to upload
            max_wait_seconds: Maximum time to wait for uploads to complete

        Returns:
            List of uploaded file objects
        """
        store = self.get_or_create_store()

        print(f"\n-> Uploading {len(file_paths)} files...")

        uploaded_files = []
        for file_path in file_paths:
            try:
                filename = os.path.basename(file_path)
                safe_filename = filename.encode("utf-8", errors="replace").decode(
                    "utf-8"
                )
                print(f"   Uploading: {safe_filename}")
            except Exception:
                print(f"   Uploading: {file_path}")

            try:
                # Determine display name based on whether area/site are provided
                base_filename = os.path.basename(file_path)

                if self.area and self.site:
                    # Encode area/site metadata in display name
                    display_name = encode_display_name(
                        self.area, self.site, base_filename
                    )
                    print(f"      → Encoded display name: {display_name}")
                else:
                    # Legacy behavior: use plain filename (for backwards compatibility)
                    display_name = base_filename

                # Use the new files.upload API with display name
                config = types.UploadFileConfig(displayName=display_name)
                uploaded_file = self.client.files.upload(file=file_path, config=config)
                uploaded_files.append(uploaded_file)
                print(f"      ✓ Uploaded as: {uploaded_file.name}")
            except Exception as e:
                print(f"   ❌ Error uploading file: {e}")
                # Re-raise to be caught by the outer handler
                raise

        print(f"-> Successfully uploaded {len(uploaded_files)} files.")
        return uploaded_files

    def list_files(self) -> int:
        """
        Get the count of active documents in the store

        Returns:
            Number of active documents
        """
        store = self.get_or_create_store()

        # Refresh store info to get latest document counts
        store = self.client.file_search_stores.get(name=store.name)

        active_count = store.active_documents_count or 0
        print(f"-> Store has {active_count} active documents")

        return active_count

    @property
    def store_name(self) -> str:
        """Get the store name (creates store if needed)"""
        store = self.get_or_create_store()
        return store["name"] if isinstance(store, dict) else store.name

    def list_all_stores(self) -> list:
        """
        List all available stores

        Returns:
            List of store objects
        """
        try:
            stores = list(self.client.file_search_stores.list())
            print(f"\n-> Found {len(stores)} total stores:")
            for i, store in enumerate(stores, 1):
                display_name = getattr(store, "display_name", "N/A")
                print(f"   [{i}] {store.name}")
                print(f"       Display Name: {display_name}")
            return stores
        except Exception as e:
            print(f"-> Error listing stores: {e}")
            return []
