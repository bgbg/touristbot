#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload Manager - Handles file uploads, deletions, and tracking for Streamlit UI

Provides functionality to:
- View uploaded content
- Remove uploaded content
- Upload new content with or without force
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import google.genai as genai

from gemini.chunker import chunk_file_tokens, chunk_text_file
from gemini.config import GeminiConfig
from gemini.directory_parser import DirectoryParser
from gemini.store_manager import StoreManager
from gemini.store_registry import StoreRegistry
from gemini.topic_extractor import extract_topics_from_chunks
from gemini.upload_tracker import UploadTracker

if TYPE_CHECKING:
    from gemini.storage import StorageBackend


class UploadManager:
    """Manages content uploads and tracking for the RAG system"""

    def __init__(
        self,
        config: GeminiConfig,
        client: genai.Client,
        registry: StoreRegistry,
        tracker: UploadTracker,
        storage_backend: Optional["StorageBackend"] = None,
    ):
        self.config = config
        self.client = client
        self.registry = registry
        self.tracker = tracker
        self.storage_backend = storage_backend

    def get_uploaded_content_summary(self) -> List[Dict]:
        """
        Get summary of all uploaded content

        Returns:
            List of dicts with area, site, store_id, metadata
        """
        all_stores = self.registry.list_all()
        summary = []

        for (area, site), store_id in all_stores.items():
            registry_data = self.registry.registry.get(f"{area}:{site}", {})
            metadata = registry_data.get("metadata", {})

            # Count chunks from storage backend or disk
            chunk_count = 0
            if self.storage_backend:
                # Use storage backend (GCS)
                try:
                    chunks_path = f"{self.config.chunks_dir}/{area}/{site}"
                    print(f"[DEBUG] Listing chunks from GCS: {chunks_path}")
                    chunk_files = self.storage_backend.list_files(chunks_path, "*.txt")
                    chunk_count = len(chunk_files)
                    print(f"[DEBUG] Found {chunk_count} chunks for {area}/{site}")
                except Exception as e:
                    print(f"[ERROR] Failed to list chunks from GCS for {area}/{site}: {e}")
                    import traceback
                    traceback.print_exc()
                    chunk_count = 0
            else:
                # Use local filesystem
                print(f"[DEBUG] Storage backend is None, using local filesystem")
                chunks_dir = os.path.join(self.config.chunks_dir, area, site)
                if os.path.exists(chunks_dir):
                    chunk_count = len(
                        [f for f in os.listdir(chunks_dir) if f.endswith(".txt")]
                    )

            summary.append(
                {
                    "area": area,
                    "site": site,
                    "store_id": store_id,
                    "file_count": metadata.get("file_count", 0),
                    "chunk_count": chunk_count,
                    "created_at": metadata.get("created_at", "N/A"),
                    "last_updated": metadata.get("last_updated", "N/A"),
                }
            )

        return summary

    def get_uploaded_files_for_location(
        self, area: str, site: str
    ) -> List[Dict[str, str]]:
        """
        Get list of uploaded files for a specific area/site

        Returns:
            List of dicts with file info
        """
        files = []
        for key, data in self.tracker.tracking_data.items():
            if data.get("area") == area and data.get("site") == site:
                files.append(
                    {
                        "file_path": data.get("file_path", ""),
                        "uploaded_at": data.get("uploaded_at", ""),
                        "hash": data.get("hash", ""),
                    }
                )
        return files

    def remove_location(self, area: str, site: str) -> Tuple[bool, str]:
        """
        Remove all content for a specific area/site

        - Deletes chunks from disk
        - Removes from registry
        - Removes from upload tracking
        - Does NOT delete from Gemini API (stores persist there)

        Returns:
            (success: bool, message: str)
        """
        try:
            # Remove chunks from storage backend or disk
            if self.storage_backend:
                # Use storage backend (GCS) - delete all chunks for this area/site
                chunks_path = f"{self.config.chunks_dir}/{area}/{site}"
                chunk_files = self.storage_backend.list_files(chunks_path)
                for chunk_file in chunk_files:
                    self.storage_backend.delete_file(chunk_file)

                # Delete topics file if it exists
                try:
                    topics_path = f"topics/{area}/{site}/topics.json"
                    self.storage_backend.delete_file(topics_path)
                except Exception:
                    # Topics file may not exist, ignore error
                    pass
            else:
                # Use local filesystem
                chunks_dir = os.path.join(self.config.chunks_dir, area, site)
                if os.path.exists(chunks_dir):
                    import shutil

                    shutil.rmtree(chunks_dir)

                # Delete topics file if it exists
                topics_file = os.path.join("topics", area, site, "topics.json")
                if os.path.exists(topics_file):
                    import shutil
                    topics_dir = os.path.join("topics", area, site)
                    shutil.rmtree(topics_dir)

            # Remove from registry
            store_key = f"{area}:{site}"
            if store_key in self.registry.registry:
                del self.registry.registry[store_key]
                self.registry._save_registry()

            # Remove from tracking
            keys_to_remove = []
            for key, data in self.tracker.tracking_data.items():
                if data.get("area") == area and data.get("site") == site:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.tracker.tracking_data[key]

            self.tracker._save_tracking()

            return True, f"Successfully removed {area}/{site} from local tracking"

        except Exception as e:
            return False, f"Error removing {area}/{site}: {str(e)}"

    def upload_content(
        self,
        area: Optional[str] = None,
        site: Optional[str] = None,
        force: bool = False,
        flat_folder: bool = False,
    ) -> Tuple[bool, str, Dict]:
        """
        Upload content for specific area/site or all content

        Args:
            area: Specific area to upload (None for all, required if flat_folder=True)
            site: Specific site to upload (requires area, required if flat_folder=True)
            force: Force re-upload even if already uploaded
            flat_folder: If True, treat content_root as a flat folder containing files directly

        Returns:
            (success: bool, message: str, stats: dict)
        """
        try:
            if flat_folder:
                # Handle flat folder upload
                if not area or not site:
                    return (
                        False,
                        "Area and site are required for flat folder uploads",
                        {},
                    )

                # Get all supported files from the folder
                import glob

                files = []
                for ext in self.config.supported_formats:
                    pattern = os.path.join(self.config.content_root, f"*{ext}")
                    files.extend(glob.glob(pattern))

                if not files:
                    return (
                        False,
                        f"No supported files found in {self.config.content_root}",
                        {},
                    )

                structure = {(area, site): files}
            else:
                # Parse directory structure
                parser = DirectoryParser(
                    self.config.content_root, self.config.supported_formats
                )
                structure = parser.parse_directory_structure()

                # Filter by area/site if specified
                if area:
                    structure = {
                        (a, s): files
                        for (a, s), files in structure.items()
                        if a == area and (not site or s == site)
                    }

                    if not structure:
                        return (
                            False,
                            f"No content found for {area}/{site or 'any site'}",
                            {},
                        )

            stats = {
                "total_files": 0,
                "total_chunks": 0,
                "locations_processed": 0,
                "locations_skipped": 0,
            }

            force_upload = force or self.config.force_reupload

            # Process each area/site
            for (loc_area, loc_site), files in structure.items():
                # Filter out already uploaded files
                files_to_upload = self.tracker.get_new_files(
                    files, loc_area, loc_site, force=force_upload
                )

                if not files_to_upload:
                    stats["locations_skipped"] += 1
                    continue

                # Chunk files
                chunk_files = []
                for file_path in files_to_upload:
                    # For GCS: use blob path like "chunks/area/site"
                    # For local: use directory path like "data/chunks/area/site"
                    if self.storage_backend:
                        area_site_chunks_dir = f"{self.config.chunks_dir}/{loc_area}/{loc_site}"
                    else:
                        area_site_chunks_dir = os.path.join(
                            self.config.chunks_dir, loc_area, loc_site
                        )

                    file_id = os.path.splitext(os.path.basename(file_path))[0]

                    if self.config.use_token_chunking:
                        chunks = chunk_file_tokens(
                            file_path,
                            file_id,
                            chunk_tokens=self.config.chunk_tokens,
                            overlap_percent=self.config.chunk_overlap_percent,
                            output_dir=area_site_chunks_dir,
                            storage_backend=self.storage_backend,
                        )
                    else:
                        chunks = chunk_text_file(
                            file_path,
                            file_id,
                            chunk_size=self.config.chunk_size,
                            output_dir=area_site_chunks_dir,
                            storage_backend=self.storage_backend,
                        )
                    chunk_files.extend(chunks)

                # Generate topics from chunks
                topics = []
                try:
                    # Load all chunk content for topic extraction
                    combined_chunks = []
                    for chunk_file in chunk_files:
                        if self.storage_backend:
                            # Read from GCS
                            chunk_content = self.storage_backend.read_file(chunk_file)
                        else:
                            # Read from local filesystem
                            with open(chunk_file, "r", encoding="utf-8") as f:
                                chunk_content = f.read()
                        combined_chunks.append(chunk_content)

                    chunks_text = "\n\n".join(combined_chunks)

                    # Extract topics using Gemini
                    topics = extract_topics_from_chunks(
                        chunks=chunks_text,
                        area=loc_area,
                        site=loc_site,
                        model=self.config.model,
                        client=self.client,
                    )

                    # Write topics to GCS
                    topics_path = f"topics/{loc_area}/{loc_site}/topics.json"
                    topics_json = json.dumps(topics, ensure_ascii=False, indent=2)

                    if self.storage_backend:
                        self.storage_backend.write_file(topics_path, topics_json)
                    else:
                        # Write to local filesystem
                        topics_dir = os.path.join("topics", loc_area, loc_site)
                        os.makedirs(topics_dir, exist_ok=True)
                        topics_file = os.path.join(topics_dir, "topics.json")
                        with open(topics_file, "w", encoding="utf-8") as f:
                            f.write(topics_json)

                    print(f"-> Generated {len(topics)} topics for {loc_area}/{loc_site}")

                except Exception as e:
                    print(f"-> Warning: Topic generation failed for {loc_area}/{loc_site}: {e}")
                    # Continue with upload even if topic generation fails
                    topics = []

                # Upload to store
                store_id = self.registry.get_store(loc_area, loc_site)
                store_manager = StoreManager(
                    self.client,
                    f"{loc_area}_{loc_site}_Tourism_RAG",
                    store_id=store_id,
                    area=loc_area,
                    site=loc_site,
                )

                store_manager.upload_files(
                    chunk_files, max_wait_seconds=self.config.max_upload_wait_seconds
                )

                # Register the store
                store_name = store_manager.store_name
                self.registry.register_store(
                    area=loc_area,
                    site=loc_site,
                    store_name=store_name,
                    metadata={
                        "file_count": len(files_to_upload),
                        "chunk_count": len(chunk_files),
                        "topic_count": len(topics),
                    },
                )

                # Mark files as uploaded
                for file_path in files_to_upload:
                    self.tracker.mark_file_uploaded(file_path, loc_area, loc_site)

                stats["total_files"] += len(files_to_upload)
                stats["total_chunks"] += len(chunk_files)
                stats["locations_processed"] += 1

            message = f"Upload complete: {stats['locations_processed']} locations, {stats['total_files']} files, {stats['total_chunks']} chunks"
            return True, message, stats

        except Exception as e:
            return False, f"Upload failed: {str(e)}", {}

    def get_available_locations(self) -> List[Tuple[str, str]]:
        """
        Get list of available locations from content directory

        Returns:
            List of (area, site) tuples
        """
        try:
            parser = DirectoryParser(
                self.config.content_root, self.config.supported_formats
            )
            structure = parser.parse_directory_structure()
            return list(structure.keys())
        except Exception:
            return []
