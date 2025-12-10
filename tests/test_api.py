"""
Tests for API endpoints
"""
import pytest

class TestAPIEndpoints:
    """Test API endpoints"""

    def test_get_active_token(self, test_client, auth_headers):
        """Test getting active token for location"""
        response = test_client.get("/api/active_token/office_main", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "token" in data
        assert "url" in data
        assert len(data["token"]) > 0
        assert "qr_uchet_bot" in data["url"]

    def test_get_active_token_unauthorized(self, test_client):
        """Test getting token without authentication"""
        response = test_client.get("/api/active_token/office_main")
        assert response.status_code == 401

    def test_get_active_token_invalid_location(self, test_client, auth_headers):
        """Test getting token for invalid location"""
        response = test_client.get("/api/active_token/invalid_location", headers=auth_headers)
        assert response.status_code == 404

    def test_create_user_admin_only(self, test_client, auth_headers):
        """Test creating user (admin only)"""
        new_user_data = {
            "username": "testmanager",
            "password": "securepass123",
            "full_name": "Test Manager",
            "role": "manager"
        }

        response = test_client.post("/api/admin/users", json=new_user_data, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "user_id" in data

    def test_create_user_duplicate_username(self, test_client, auth_headers):
        """Test creating user with existing username"""
        duplicate_user_data = {
            "username": "admin",  # Admin already exists
            "password": "somepass",
            "full_name": "Duplicate Admin",
            "role": "user"
        }

        response = test_client.post("/api/admin/users", json=duplicate_user_data, headers=auth_headers)
        # Should fail due to unique constraint
        assert response.status_code == 400

    def test_get_users_admin_only(self, test_client, auth_headers):
        """Test getting all users (admin only)"""
        response = test_client.get("/api/admin/users", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "users" in data
        assert isinstance(data["users"], list)
        assert len(data["users"]) >= 1  # At least admin user

        # Check admin user exists
        admin_user = None
        for user in data["users"]:
            if user["username"] == "admin":
                admin_user = user
                break

        assert admin_user is not None
        assert admin_user["role"] == "admin"

    def test_web_interface_endpoints(self, test_client):
        """Test web interface endpoints"""
        # Login page should be accessible without auth
        response = test_client.get("/login")
        assert response.status_code == 200
        assert "login" in response.text.lower()

        # Protected pages should redirect to login
        response = test_client.get("/terminal", allow_redirects=False)
        assert response.status_code == 302  # Redirect
        assert "/login" in response.headers.get("location", "")

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
