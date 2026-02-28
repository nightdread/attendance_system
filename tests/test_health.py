import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("BOT_TOKEN", "test-bot-token")
os.environ.setdefault("BOT_USERNAME", "test_bot")
os.environ.setdefault("WEB_PASSWORD", "test-password")

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from auth.jwt_handler import JWTHandler  # noqa: E402

client = TestClient(app)


def _auth_headers():
    token = JWTHandler.create_access_token(data={"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data.get("timestamp")


def test_active_token():
    # /api/active_token требует авторизацию (JWT или сессию)
    resp = client.get("/api/active_token", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data and data["token"]
    assert "url" in data and "t.me" in data["url"]

