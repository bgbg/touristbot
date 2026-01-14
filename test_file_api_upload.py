#!/usr/bin/env python3
"""Test image upload to Gemini File API"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import google.genai as genai

from gemini.config import GeminiConfig
from gemini.image_extractor import extract_images_from_docx
from gemini.file_api_manager import FileAPIManager

print("=" * 70)
print("Testing Image Upload to Gemini File API")
print("=" * 70)
print()

# Load configuration
try:
    config = GeminiConfig.from_yaml()
    print(f"✓ Config loaded")
    print()
except Exception as e:
    print(f"❌ Error loading config: {e}")
    sys.exit(1)

# Connect to Gemini
try:
    client = genai.Client(api_key=config.api_key)
    print(f"✓ Connected to Gemini API")
    print()
except Exception as e:
    print(f"❌ Error connecting to Gemini: {e}")
    sys.exit(1)

# Extract images from sample DOCX
docx_path = "data/locations/hefer_valley/agamon_hefer/אגמון חפר.docx"

print(f"Extracting images from: {docx_path}")
try:
    images = extract_images_from_docx(docx_path)
    print(f"✓ Extracted {len(images)} image(s)")
    print()
except Exception as e:
    print(f"❌ Error extracting images: {e}")
    sys.exit(1)

# Initialize File API manager
file_api = FileAPIManager(client)

# Upload images
area = "hefer_valley"
site = "agamon_hefer"
doc = "agamon_hefer_test"

print(f"Uploading images to Gemini File API...")
print(f"  Area: {area}")
print(f"  Site: {site}")
print(f"  Doc: {doc}")
print()

try:
    uploaded = file_api.upload_images_from_extraction(
        images=images, area=area, site=site, doc=doc
    )

    print()
    print(f"✓ Uploaded {len(uploaded)} image(s) to File API")
    print()

    for image_index, file_uri, file_name, caption in uploaded:
        print(f"Image {image_index}:")
        print(f"  File URI: {file_uri}")
        print(f"  File Name: {file_name}")
        print(f"  Caption: {caption}")
        print()

        # Verify file exists
        try:
            file_obj = file_api.get_file(file_name)
            print(f"  ✓ Verified: State = {file_obj.state.name}")
        except Exception as e:
            print(f"  ❌ Verification failed: {e}")

        print()

    print("✓ All images uploaded and verified successfully!")

except Exception as e:
    print(f"❌ Error uploading images: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
