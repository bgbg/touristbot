import os
os.environ["BACKEND_API_KEYS"] = "d7fa3b1107a69835d969b850377ccb2b92c244c583a63f0ada3066eed0924095"
os.environ["GCS_BUCKET"] = "tarasa_tourist_bot_content"  
os.environ["GOOGLE_API_KEY"] = "test"

from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
try:
    response = client.post(
        "/qa",
        headers={"Authorization": "Bearer d7fa3b1107a69835d969b850377ccb2b92c244c583a63f0ada3066eed0924095"},
        json={"area": "hefer_valley", "site": "agamon_hefer", "query": "hello"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
