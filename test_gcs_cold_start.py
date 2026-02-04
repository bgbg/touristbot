#!/usr/bin/env python3
"""
Test GCS cold start hypothesis.

Downloads the same image multiple times to see if:
- First access is slow (cold start)
- Subsequent accesses are fast (warmed up)
"""

import time
import urllib.request
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests


def download_image(url: str) -> tuple[int, float]:
    """Download image and return size and time."""
    start = time.time()
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.getcode() != 200:
            raise Exception(f"Download failed with status {resp.getcode()}")
        data = resp.read()
    elapsed = time.time() - start
    return len(data), elapsed


def main():
    print("Testing GCS Cold Start Hypothesis")
    print("="*60)

    # Load API key
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    api_key = os.getenv("BACKEND_API_KEY", "")
    if not api_key:
        print("Error: BACKEND_API_KEY required")
        sys.exit(1)

    # Get a test image URL
    print("\n1. Fetching test image URL from backend...")
    backend_url = "https://tourism-rag-backend-347968285860.me-west1.run.app/qa"
    payload = {
        "area": "עמק חפר",
        "site": "אגמון חפר",
        "query": "תמונות של האגמון"
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    resp = requests.post(backend_url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if not result.get("images"):
        print("No images returned")
        sys.exit(1)

    # Find all images and their sizes
    print(f"\n   Found {len(result['images'])} images. Checking sizes...")

    # Download each image once to check size
    largest_image = None
    largest_size = 0

    for img in result["images"]:
        try:
            # Quick HEAD request to check size
            head_resp = requests.head(img["uri"], timeout=10)
            content_length = int(head_resp.headers.get('content-length', 0))
            size_mb = content_length / (1024 * 1024)

            print(f"   - {img['caption'][:40]}: {size_mb:.2f}MB")

            if content_length > largest_size:
                largest_size = content_length
                largest_image = img
        except Exception as e:
            print(f"   - Failed to check: {e}")
            continue

    if not largest_image:
        print("\n   No valid images found")
        sys.exit(1)

    test_image = largest_image
    image_url = test_image["uri"]
    size_mb = largest_size / (1024 * 1024)

    print(f"\n   Testing with LARGEST image ({size_mb:.2f}MB):")
    print(f"   Caption: {test_image['caption'][:50]}...")
    print(f"   URL: {image_url[:80]}...")

    # Download the same image 5 times
    print(f"\n2. Downloading same image 5 times...")
    print("   (If cold start: first should be slow, rest should be fast)")
    print()

    times = []
    sizes = []

    for i in range(5):
        try:
            size, elapsed = download_image(image_url)
            times.append(elapsed)
            sizes.append(size)
            size_mb = size / (1024 * 1024)
            speed = size_mb / elapsed

            status = "⏱️  SLOW" if elapsed > 1.0 else "✓ FAST"
            print(f"   #{i+1}: {elapsed:.2f}s ({size_mb:.2f}MB @ {speed:.2f}MB/s) {status}")

            # Small delay between requests
            time.sleep(0.5)
        except Exception as e:
            print(f"   #{i+1}: FAILED - {e}")
            times.append(None)
            sizes.append(None)

    # Analyze results
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)

    valid_times = [t for t in times if t is not None]
    if len(valid_times) < 2:
        print("Not enough successful downloads to analyze")
        return

    first_time = times[0]
    avg_subsequent = sum(times[1:]) / len(times[1:])

    print(f"\nFirst download:       {first_time:.2f}s")
    print(f"Subsequent average:   {avg_subsequent:.2f}s")

    if first_time > avg_subsequent * 2:
        speedup = first_time / avg_subsequent
        print(f"\n✓ COLD START DETECTED!")
        print(f"  First download is {speedup:.1f}x slower than subsequent ones")
        print(f"  This suggests GCS blob access has significant cold start latency")
    elif first_time > 1.0:
        print(f"\n⚠️  ALL DOWNLOADS ARE SLOW")
        print(f"  This suggests network issues or GCS throttling")
        print(f"  Not a cold start issue - consistent slow performance")
    else:
        print(f"\n✓ NO COLD START ISSUE")
        print(f"  All downloads are fast and consistent")

    # Additional test: Download from local environment vs Cloud Run
    print("\n" + "="*60)
    print("ENVIRONMENT")
    print("="*60)
    print(f"Running from: Local machine")
    print(f"Target: GCS bucket in me-west1")
    print(f"\nNote: Production Cloud Run (also in me-west1) should have")
    print(f"      faster access. This test shows cold start behavior,")
    print(f"      but production latency may differ.")


if __name__ == "__main__":
    main()
