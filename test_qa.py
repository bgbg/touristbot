import requests
import json

response = requests.post(
    "http://127.0.0.1:8001/qa",
    headers={
        "Authorization": "Bearer d7fa3b1107a69835d969b850377ccb2b92c244c583a63f0ada3066eed0924095",
        "Content-Type": "application/json"
    },
    json={"area": "hefer_valley", "site": "agamon_hefer", "query": "hello"},
    timeout=30
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")
