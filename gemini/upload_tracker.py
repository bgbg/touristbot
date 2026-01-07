"""
Upload Tracker - Tracks which files have been uploaded to avoid duplicates
Maintains file hashes and modification times for incremental uploads
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set


class UploadTracker:
    """Tracks uploaded files to enable incremental uploads"""

    def __init__(self, tracking_file: str = "upload_tracking.json"):
        """
        Initialize upload tracker

        Args:
            tracking_file: Path to JSON file storing upload history
        """
        self.tracking_file = tracking_file
        self.tracking_data: Dict[str, Dict] = self._load_tracking()

    def _load_tracking(self) -> Dict[str, Dict]:
        """Load tracking data from disk"""
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse {self.tracking_file}. Starting fresh.")
                return {}
        return {}

    def _save_tracking(self):
        """Save tracking data to disk"""
        try:
            os.makedirs(os.path.dirname(self.tracking_file) or ".", exist_ok=True)
            with open(self.tracking_file, "w", encoding="utf-8") as f:
                json.dump(self.tracking_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"-> Warning: Could not save tracking data: {e}")

    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def _get_file_mtime(file_path: str) -> float:
        """Get file modification time"""
        return os.path.getmtime(file_path)

    def is_file_uploaded(self, file_path: str, area: str, site: str) -> bool:
        """
        Check if a file has already been uploaded

        Args:
            file_path: Path to file
            area: Area name
            site: Site name

        Returns:
            True if file was already uploaded and hasn't changed
        """
        # Create unique key for this area/site/file combination
        rel_path = os.path.relpath(file_path)
        key = f"{area}:{site}:{rel_path}"

        if key not in self.tracking_data:
            return False

        # Check if file has been modified
        stored_data = self.tracking_data[key]
        current_mtime = self._get_file_mtime(file_path)

        # If modification time changed, file was updated
        if stored_data.get("mtime") != current_mtime:
            return False

        # Optionally verify hash for extra safety
        if "hash" in stored_data:
            current_hash = self._calculate_file_hash(file_path)
            if stored_data["hash"] != current_hash:
                return False

        return True

    def mark_file_uploaded(
        self, file_path: str, area: str, site: str, chunk_path: Optional[str] = None
    ):
        """
        Mark a file as uploaded

        Args:
            file_path: Path to original file
            area: Area name
            site: Site name
            chunk_path: Path to chunk file if applicable
        """
        rel_path = os.path.relpath(file_path)
        key = f"{area}:{site}:{rel_path}"

        self.tracking_data[key] = {
            "file_path": file_path,
            "area": area,
            "site": site,
            "mtime": self._get_file_mtime(file_path),
            "hash": self._calculate_file_hash(file_path),
            "uploaded_at": datetime.now().isoformat(),
            "chunk_path": chunk_path,
        }

        self._save_tracking()

    def get_new_files(
        self, file_paths: list, area: str, site: str, force: bool = False
    ) -> list:
        """
        Filter file list to only include new or modified files

        Args:
            file_paths: List of file paths to check
            area: Area name
            site: Site name
            force: If True, return all files (ignore tracking)

        Returns:
            List of files that need to be uploaded
        """
        if force:
            print("-> Force mode enabled - will upload all files")
            return file_paths

        new_files = []
        for file_path in file_paths:
            if not self.is_file_uploaded(file_path, area, site):
                new_files.append(file_path)

        skipped_count = len(file_paths) - len(new_files)
        if skipped_count > 0:
            print(f"-> Skipping {skipped_count} already uploaded files")

        return new_files

    def clear_tracking(self, area: Optional[str] = None, site: Optional[str] = None):
        """
        Clear tracking data

        Args:
            area: If specified, only clear this area
            site: If specified (with area), only clear this site
        """
        if area is None:
            # Clear all
            self.tracking_data = {}
            print("-> Cleared all tracking data")
        elif site is None:
            # Clear all entries for this area
            keys_to_remove = [
                k for k in self.tracking_data.keys() if k.startswith(f"{area}:")
            ]
            for key in keys_to_remove:
                del self.tracking_data[key]
            print(f"-> Cleared tracking data for area: {area}")
        else:
            # Clear specific area/site
            keys_to_remove = [
                k for k in self.tracking_data.keys() if k.startswith(f"{area}:{site}:")
            ]
            for key in keys_to_remove:
                del self.tracking_data[key]
            print(f"-> Cleared tracking data for {area}:{site}")

        self._save_tracking()

    def print_stats(self):
        """Print tracking statistics"""
        if not self.tracking_data:
            print("-> No files tracked yet")
            return

        areas = {}
        for key in self.tracking_data.keys():
            area = key.split(":")[0]
            areas[area] = areas.get(area, 0) + 1

        print(f"\n=== Upload Tracking Statistics ===")
        print(f"Total files tracked: {len(self.tracking_data)}")
        print(f"\nBy Area:")
        for area, count in sorted(areas.items()):
            print(f"  {area.title()}: {count} files")
        print("=" * 50)
