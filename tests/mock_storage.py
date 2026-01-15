"""
Mock storage backend for testing

Provides in-memory storage backend that implements StorageBackend interface
without requiring actual GCS connection.
"""

from typing import Dict, List
from gemini.storage import StorageBackend


class MockStorageBackend(StorageBackend):
    """In-memory storage backend for testing"""

    def __init__(self):
        """Initialize empty in-memory storage"""
        self.files: Dict[str, str] = {}

    def write_file(self, path: str, content: str) -> bool:
        """Write content to in-memory storage"""
        self.files[path] = content
        return True

    def read_file(self, path: str) -> str:
        """Read content from in-memory storage"""
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        return self.files[path]

    def list_files(self, path: str, pattern: str = "*") -> List[str]:
        """List files matching pattern"""
        # Simple implementation - just return all files with matching prefix
        if not path.endswith("/"):
            path = path + "/"

        matching_files = []
        for file_path in self.files.keys():
            if file_path.startswith(path):
                # Skip directory markers
                if file_path.endswith("/"):
                    continue

                # Simple pattern matching
                if pattern == "*":
                    matching_files.append(file_path)
                elif pattern.startswith("*."):
                    ext = pattern[1:]  # Remove *
                    if file_path.endswith(ext):
                        matching_files.append(file_path)

        return matching_files

    def delete_file(self, path: str) -> bool:
        """Delete file from in-memory storage"""
        if path in self.files:
            del self.files[path]
            return True
        return False

    def file_exists(self, path: str) -> bool:
        """Check if file exists in in-memory storage"""
        return path in self.files

    def clear(self):
        """Clear all files (utility for tests)"""
        self.files.clear()
