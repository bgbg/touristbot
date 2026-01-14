#!/usr/bin/env python3
"""Test image extraction from sample DOCX file"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini.image_extractor import extract_images_from_docx

# Test with the sample DOCX
docx_path = "data/locations/hefer_valley/agamon_hefer/אגמון חפר.docx"
output_dir = "test_extracted_images"

print("=" * 70)
print("Testing Image Extraction from DOCX")
print("=" * 70)
print(f"\nDOCX File: {docx_path}")
print(f"Output Directory: {output_dir}")
print()

try:
    # Extract images
    images = extract_images_from_docx(docx_path, output_dir)

    print(f"✓ Extracted {len(images)} image(s)")
    print()

    # Display details
    for i, img in enumerate(images, 1):
        print(f"Image {i}:")
        print(f"  Format: {img.image_format}")
        print(f"  Size: {len(img.image_data)} bytes ({len(img.image_data) / 1024:.1f} KB)")
        print(f"  Caption: {img.caption}")
        print(f"  Context Before: {img.context_before[:100]}..." if len(img.context_before) > 100 else f"  Context Before: {img.context_before}")
        print(f"  Context After: {img.context_after[:100]}..." if len(img.context_after) > 100 else f"  Context After: {img.context_after}")
        print(f"  Paragraph Index: {img.paragraph_index}")
        print()

    print(f"✓ Images saved to: {output_dir}/")
    print("\nDone!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
