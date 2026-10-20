import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_ecoroute.db"
os.environ["GRAPH_PATH"] = "does-not-exist.graphml"   # force demo graph
os.environ["LLM_PROVIDER"] = "none"
os.environ["N8N_WEBHOOK_URL"] = ""
os.environ["UPLOAD_DIR"] = "test_uploads"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def client():
    if os.path.exists("test_ecoroute.db"):
        os.remove("test_ecoroute.db")
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c
