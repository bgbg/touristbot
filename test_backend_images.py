#!/usr/bin/env python3
"""Test backend QA endpoint to debug image display"""

import requests
import json

BACKEND_URL = "http://localhost:8001"
API_KEY = "d7fa3b1107a69835d969b850377ccb2b92c244c583a63f0ada3066eed0924095"

# Test query about images
payload = {
    "conversation_id": "test_img_debug",
    "area": "עמק חפר",
    "site": "אגמון חפר",
    "query": "יש פה תמונות של שקנאים?"
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

print("Testing backend QA endpoint...")
print(f"Query: {payload['query']}")
print(f"Location: {payload['area']}/{payload['site']}\n")

response = requests.post(f"{BACKEND_URL}/qa", json=payload, headers=headers, timeout=60)

if response.status_code == 200:
    data = response.json()
    print(f"✓ Backend responded")
    print(f"  should_include_images: {data.get('should_include_images')}")
    print(f"  images_count: {len(data.get('images', []))}")
    print(f"  response_text length: {len(data.get('response_text', ''))}")
    print(f"\nResponse preview:")
    print(f"  {data.get('response_text', '')[:200]}...")

    if data.get('images'):
        print(f"\nImages:")
        for i, img in enumerate(data['images'][:3], 1):
            print(f"  {i}. Caption: {img.get('caption', 'No caption')[:50]}")
            print(f"     Relevance: {img.get('relevance_score', 'N/A')}")
    else:
        print("\n⚠️  No images returned!")
        print("  This is the problem - images exist in registry but backend isn't returning them")
else:
    print(f"✗ Backend error: {response.status_code}")
    print(f"  {response.text}")
