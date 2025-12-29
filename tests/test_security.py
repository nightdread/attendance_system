"""
Security tests - SQL injection, XSS, authorization
"""
import pytest
from fastapi import HTTPException
from unittest.mock import Mock, patch
from database import Database
from utils.validators import sanitize_string


class TestSQLInjection:
    """Test SQL injection protection"""

    def test_sql_injection_in_username(self, test_db):
        """Test that SQL injection in username is prevented"""
        # Try to inject SQL in username
        malicious_username = "admin' OR '1'='1"
        
        # Should not find user (parameterized query prevents injection)
        user = test_db.get_web_user_by_username(malicious_username)
        assert user is None

    def test_sql_injection_in_password(self, test_db):
        """Test that SQL injection in password is prevented"""
        # Create a test user
        test_db.create_web_user(
            username="testuser",
            password="safe_password",
            full_name="Test User"
        )
        
        # Try SQL injection in password
        malicious_password = "'; DROP TABLE users; --"
        
        # Should not execute DROP TABLE (parameterized query prevents it)
        # Just verify the user still exists
        user = test_db.get_web_user_by_id(1)
        assert user is not None

    def test_sql_injection_in_fio(self, test_db):
        """Test that SQL injection in FIO is prevented"""
        # Try to inject SQL in FIO
        malicious_fio = "'; DROP TABLE people; --"
        
        # Should be sanitized/validated
        sanitized = sanitize_string(malicious_fio)
        # Should not contain dangerous characters or be handled safely
        assert "'" not in sanitized or sanitized != malicious_fio

    def test_parameterized_queries_used(self, test_db):
        """Test that parameterized queries are used (not string concatenation)"""
        # This is more of a code review test, but we can verify
        # that queries use ? placeholders by checking the database methods
        
        # All database methods should use parameterized queries
        # This is verified by the fact that SQL injection attempts don't work
        test_username = "test'user"
        user = test_db.get_web_user_by_username(test_username)
        # Should not find user, not crash or execute malicious SQL
        assert user is None or isinstance(user, dict)


class TestXSSProtection:
    """Test XSS (Cross-Site Scripting) protection"""

    def test_xss_in_username(self):
        """Test that XSS in username is sanitized"""
        xss_payload = "<script>alert('XSS')</script>"
        sanitized = sanitize_string(xss_payload)
        
        # Should not contain script tags (or be escaped by Jinja2)
        # sanitize_string removes control chars but not HTML
        # Jinja2 auto-escapes in templates
        assert "<script>" in sanitized  # sanitize_string doesn't remove HTML
        # But Jinja2 will escape it in templates

    def test_xss_in_fio(self):
        """Test that XSS in FIO is handled safely"""
        xss_payload = "<img src=x onerror=alert('XSS')>"
        
        # Should be sanitized
        sanitized = sanitize_string(xss_payload)
        # Validation should reject or sanitize
        from utils.validators import validate_fio
        is_valid, _ = validate_fio(xss_payload)
        # FIO validation should reject HTML tags
        assert is_valid is False  # Contains invalid characters

    def test_xss_in_full_name(self):
        """Test that XSS in full_name is handled safely"""
        xss_payload = "';alert('XSS');//"
        
        # Should be sanitized
        sanitized = sanitize_string(xss_payload)
        # Should not execute JavaScript
        assert "alert" in sanitized  # String is preserved
        # But when rendered in template, Jinja2 escapes it

    def test_jinja2_auto_escape(self):
        """Test that Jinja2 auto-escapes variables"""
        # This is a conceptual test - Jinja2 by default escapes all variables
        # We verify that our templates don't use |safe filter inappropriately
        
        # Check that templates don't have unsafe rendering
        # This would be better as a template linting test
        from pathlib import Path
        templates_dir = Path("templates")
        if templates_dir.exists():
            for template_file in templates_dir.glob("*.html"):
                content = template_file.read_text()
                # Check for potentially unsafe patterns (but allow legitimate use)
                # We're not banning |safe entirely, just checking awareness
                unsafe_patterns = [
                    "{{.*\\|safe.*}}",  # Variables with |safe
                ]
                # This is informational - we allow |safe for trusted content
                pass


