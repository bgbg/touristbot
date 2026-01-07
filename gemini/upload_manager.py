#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload Manager - Handles file uploads, deletions, and tracking for Streamlit UI

Provides functionality to:
- View uploaded content
- Remove uploaded content
- Upload new content with or without force
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import google.genai as genai

from gemini.chunker import chunk_file_tokens, chunk_text_file
from gemini.config import GeminiConfig
from gemini.directory_parser import DirectoryParser
from gemini.store_manager import StoreManager
from gemini.store_registry import StoreRegistry
from gemini.upload_tracker import UploadTracker


class UploadManager:
    """Manages content uploads and tracking for the RAG system"""

    def __init__(
        self,
        config: GeminiConfig,
        client: genai.Client,
        registry: StoreRegistry,
        tracker: UploadTracker,
    ):
        self.config = config
        self.client = client
        self.registry = registry
        self.tracker = tracker

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

            # Count chunks on disk
            chunks_dir = os.path.join(self.config.chunks_dir, area, site)
            chunk_count = 0
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
            # Remove chunks from disk
            chunks_dir = os.path.join(self.config.chunks_dir, area, site)
            if os.path.exists(chunks_dir):
                import shutil

                shutil.rmtree(chunks_dir)

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
                        )
                    else:
                        chunks = chunk_text_file(
                            file_path,
                            file_id,
                            chunk_size=self.config.chunk_size,
                            output_dir=area_site_chunks_dir,
                        )
                    chunk_files.extend(chunks)

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
