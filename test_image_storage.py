#!/usr/bin/env python3
"""Test image storage to GCS"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini.config import GeminiConfig
from gemini.image_extractor import extract_images_from_docx
from gemini.image_storage import ImageStorage

print("=" * 70)
print("Testing Image Storage to GCS")
print("=" * 70)
print()

# Load configuration
try:
    config = GeminiConfig.from_yaml()
    print(f"✓ Config loaded")
    print(f"  GCS Bucket: {config.gcs_bucket_name}")
    print()
except Exception as e:
    print(f"❌ Error loading config: {e}")
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

# Initialize image storage
try:
    image_storage = ImageStorage(
        bucket_name=config.gcs_bucket_name,
        credentials_json=config.gcs_credentials_json,
    )
    print(f"✓ Connected to GCS bucket: {config.gcs_bucket_name}")
    print()
except Exception as e:
    print(f"❌ Error connecting to GCS: {e}")
    sys.exit(1)

# Upload images
area = "hefer_valley"
site = "agamon_hefer"
doc = "agamon_hefer_test"

print(f"Uploading images to GCS...")
print(f"  Area: {area}")
print(f"  Site: {site}")
print(f"  Doc: {doc}")
print()

try:
    uploaded = image_storage.upload_images_from_extraction(
        images=images,
        area=area,
        site=site,
        doc=doc,
        make_public=False,  # Keep private for now
    )

    print(f"✓ Uploaded {len(uploaded)} image(s)")
    print()

    for i, (gcs_path, url) in enumerate(uploaded, 1):
        print(f"Image {i}:")
        print(f"  GCS Path: {gcs_path}")
        print(f"  URI: {url}")

        # Verify image exists
        exists = image_storage.image_exists(gcs_path)
        print(f"  Exists: {'✓ Yes' if exists else '❌ No'}")
        print()

    print("✓ All images uploaded successfully!")

except Exception as e:
    print(f"❌ Error uploading images: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