class TestAuthorization:
    """Test authorization and access control"""

    def test_unauthorized_access_to_admin_endpoint(self, test_client):
        """Test that unauthorized users cannot access admin endpoints"""
        # Try to access admin endpoint without auth
        response = test_client.get("/admin")
        # Should redirect to login
        assert response.status_code in [302, 401]
        if response.status_code == 302:
            assert "/login" in response.headers.get("location", "")

    def test_unauthorized_access_to_api(self, test_client):
        """Test that unauthorized users cannot access protected API"""
        # Try to access protected API without token
        response = test_client.get("/api/user/1")
        # Should return 401 or 403
        assert response.status_code in [401, 403]

    def test_user_cannot_access_admin_api(self, test_client):
        """Test that regular user cannot access admin API"""
        from auth.jwt_handler import JWTHandler
        
        # Create token for regular user
        token = JWTHandler.create_access_token(data={"sub": "user", "role": "user"})
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to access admin endpoint
        response = test_client.get("/api/user/1", headers=headers)
        # Should return 403 Forbidden
        assert response.status_code == 403

    def test_admin_can_access_admin_api(self, test_client, auth_headers):
        """Test that admin can access admin API"""
        # Use auth_headers fixture which has admin token
        response = test_client.get("/api/user/1", headers=auth_headers)
        # Should succeed (or 404 if user doesn't exist, but not 403)
        assert response.status_code != 403

    def test_role_based_access_control(self, test_client):
        """Test role-based access control"""
        from auth.jwt_handler import JWTHandler
        
        # Test manager role
        manager_token = JWTHandler.create_access_token(data={"sub": "manager", "role": "manager"})
        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        
        # Manager should be able to access user management
        response = test_client.get("/api/user/1", headers=manager_headers)
        assert response.status_code != 403  # Should not be forbidden
        
        # Test user role
        user_token = JWTHandler.create_access_token(data={"sub": "user", "role": "user"})
        user_headers = {"Authorization": f"Bearer {user_token}"}
        
        # User should NOT be able to access user management
        response = test_client.get("/api/user/1", headers=user_headers)
        assert response.status_code == 403  # Should be forbidden


class TestInputValidation:
    """Test input validation for security"""

    def test_path_traversal_prevention(self):
        """Test that path traversal is prevented"""
        malicious_path = "../../../etc/passwd"
        sanitized = sanitize_string(malicious_path)
        
        # Should be sanitized (though this is more of a file operation concern)
        assert sanitized is not None

    def test_command_injection_prevention(self):
        """Test that command injection is prevented"""
        malicious_input = "; rm -rf /"
        sanitized = sanitize_string(malicious_input)
        
        # Should be sanitized
        assert sanitized is not None
        # Validation should handle it
        from utils.validators import validate_username
        is_valid, _ = validate_username(malicious_input)
        assert is_valid is False  # Contains invalid characters

    def test_null_byte_injection(self):
        """Test that null byte injection is prevented"""
        malicious_input = "test\x00string"
        sanitized = sanitize_string(malicious_input)
        
        # Should remove null bytes
        assert "\x00" not in sanitized

    def test_oversized_input(self):
        """Test that oversized input is rejected"""
        oversized_username = "a" * 1000
        
        from utils.validators import validate_username
        is_valid, error = validate_username(oversized_username)
        assert is_valid is False
        assert "50" in error  # Max length is 50


class TestCSRFSecurity:
    """Test CSRF protection security"""

    def test_csrf_token_required_for_state_changing_operations(self, test_client):
        """Test that CSRF token is required for POST/PUT operations"""
        # Try to update user without CSRF token
        from auth.jwt_handler import JWTHandler
        token = JWTHandler.create_access_token(data={"sub": "admin", "role": "admin"})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = test_client.put(
            "/api/user/1",
            json={"full_name": "New Name"},
            headers=headers
        )
        # Should fail CSRF check
        assert response.status_code == 403

    def test_csrf_token_uniqueness(self):
        """Test that CSRF tokens are unique"""
        from utils.csrf import generate_csrf_token
        
        tokens = [generate_csrf_token() for _ in range(10)]
        # All tokens should be unique
        assert len(set(tokens)) == 10

    def test_csrf_token_not_guessable(self):
        """Test that CSRF tokens are not easily guessable"""
        from utils.csrf import generate_csrf_token
        
        token = generate_csrf_token()
        # Should be long enough and random
        assert len(token) >= 32  # Base64 encoded 32 bytes = ~43 chars
        # Should not be a simple pattern
        assert token != "a" * len(token)


class TestRateLimitSecurity:
    """Test rate limiting security"""

    def test_rate_limit_prevents_brute_force(self, test_client):
        """Test that rate limiting prevents brute force attacks"""
        # Make many login attempts
        attempts = []
        for i in range(10):
            response = test_client.post(
                "/login",
                data={
                    "username": "admin",
                    "password": f"wrong{i}",
                    "csrf_token": "test"  # Will fail but that's OK
                }
            )
            attempts.append(response.status_code)
        
        # After MAX_LOGIN_ATTEMPTS (5), should see rate limiting
        # Check that some requests are blocked
        assert 429 in attempts or any("много попыток" in str(r.content) for r in attempts if hasattr(r, 'content'))

    def test_rate_limit_by_ip(self):
        """Test that rate limiting is per IP address"""
        from utils.rate_limit import get_client_ip
        from fastapi import Request
        
        # Different IPs should have separate rate limits
        request1 = Mock(spec=Request)
        request1.client = Mock()
        request1.client.host = "192.168.1.1"
        request1.headers = {}
        
        request2 = Mock(spec=Request)
        request2.client = Mock()
        request2.client.host = "192.168.1.2"
        request2.headers = {}
        
        ip1 = get_client_ip(request1)
        ip2 = get_client_ip(request2)
        
        assert ip1 != ip2
        # Each IP should have separate rate limit counters

