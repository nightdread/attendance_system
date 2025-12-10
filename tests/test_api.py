"""
Tests for API endpoints
"""
import pytest

class TestAPIEndpoints:
    """Test API endpoints"""

    def test_get_active_token(self, test_client, auth_headers):
        """Test getting active token (authorized)"""
        response = test_client.get("/api/active_token", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "token" in data
        assert "url" in data
        assert len(data["token"]) > 0

    def test_web_interface_endpoints(self, test_client):
        """Test web interface endpoints"""
        # Login page should be accessible without auth
        response = test_client.get("/login")
        assert response.status_code == 200
        assert "login" in response.text.lower()

        # Терминал теперь публичный
        response = test_client.get("/terminal", allow_redirects=False)
        assert response.status_code == 200

        response = test_client.get("/admin", allow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers.get("location", "")

    def test_openapi_documentation(self, test_client):
        """Test OpenAPI documentation endpoints"""
        # OpenAPI JSON schema
        response = test_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "info" in schema
        assert schema["info"]["title"] == "Attendance System API"

        # Swagger UI
        response = test_client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

        # ReDoc
        response = test_client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()
