"""
Upload helper - Simplified wrapper around upload functionality for Streamlit UI.

Note: This is a minimal MVP implementation that provides basic upload capability.
For production use, consider integrating more deeply with gemini/main_upload.py.
"""

import os
import subprocess
import tempfile
from typing import List, Tuple, Optional, Callable
from pathlib import Path

from gemini.config import GeminiConfig


class UploadManager:
    """
    Manages file uploads to File Search Store with progress tracking.

    MVP Implementation: Wraps CLI uploader subprocess for simplicity.
    Future: Refactor to use FileSearchStoreManager directly for better progress tracking.
    """

    def __init__(self, config: GeminiConfig):
        """
        Initialize upload manager.

        Args:
            config: Gemini configuration object
        """
        self.config = config

    def upload_files(
        self,
        file_paths: List[str],
        area: str,
        site: str,
        force: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict:
        """
        Upload files to File Search Store.

        MVP Implementation: Uses existing CLI uploader via subprocess.
        This provides immediate functionality while maintaining all existing logic.

        Args:
            file_paths: List of absolute file paths to upload
            area: Location area (e.g., "hefer_valley")
            site: Location site (e.g., "agamon_hefer")
            force: Force re-upload even if already uploaded
            progress_callback: Optional callback(current, total, message) for progress

        Returns:
            Dict with:
            - uploaded_count: Number of files uploaded
            - skipped_count: Number of files skipped
            - image_count: Number of images extracted (estimated)
            - topics_count: Number of topics generated (estimated)
            - errors: List of error messages
        """
        errors = []
        uploaded_count = 0
        skipped_count = 0

        # Validate files first
        valid_files, invalid_files = self.validate_files(file_paths)

        if invalid_files:
            errors.extend(invalid_files)

        if not valid_files:
            return {
                "uploaded_count": 0,
                "skipped_count": 0,
                "image_count": 0,
                "topics_count": 0,
                "errors": errors,
            }

        # Copy files directly to data/locations directory
        # This avoids needing a temp directory since the CLI uploader
        # reads from config.content_root (data/locations)
        from pathlib import Path
        import shutil

        project_root = Path(__file__).parent.parent
        target_dir = project_root / self.config.content_root / area / site
        target_dir.mkdir(parents=True, exist_ok=True)

        copied_files = []
        try:
            # Copy files to target location
            for file_path in valid_files:
                file_name = os.path.basename(file_path)
                target_file = target_dir / file_name

                # Copy file
                shutil.copy2(file_path, target_file)
                copied_files.append(str(target_file))

            if progress_callback:
                progress_callback(1, 4, f"Files staged: {len(valid_files)} file(s)")

            # Build CLI command
            # Use the existing main_upload.py script
            cmd = [
                "python",
                "gemini/main_upload.py",
                "--area", area,
                "--site", site,
            ]

            if force:
                cmd.append("--force")

            # Set environment
            env = os.environ.copy()

            if progress_callback:
                progress_callback(2, 4, f"Uploading to File Search Store...")

            # Run upload subprocess
            # Change to project root for proper imports
            result = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                env=env,
            )

            if progress_callback:
                progress_callback(3, 4, "Processing upload results...")

            # Parse output for metrics
            output = result.stdout + result.stderr

            if result.returncode == 0:
                uploaded_count = len(valid_files)
                # Estimate image/topics counts from output
                image_count = output.count("Uploaded image to GCS")
                topics_count = 1 if "topics generated" in output.lower() else 0
            else:
                # Show both stdout and stderr for debugging
                error_msg = f"Upload subprocess failed (return code {result.returncode})"
                if result.stderr:
                    error_msg += f"\nError output: {result.stderr}"
                if result.stdout:
                    error_msg += f"\nStandard output: {result.stdout}"
                errors.append(error_msg)
                skipped_count = len(valid_files)

            if progress_callback:
                progress_callback(4, 4, "Upload complete!")

            return {
                "uploaded_count": uploaded_count,
                "skipped_count": skipped_count,
                "image_count": image_count if uploaded_count > 0 else 0,
                "topics_count": topics_count if uploaded_count > 0 else 0,
                "errors": errors,
            }

        except subprocess.TimeoutExpired:
            errors.append("Upload timed out after 5 minutes")
            # Clean up copied files on timeout
            for file in copied_files:
                try:
                    os.remove(file)
                except Exception:
                    pass
            return {
                "uploaded_count": 0,
                "skipped_count": len(valid_files),
                "image_count": 0,
                "topics_count": 0,
                "errors": errors,
            }
        except Exception as e:
            errors.append(f"Upload error: {str(e)}")
            # Clean up copied files on error
            for file in copied_files:
                try:
                    os.remove(file)
                except Exception:
                    pass
            return {
                "uploaded_count": 0,
                "skipped_count": len(valid_files),
                "image_count": 0,
                "topics_count": 0,
                "errors": errors,
            }

    def validate_files(self, file_paths: List[str]) -> Tuple[List[str], List[str]]:
        """
        Validate files before upload.

        Args:
            file_paths: List of file paths to validate

        Returns:
            Tuple of (valid_files, invalid_files_with_reasons)
        """
        valid_files = []
        invalid_files = []

        supported_extensions = [".docx", ".pdf", ".txt", ".md"]
        max_file_size = 50 * 1024 * 1024  # 50 MB

        for file_path in file_paths:
            # Check file exists
            if not os.path.exists(file_path):
                invalid_files.append(f"{file_path}: File not found")
                continue

            # Check file is readable
            if not os.access(file_path, os.R_OK):
                invalid_files.append(f"{file_path}: File not readable")
                continue

            # Check extension
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in supported_extensions:
                invalid_files.append(
                    f"{file_path}: Unsupported format (supported: {', '.join(supported_extensions)})"
                )
                continue

            # Check file size
            try:
                file_size = os.path.getsize(file_path)
                if file_size > max_file_size:
                    invalid_files.append(
                        f"{file_path}: File too large ({file_size / 1024 / 1024:.1f} MB, max 50 MB)"
                    )
                    continue
                if file_size == 0:
                    invalid_files.append(f"{file_path}: File is empty")
                    continue
            except Exception as e:
                invalid_files.append(f"{file_path}: Cannot read file size: {str(e)}")
                continue

            valid_files.append(file_path)

        return valid_files, invalid_files
