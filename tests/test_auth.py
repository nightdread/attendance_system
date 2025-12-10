"""
Tests for authentication system
"""
import pytest
from auth.jwt_handler import JWTHandler

class TestJWTHandler:
    """Test JWT token handling"""

    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123"

        # Hash password
        hashed = JWTHandler.get_password_hash(password)
        assert hashed != password
        assert len(hashed) > 0

        # Verify password
        assert JWTHandler.verify_password(password, hashed)
        assert not JWTHandler.verify_password("wrong_password", hashed)

    def test_token_creation_and_verification(self):
        """Test JWT token creation and verification"""
        test_data = {"sub": "testuser", "role": "admin"}

        # Create token
        token = JWTHandler.create_access_token(test_data)
        assert token is not None
        assert len(token) > 0

        # Verify token
        payload = JWTHandler.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_invalid_token(self):
        """Test invalid token handling"""
        assert JWTHandler.verify_token("invalid_token") is None
        assert JWTHandler.verify_token("") is None

    def test_get_current_user(self):
        """Test getting current user from token"""
        test_data = {"sub": "testuser", "role": "user"}
        token = JWTHandler.create_access_token(test_data)

        user = JWTHandler.get_current_user(token)
        assert user is not None
        assert user["username"] == "testuser"
        assert user["role"] == "user"

class TestAuthAPI:
    """Test authentication API endpoints"""

    def test_health_check(self, test_client):
        """Test health check endpoint"""
        response = test_client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_login_success(self, test_client):
        """Test successful login"""
        response = test_client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })

        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["expires_in"] > 0

    def test_login_failure(self, test_client):
        """Test login with wrong credentials"""
        response = test_client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrong_password"
        })

        assert response.status_code == 401

    def test_protected_endpoint_without_token(self, test_client):
        """Test accessing protected endpoint without token"""
        response = test_client.get("/api/auth/me")
        assert response.status_code == 401

    def test_protected_endpoint_with_token(self, test_client, auth_headers):
        """Test accessing protected endpoint with valid token"""
        response = test_client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"

    def test_admin_only_endpoint(self, test_client, auth_headers):
        """Test admin-only endpoint access"""
        response = test_client.get("/api/admin/users", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "users" in data
        assert len(data["users"]) >= 1  # At least admin user exists
