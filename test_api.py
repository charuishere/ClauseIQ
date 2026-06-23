from fastapi.testclient import TestClient
import os
os.environ["S3_BUCKET_NAME"] = "test"
os.environ["DYNAMODB_TABLE_NAME"] = "test"
os.environ["PINECONE_SECRET_ARN"] = "test"
import sys
sys.path.append(os.path.abspath("api"))
from api.main import app
from api.auth import get_current_user

app.dependency_overrides[get_current_user] = lambda: {"userId": "test"}

client = TestClient(app)
try:
    response = client.post("/agreements/123/chat", json={"question": "hello"})
    print(response.status_code)
    print(response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
