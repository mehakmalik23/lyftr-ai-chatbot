import os
import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

os.environ["LLM_API_KEYS"] = "test_key_alpha,test_key_beta"
os.environ["DATABASE_URL"] = "sqlite:////tmp/test_lyftr_app.db"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"

import litellm
from app.main import app
from app.database import init_db

@pytest.fixture(autouse=True)
def clean_env_and_cache(monkeypatch):
    if os.path.exists("/tmp/test_lyftr_app.db"):
        os.remove("/tmp/test_lyftr_app.db")
    init_db()
    from litellm.caching.caching import Cache
    litellm.cache = Cache(type="local")

    def fake_completion(model, messages, api_key, **kwargs):
        user_msg = messages[-1]["content"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=f"Echo: {user_msg}"))],
            usage=SimpleNamespace(prompt_tokens=25, completion_tokens=8)
        )

    monkeypatch.setattr(litellm, "completion", fake_completion)
    yield

client = TestClient(app)

def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["keys_configured"] == 2
    assert data["cache_enabled"] is True

def test_live_inference_and_cross_session_cache():
    # First call in session 1 -> LIVE_INFERENCE
    r1 = client.post("/chat", json={"session_id": "s-1", "message": "What is the capital of France?"})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert d1["metadata"]["key_id"] == "key_1"
    assert d1["metadata"]["fallback_attempts"] == 0
    assert d1["metadata"]["input_tokens"] == 25
    assert d1["metadata"]["output_tokens"] == 8

    # Identical first message in a NEW session -> LLM_CACHE with key_id=None and fallback_attempts=0
    r2 = client.post("/chat", json={"session_id": "s-2", "message": "What is the capital of France?"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["reply"] == d1["reply"]
    assert d2["metadata"]["resolution_source"] == "LLM_CACHE"
    assert d2["metadata"]["key_id"] is None
    assert d2["metadata"]["fallback_attempts"] == 0

def test_failover_simulation_hook():
    # Simulate key_1=429 -> should succeed on key_2 with fallback_attempts=1
    r = client.post(
        "/chat",
        json={"session_id": "s-failover", "message": "Test key 1 rate limit"},
        headers={"X-Simulate-Failure": "key_1=429"}
    )
    assert r.status_code == 200
    meta = r.json()["metadata"]
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["key_id"] == "key_2"
    assert meta["fallback_attempts"] == 1

def test_all_keys_fail_503_and_not_saved():
    r = client.post(
        "/chat",
        json={"session_id": "s-503", "message": "All keys down"},
        headers={"X-Simulate-Failure": "*=429"}
    )
    assert r.status_code == 503
    assert r.json() == {"detail": "all providers unavailable"}

    # Failed request must NOT create session history
    h = client.get("/sessions/s-503/messages")
    assert h.status_code == 404
    assert h.json() == {"detail": "session not found"}

def test_validation_422():
    # Empty whitespace message -> 422
    r = client.post("/chat", json={"session_id": "s-422", "message": "    "})
    assert r.status_code == 422
    assert "detail" in r.json()
