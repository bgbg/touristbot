#!/usr/bin/env python3
"""Test image registry system"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini.image_registry import ImageRegistry

print("=" * 70)
print("Testing Image Registry")
print("=" * 70)
print()

# Use a test registry file
test_registry_path = "test_image_registry.json"

# Clean up if exists
if os.path.exists(test_registry_path):
    os.remove(test_registry_path)

# Initialize registry
registry = ImageRegistry(test_registry_path)

print("✓ Initialized empty registry")
print()

# Add test images
print("Adding test images...")

image1_key = registry.add_image(
    area="hefer_valley",
    site="agamon_hefer",
    doc="agamon_hefer_test",
    image_index=1,
    caption="שקנאי – ציפור נודדת שאוהבת לחנות באגמון",
    context_before="צומת אווירי: ישראל נחשבת לצוואר בקבוק עולמי בנדידת ציפורים",
    context_after="שקנאים חיים בקבוצות של 20-200 פריטים",
    gcs_path="images/hefer_valley/agamon_hefer/agamon_hefer_test/image_001.jpg",
    file_api_uri="https://generativelanguage.googleapis.com/v1beta/files/test123",
    file_api_name="files/test123",
    image_format="jpg",
)

print(f"  ✓ Added image 1: {image1_key}")

image2_key = registry.add_image(
    area="hefer_valley",
    site="agamon_hefer",
    doc="agamon_hefer_test",
    image_index=2,
    caption="נוף האגמון בשקיעה",
    context_before="האגמון מציע נופים מרהיבים",
    context_after="מומלץ להגיע לקראת שקיעה",
    gcs_path="images/hefer_valley/agamon_hefer/agamon_hefer_test/image_002.jpg",
    file_api_uri="https://generativelanguage.googleapis.com/v1beta/files/test456",
    file_api_name="files/test456",
    image_format="jpg",
)

print(f"  ✓ Added image 2: {image2_key}")
print()

# Test retrieval by location
print("Retrieving images for location...")
images = registry.get_images_for_location("hefer_valley", "agamon_hefer", "agamon_hefer_test")

print(f"  ✓ Found {len(images)} image(s)")
for img in images:
    print(f"    - Image {img.image_index}: {img.caption}")
print()

# Test retrieval by key
print("Retrieving image by key...")
img = registry.get_image(image1_key)
if img:
    print(f"  ✓ Found image: {img.caption}")
    print(f"    GCS Path: {img.gcs_path}")
    print(f"    File API URI: {img.file_api_uri}")
print()

# Test search by caption
print("Searching by caption...")
results = registry.search_by_caption("שקנאי")
print(f"  ✓ Found {len(results)} image(s) matching 'שקנאי'")
for img in results:
    print(f"    - {img.caption}")
print()

# Test stats
print("Registry statistics...")
stats = registry.get_stats()
print(f"  Total images: {stats['total_images']}")
print(f"  Unique areas: {stats['unique_areas']}")
print(f"  Unique sites: {stats['unique_sites']}")
print(f"  Unique docs: {stats['unique_docs']}")
print(f"  Locations: {stats['locations']}")
print()

# Verify file was created
if os.path.exists(test_registry_path):
    print(f"✓ Registry file created: {test_registry_path}")
    print()

    # Show file contents
    import json
    with open(test_registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        print("Registry contents (first record):")
        first_key = list(data.keys())[0]
        print(f"  Key: {first_key}")
        print(f"  Data: {json.dumps(data[first_key], ensure_ascii=False, indent=4)}")

print()
print("✓ All tests passed!")

# Clean up test file
os.remove(test_registry_path)
print(f"\n✓ Cleaned up test file")
