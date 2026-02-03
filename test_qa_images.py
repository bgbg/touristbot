import requests
import json

response = requests.post(
    "http://127.0.0.1:8001/qa",
    headers={
        "Authorization": "Bearer d7fa3b1107a69835d969b850377ccb2b92c244c583a63f0ada3066eed0924095",
        "Content-Type": "application/json"
    },
    json={"area": "hefer_valley", "site": "agamon_hefer", "query": "Show me pictures of birds"},
    timeout=30
)

print(f"Status: {response.status_code}")
data = response.json()
print(f"Response text type: {type(data['response_text'])}")
print(f"Response text (first 200 chars): {data['response_text'][:200]}")
print(f"Should include images: {data.get('should_include_images')}")
print(f"Images count: {len(data.get('images', []))}")

# Check if response_text is a string (not dict)
if isinstance(data['response_text'], dict):
    print("\n❌ ERROR: response_text is a dict! Issue #43 NOT fixed!")
else:
    print("\n✅ SUCCESS: response_text is a string! Issue #43 appears fixed!")
