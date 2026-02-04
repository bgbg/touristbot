#!/usr/bin/env python3
"""
Test image download performance: urllib vs requests.

This script measures the time to download a 5MB image from GCS
using both urllib (current implementation) and requests library.
"""

import time
import urllib.request
import requests
import sys


def download_with_urllib(url: str) -> tuple[bytes, float]:
    """Download using urllib (current implementation)."""
    start = time.time()
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.getcode() != 200:
            raise Exception(f"Download failed with status {resp.getcode()}")
        data = resp.read()
    elapsed = time.time() - start
    return data, elapsed


def download_with_requests(url: str) -> tuple[bytes, float]:
    """Download using requests library."""
    start = time.time()
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.content
    elapsed = time.time() - start
    return data, elapsed


def main():
    # Get image URL from backend to test with real GCS signed URL
    print("Fetching test image URL from backend...")

    # Load from .env file
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    # Try to load from .env
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Use a test query to get an image URL
    backend_url = "https://tourism-rag-backend-347968285860.me-west1.run.app/qa"
    api_key = os.getenv("BACKEND_API_KEY", "")

    if not api_key:
        print("Error: BACKEND_API_KEY required (set in .env file)")
        sys.exit(1)

    # Query to get images
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
        print("No images returned from backend")
        sys.exit(1)

    # Get first large image (ideally 5MB)
    test_image = None
    for img in result["images"]:
        print(f"Found image: {img['caption'][:50]}...")
        test_image = img
        break

    if not test_image or not test_image.get("uri"):
        print("No suitable test image found")
        sys.exit(1)

    image_url = test_image["uri"]
    print(f"\nTest image URL: {image_url[:80]}...")

    # Run tests
    print("\n" + "="*60)
    print("PERFORMANCE TEST: urllib vs requests")
    print("="*60)

    # Test urllib (current implementation)
    print("\n1. Testing urllib.request.urlopen() [CURRENT]...")
    try:
        data_urllib, time_urllib = download_with_urllib(image_url)
        size_mb = len(data_urllib) / (1024 * 1024)
        print(f"   ✓ Downloaded {size_mb:.2f}MB in {time_urllib:.2f}s")
        print(f"   ✓ Speed: {size_mb/time_urllib:.2f} MB/s")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        time_urllib = None

    # Test requests
    print("\n2. Testing requests.get() [PROPOSED]...")
    try:
        data_requests, time_requests = download_with_requests(image_url)
        size_mb = len(data_requests) / (1024 * 1024)
        print(f"   ✓ Downloaded {size_mb:.2f}MB in {time_requests:.2f}s")
        print(f"   ✓ Speed: {size_mb/time_requests:.2f} MB/s")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        time_requests = None

    # Compare
    if time_urllib and time_requests:
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        improvement = ((time_urllib - time_requests) / time_urllib) * 100
        speedup = time_urllib / time_requests

        print(f"urllib:   {time_urllib:.2f}s")
        print(f"requests: {time_requests:.2f}s")
        print(f"\nImprovement: {improvement:.1f}% faster ({speedup:.2f}x speedup)")

        if improvement < 10:
            print("\n⚠️  WARNING: Less than 10% improvement!")
            print("   The slow download is likely due to network/GCS issues,")
            print("   not the HTTP library choice.")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
