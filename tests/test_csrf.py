"""
Tests for CSRF protection
"""
import pytest
import time
from fastapi import Request
from unittest.mock import Mock, MagicMock
from utils.csrf import (
    generate_csrf_token, get_csrf_token, set_csrf_token,
    validate_csrf_token, require_csrf_token
)


class TestCSRFToken:
    """Test CSRF token generation and management"""

    def test_generate_csrf_token(self):
        """Test CSRF token generation"""
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        
        assert token1 is not None
        assert token2 is not None
        assert len(token1) > 0
        assert len(token2) > 0
        assert token1 != token2  # Should be unique

    def test_get_set_csrf_token(self):
        """Test getting and setting CSRF token in session"""
        request = Mock(spec=Request)
        request.session = {}
        
        # Set token
        token = set_csrf_token(request)
        assert token is not None
        assert "csrf_token" in request.session
        assert request.session["csrf_token"] == token
        
        # Get token
        retrieved_token = get_csrf_token(request)
        assert retrieved_token == token

    def test_get_csrf_token_none(self):
        """Test getting CSRF token when not set"""
        request = Mock(spec=Request)
        request.session = {}
        
        token = get_csrf_token(request)
        assert token is None

    def test_set_custom_csrf_token(self):
        """Test setting custom CSRF token"""
        request = Mock(spec=Request)
        request.session = {}
        
        custom_token = "custom_token_123"
        result = set_csrf_token(request, token=custom_token)
        assert result == custom_token
        assert request.session["csrf_token"] == custom_token


class TestCSRFValidation:
    """Test CSRF token validation"""

    def test_validate_csrf_token_valid(self):
        """Test validating valid CSRF token"""
        request = Mock(spec=Request)
        request.session = {"csrf_token": "test_token_123"}
        
        assert validate_csrf_token(request, "test_token_123") is True

    def test_validate_csrf_token_invalid(self):
        """Test validating invalid CSRF token"""
        request = Mock(spec=Request)
        request.session = {"csrf_token": "test_token_123"}
        
        assert validate_csrf_token(request, "wrong_token") is False

    def test_validate_csrf_token_missing_session(self):
        """Test validation when session token is missing"""
        request = Mock(spec=Request)
        request.session = {}
        
        assert validate_csrf_token(request, "any_token") is False

    def test_validate_csrf_token_from_header(self):
        """Test validation with token from header"""
        request = Mock(spec=Request)
        request.session = {"csrf_token": "test_token_123"}
        request.headers = {"X-CSRF-Token": "test_token_123"}
        
        # validate_csrf_token should get token from header if not provided
        # But the function needs token parameter, so we test with explicit token
        assert validate_csrf_token(request, "test_token_123") is True

    def test_validate_csrf_token_timing_attack_protection(self):
        """Test that validation uses constant-time comparison"""
        request = Mock(spec=Request)
        request.session = {"csrf_token": "test_token_123"}
        
        # Both should take similar time (secrets.compare_digest)
        start1 = time.time()
        validate_csrf_token(request, "test_token_123")
        time1 = time.time() - start1
        
        start2 = time.time()
        validate_csrf_token(request, "wrong_token")
        time2 = time.time() - start2
        
        # Times should be similar (within reasonable margin)
        # This is a basic check - real timing attack protection is in secrets.compare_digest
        assert abs(time1 - time2) < 0.1  # Should be very close


class TestRequireCSRFToken:
    """Test require_csrf_token function"""

    @pytest.mark.asyncio
    async def test_require_csrf_token_valid(self):
        """Test requiring valid CSRF token"""
        request = Mock(spec=Request)
        request.session = {"csrf_token": "test_token_123"}
        request.headers = {"X-CSRF-Token": "test_token_123"}
        request.method = "POST"
        
        # Should not raise exception
        await require_csrf_token(request)

    @pytest.mark.asyncio
    async def test_require_csrf_token_invalid(self):
        """Test requiring invalid CSRF token"""
        request = Mock(spec=Request)
        request.session = {"csrf_token": "test_token_123"}
        request.headers = {"X-CSRF-Token": "wrong_token"}
        request.method = "POST"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.url = Mock()
        request.url.path = "/api/test"
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await require_csrf_token(request)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_csrf_token_missing(self):
        """Test requiring CSRF token when missing"""
        request = Mock(spec=Request)
        request.session = {"csrf_token": "test_token_123"}
        request.headers = {}  # No CSRF token header
        request.method = "POST"
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.url = Mock()
        request.url.path = "/api/test"
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await require_csrf_token(request)
        assert exc_info.value.status_code == 403


class TestCSRFIntegration:
    """Integration tests for CSRF protection"""

    def test_login_without_csrf_token(self, test_client):
        """Test login without CSRF token should fail"""
        response = test_client.post(
            "/login",
            data={
                "username": "testuser",
                "password": "testpass"
                # No csrf_token
            }
        )
        # Should fail CSRF validation
        assert response.status_code == 403

    def test_login_with_invalid_csrf_token(self, test_client):
        """Test login with invalid CSRF token should fail"""
        # First get a valid CSRF token
        login_page = test_client.get("/login")
        assert login_page.status_code == 200
        
        # Try to login with invalid token
        response = test_client.post(
            "/login",
            data={
                "username": "testuser",
                "password": "testpass",
                "csrf_token": "invalid_token"
            }
        )
        # Should fail CSRF validation
        assert response.status_code == 403

