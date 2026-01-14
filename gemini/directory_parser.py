"""
Directory Parser - Parse area/site directory structure and collect files
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class DirectoryParser:
    """Parse directory structure for area/site hierarchy"""

    def __init__(self, content_root: str, supported_formats: List[str]):
        """
        Initialize directory parser

        Args:
            content_root: Root directory containing area/site structure
            supported_formats: List of supported file extensions (e.g., ['.txt', '.md'])
        """
        self.content_root = content_root
        self.supported_formats = [fmt.lower() for fmt in supported_formats]

    def parse_directory_structure(self) -> Dict[Tuple[str, str], List[str]]:
        """
        Parse directory structure to extract area/site mapping and files

        Expected structure:
            content_root/
                Area1/
                    Site1/
                        file1.txt
                        file2.md
                    Site2/
                        file3.txt
                Area2/
                    Site3/
                        file4.txt

        Returns:
            Dict mapping (area, site) tuples to lists of file paths
        """
        if not os.path.exists(self.content_root):
            raise FileNotFoundError(f"Content root not found: {self.content_root}")

        result = {}

        # Walk through area directories
        logger.debug(f"Scanning content root: {self.content_root}")
        areas = os.listdir(self.content_root)
        logger.debug(f"Found {len(areas)} potential areas")

        for area_name in areas:
            area_path = os.path.join(self.content_root, area_name)

            if not os.path.isdir(area_path):
                logger.debug(f"Skipping non-directory: {area_name}")
                continue

            logger.debug(f"Scanning area: {area_name}")

            # Walk through site directories within area
            sites = os.listdir(area_path)
            logger.debug(f"Found {len(sites)} potential sites")

            for site_name in sites:
                site_path = os.path.join(area_path, site_name)

                if not os.path.isdir(site_path):
                    logger.debug(f"Skipping non-directory: {site_name}")
                    continue

                logger.debug(f"Scanning site: {site_name}")

                # Collect supported files from this site
                files = self._collect_files(site_path)

                if files:
                    logger.debug(f"Found {len(files)} supported files")
                    result[(area_name, site_name)] = files
                else:
                    logger.debug(f"No supported files found")

        return result

    def _collect_files(self, directory: str) -> List[str]:
        """
        Recursively collect supported files from a directory

        Args:
            directory: Directory to scan

        Returns:
            List of file paths
        """
        files = []

        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                # Skip Word temp files (start with ~$)
                if filename.startswith('~$'):
                    continue

                file_path = os.path.join(root, filename)
                file_ext = os.path.splitext(filename)[1].lower()

                if file_ext in self.supported_formats:
                    files.append(file_path)

        return files

    def get_area_site_from_path(self, file_path: str) -> Tuple[str, str]:
        """
        Extract area and site names from a file path

        Args:
            file_path: Full path to file

        Returns:
            Tuple of (area, site)
        """
        rel_path = os.path.relpath(file_path, self.content_root)
        parts = Path(rel_path).parts

        if len(parts) < 2:
            raise ValueError(f"Invalid file path structure: {file_path}")

        area = parts[0]
        site = parts[1]

        return area, site

    def print_structure(self):
        """Print the parsed directory structure"""
        structure = self.parse_directory_structure()

        if not structure:
            logger.info("No valid area/site structure found")
            return

        logger.info("Content Structure")
        logger.info(f"Content Root: {self.content_root}")
        logger.info(f"Found {len(structure)} area/site combinations")

        for (area, site), files in sorted(structure.items()):
            logger.info(f"{area} / {site}")
            logger.debug(f"  Files: {len(files)}")
            for file in files[:3]:  # Show first 3 files
                logger.debug(f"  - {os.path.basename(file)}")
            if len(files) > 3:
                logger.debug(f"  ... and {len(files) - 3} more")
