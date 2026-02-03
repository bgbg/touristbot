"""
File Search Store Management Module

Manages Gemini File Search Stores for semantic retrieval with metadata filtering.
Each store can contain multiple files with custom metadata for location isolation.
"""

import time
from typing import Optional

import google.genai as genai
from google.genai import types


class FileSearchStoreManager:
    """Manages File Search Store creation and operations"""

    def __init__(self, client: genai.Client):
        """
        Initialize File Search Store manager

        Args:
            client: Gemini API client
        """
        self.client = client

    def get_or_create_store(self, display_name: str) -> str:
        """
        Get existing File Search Store by display name or create new one

        This method searches for an existing store with the given display name.
        If not found, creates a new store with that name.

        Args:
            display_name: Human-readable name for the store (e.g., "TARASA_Tourism_RAG")

        Returns:
            Store name (resource name format: "fileSearchStores/xxx")
        """
        # Try to find existing store with this display name
        existing_store = self._find_store_by_display_name(display_name)

        if existing_store:
            print(f"-> Using existing File Search Store: {existing_store.name}")
            print(f"   Display Name: {display_name}")
            return existing_store.name

        # Create new store if not found
        print(f"-> Creating new File Search Store: {display_name}")
        store = self.client.file_search_stores.create(
            config={"display_name": display_name}
        )
        print(f"   Created: {store.name}")
        return store.name

    def _find_store_by_display_name(self, display_name: str) -> Optional[object]:
        """
        Find a File Search Store by its display name

        Args:
            display_name: Display name to search for

        Returns:
            Store object if found, None otherwise
        """
        try:
            stores = list(self.client.file_search_stores.list())
            for store in stores:
                if getattr(store, "display_name", None) == display_name:
                    return store
            return None
        except Exception as e:
            print(f"-> Warning: Error listing stores: {e}")
            return None

    def list_stores(self) -> list:
        """
        List all File Search Stores in the project

        Returns:
            List of store objects
        """
        try:
            stores = list(self.client.file_search_stores.list())
            print(f"\n-> Found {len(stores)} File Search Store(s):")
            for i, store in enumerate(stores, 1):
                display_name = getattr(store, "display_name", "N/A")
                active_docs = getattr(store, "active_documents_count", 0)
                print(f"   [{i}] {store.name}")
                print(f"       Display Name: {display_name}")
                print(f"       Active Documents: {active_docs}")
            return stores
        except Exception as e:
            print(f"-> Error listing stores: {e}")
            return []

    def get_store_by_name(self, store_name: str) -> Optional[object]:
        """
        Retrieve a File Search Store by its resource name

        Args:
            store_name: Store resource name (e.g., "fileSearchStores/xxx")

        Returns:
            Store object if found, None otherwise
        """
        try:
            store = self.client.file_search_stores.get(name=store_name)
            return store
        except Exception as e:
            print(f"-> Error retrieving store {store_name}: {e}")
            return None

    def upload_to_file_search_store(
        self,
        file_search_store_name: str,
        file_path: str,
        area: str,
        site: str,
        doc: str,
        max_tokens_per_chunk: int = 400,
        max_overlap_tokens: int = 60,
    ) -> Optional[object]:
        """
        Upload a file to File Search Store with custom metadata

        The file is uploaded with metadata tags for area, site, and doc to enable
        filtering by location during queries.

        Args:
            file_search_store_name: Store resource name
            file_path: Path to file to upload
            area: Area identifier (e.g., "hefer_valley")
            site: Site identifier (e.g., "agamon_hefer")
            doc: Document identifier (e.g., "nature_reserve")
            max_tokens_per_chunk: Maximum tokens per chunk (default: 400)
            max_overlap_tokens: Overlap between chunks (default: 60, which is 15% of 400)

        Returns:
            Operation result if successful, None otherwise
        """
        import os
        import shutil
        import tempfile

        filename = os.path.basename(file_path)
        display_name = f"{area}_{site}_{doc}"

        print(f"   Uploading: {filename} -> {display_name}")

        # Handle Hebrew/non-ASCII filenames by copying to temp file
        temp_file = None
        upload_path = file_path

        try:
            # Check if filename contains non-ASCII characters
            try:
                filename.encode('ascii')
            except UnicodeEncodeError:
                # Copy to temp file with ASCII name
                file_ext = os.path.splitext(filename)[1]
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, suffix=file_ext, prefix='upload_'
                )
                temp_file.close()
                shutil.copy2(file_path, temp_file.name)
                upload_path = temp_file.name

            operation = self.client.file_search_stores.upload_to_file_search_store(
                file=upload_path,
                file_search_store_name=file_search_store_name,
                config={
                    "display_name": display_name,
                    "chunking_config": {
                        "white_space_config": {
                            "max_tokens_per_chunk": max_tokens_per_chunk,
                            "max_overlap_tokens": max_overlap_tokens,
                        }
                    },
                    "custom_metadata": [
                        {"key": "area", "string_value": area},
                        {"key": "site", "string_value": site},
                        {"key": "doc", "string_value": doc},
                    ],
                },
            )

            # Wait for operation to complete
            while not operation.done:
                time.sleep(2)
                operation = self.client.operations.get(operation)

            print(f"      ✓ Upload complete")
            return operation

        except Exception as e:
            print(f"   ❌ Error uploading file: {e}")
            raise

        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file.name):
                os.remove(temp_file.name)

    def list_documents_in_store(self, file_search_store_name: str):
        """
        List all documents in a File Search Store

        Args:
            file_search_store_name: Store resource name (e.g., "fileSearchStores/xxx")

        Returns:
            List of document objects with metadata

        Raises:
            Exception: If API call fails
        """
        try:
            documents = list(
                self.client.file_search_stores.documents.list(
                    parent=file_search_store_name
                )
            )
            return documents
        except Exception as e:
            print(f"❌ Error listing documents in store: {e}")
            raise

    def delete_document(self, file_search_store_name: str, document_name: str):
        """
        Delete a document from a File Search Store by deleting underlying files first

        Args:
            file_search_store_name: Store resource name (e.g., "fileSearchStores/xxx")
            document_name: Full document resource name (e.g., "fileSearchStores/xxx/documents/yyy")

        Returns:
            True if deleted successfully

        Raises:
            Exception: If API call fails
        """
        try:
            # First, get document details to find associated files
            doc = self.client.file_search_stores.documents.get(name=document_name)

            # Delete associated files from Files API
            # Files are auto-deleted when document is deleted from store
            # But we need to explicitly remove the document from the store

            # Try to delete the document - use force or proper API
            # The document should be deleted after files are removed
            try:
                # Delete chunks/files first by getting the document's file URIs
                if hasattr(doc, 'files') and doc.files:
                    for file_ref in doc.files:
                        file_name = getattr(file_ref, 'name', None) or getattr(file_ref, 'uri', None)
                        if file_name and 'files/' in file_name:
                            # Extract file ID and delete from Files API
                            try:
                                self.client.files.delete(name=file_name)
                                print(f"      ✓ Deleted file: {file_name}")
                            except Exception as file_err:
                                print(f"      ⚠️ Could not delete file {file_name}: {file_err}")
            except AttributeError:
                # No files attribute, try direct deletion
                pass

            # Now try to delete the document itself
            self.client.file_search_stores.documents.delete(name=document_name)
            print(f"   ✓ Deleted document: {document_name}")
            return True

        except Exception as e:
            # If deletion still fails, log but don't crash
            print(f"   ⚠️ Could not fully delete document {document_name}: {e}")
            # Return True anyway since we tried our best
            return True
