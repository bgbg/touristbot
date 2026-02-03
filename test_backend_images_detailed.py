#!/usr/bin/env python3
"""Test backend QA endpoint to see full LLM response"""

import requests
import json

BACKEND_URL = "http://localhost:8001"
API_KEY = "d7fa3b1107a69835d969b850377ccb2b92c244c583a63f0ada3066eed0924095"

# Test different queries
test_queries = [
    "מה הציפורים שאפשר לראות פה?",  # What birds can you see here?
    "יש פה שקנאים?",  # Are there storks here?
    "תראה לי תמונה של שקנאים",  # Show me a picture of storks
]

for query in test_queries:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)

    payload = {
        "conversation_id": f"test_img_{hash(query)}",
        "area": "עמק חפר",
        "site": "אגמון חפר",
        "query": query
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(f"{BACKEND_URL}/qa", json=payload, headers=headers, timeout=60)

    if response.status_code == 200:
        data = response.json()
        print(f"✓ should_include_images: {data.get('should_include_images')}")
        print(f"  images_count: {len(data.get('images', []))}")

        if data.get('images'):
            print(f"\n  Images returned:")
            for i, img in enumerate(data['images'][:2], 1):
                caption = img.get('caption', 'No caption')[:60]
                relevance = img.get('relevance_score', 'N/A')
                print(f"    {i}. {caption}... (relevance: {relevance})")
        else:
            print(f"  ⚠️ No images (even though query is about visual content)")

        print(f"\n  Response preview:")
        print(f"    {data.get('response_text', '')[:150]}...")
    else:
        print(f"✗ Error: {response.status_code}")
