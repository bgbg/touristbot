"""
Image Extraction Module for DOCX Files

Extracts images from MS Word documents along with their captions and context.
Handles Hebrew text and RTL content correctly.
"""

import io
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from docx import Document
from docx.oxml import CT_Blip
from docx.oxml.xmlchemy import BaseOxmlElement


@dataclass
class ExtractedImage:
    """Represents an extracted image with its metadata"""

    image_data: bytes
    image_format: str  # 'png', 'jpeg', 'jpg', etc.
    caption: str
    context_before: str
    context_after: str
    paragraph_index: int  # Index in document for reference


class ImageExtractor:
    """Extracts images and metadata from DOCX files"""

    def __init__(self, docx_path: str):
        """
        Initialize image extractor

        Args:
            docx_path: Path to DOCX file
        """
        self.docx_path = docx_path
        self.document = Document(docx_path)

    def extract_images(self) -> List[ExtractedImage]:
        """
        Extract all images from DOCX file with captions and context

        Returns:
            List of ExtractedImage objects

        Raises:
            ValueError: If DOCX file cannot be parsed
        """
        extracted_images = []

        # Iterate through paragraphs to find images
        for i, paragraph in enumerate(self.document.paragraphs):
            # Check if paragraph contains images (via runs)
            for run in paragraph.runs:
                # Look for inline images in the run's XML using findall with full namespace
                drawings = run._element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')

                for drawing in drawings:
                    pics = drawing.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/picture}pic')

                    for shape in pics:
                        # Extract image data from relationship
                        image_data, image_format = self._extract_image_data(shape)

                        if image_data:
                            # Extract caption (next paragraph after image)
                            caption = self._get_caption(i)

                            # Extract context paragraphs
                            context_before = self._get_paragraph_text(i - 1)
                            # Skip the caption paragraph when getting context after
                            context_after = self._get_paragraph_text(i + 2)

                            extracted_images.append(
                                ExtractedImage(
                                    image_data=image_data,
                                    image_format=image_format,
                                    caption=caption,
                                    context_before=context_before,
                                    context_after=context_after,
                                    paragraph_index=i,
                                )
                            )

        return extracted_images

    def _extract_image_data(self, pic_element: BaseOxmlElement) -> Tuple[Optional[bytes], str]:
        """
        Extract image binary data and format from picture element

        Args:
            pic_element: Picture XML element

        Returns:
            Tuple of (image_data, format) or (None, "") if extraction fails
        """
        try:
            # Find the blip element (contains image reference) using findall
            blips = pic_element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')

            if not blips:
                return None, ""

            blip = blips[0]

            # Get the relationship ID
            embed_id = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")

            if not embed_id:
                return None, ""

            # Get the image part from the document relationships
            image_part = self.document.part.related_parts[embed_id]

            # Extract image data and format
            image_data = image_part.blob
            image_format = image_part.content_type.split('/')[-1]  # e.g., 'image/jpeg' -> 'jpeg'

            # Normalize format
            if image_format == 'jpeg':
                image_format = 'jpg'

            return image_data, image_format

        except Exception as e:
            print(f"Warning: Could not extract image data: {e}")
            return None, ""

    def _get_caption(self, image_paragraph_index: int) -> str:
        """
        Get caption for image (paragraph immediately after image)

        Args:
            image_paragraph_index: Index of paragraph containing image

        Returns:
            Caption text or empty string
        """
        caption_index = image_paragraph_index + 1

        if caption_index < len(self.document.paragraphs):
            caption = self.document.paragraphs[caption_index].text.strip()
            return caption

        return ""

    def _get_paragraph_text(self, index: int) -> str:
        """
        Get text of paragraph at index

        Args:
            index: Paragraph index

        Returns:
            Paragraph text or empty string if out of bounds
        """
        if 0 <= index < len(self.document.paragraphs):
            return self.document.paragraphs[index].text.strip()

        return ""

    def save_images(
        self, images: List[ExtractedImage], output_dir: str, base_name: str = "image"
    ) -> List[str]:
        """
        Save extracted images to disk with sequential naming

        Args:
            images: List of ExtractedImage objects
            output_dir: Directory to save images
            base_name: Base name for files (default: "image")

        Returns:
            List of saved file paths

        Raises:
            OSError: If directory creation or file writing fails
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        saved_paths = []

        for i, image in enumerate(images, 1):
            # Generate filename: image_001.jpg, image_002.png, etc.
            filename = f"{base_name}_{i:03d}.{image.image_format}"
            filepath = os.path.join(output_dir, filename)

            # Write image data to file
            with open(filepath, 'wb') as f:
                f.write(image.image_data)

            saved_paths.append(filepath)

        return saved_paths


def extract_images_from_docx(
    docx_path: str, output_dir: Optional[str] = None
) -> List[ExtractedImage]:
    """
    Convenience function to extract images from DOCX file

    Args:
        docx_path: Path to DOCX file
        output_dir: Optional directory to save images

    Returns:
        List of ExtractedImage objects

    Example:
        >>> images = extract_images_from_docx('document.docx', 'output/images')
        >>> for img in images:
        ...     print(f"Caption: {img.caption}")
        ...     print(f"Format: {img.image_format}")
    """
    extractor = ImageExtractor(docx_path)
    images = extractor.extract_images()

    if output_dir:
        extractor.save_images(images, output_dir)

    return images
