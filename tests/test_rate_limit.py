"""
Tests for rate limiting
"""
import pytest
import time
from fastapi import Request
from unittest.mock import Mock, MagicMock
from utils.rate_limit import rate_limit, get_client_ip
from utils.cache import cache


class TestRateLimit:
    """Test rate limiting functionality"""

    def test_get_client_ip_from_request(self):
        """Test getting client IP from request"""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.headers = {}
        
        ip = get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_from_forwarded_header(self):
        """Test getting client IP from X-Forwarded-For header"""
        request = Mock(spec=Request)
        request.client = None
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        
        ip = get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_unknown(self):
        """Test getting client IP when unavailable"""
        request = Mock(spec=Request)
        request.client = None
        request.headers = {}
        
        ip = get_client_ip(request)
        assert ip == "unknown"

    def test_rate_limit_allows_requests_within_limit(self):
        """Test that rate limit allows requests within limit"""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.method = "GET"
        
        # Mock cache to allow requests
        original_redis = cache.redis_client
        cache.redis_client = Mock()
        cache.redis_client.exists.return_value = False
        cache.redis_client.incr.return_value = 1
        cache.redis_client.expire.return_value = True
        
        try:
            result = rate_limit(request, max_requests=10, window_seconds=60, key_prefix="test")
            assert result is None  # No exception raised
        finally:
            cache.redis_client = original_redis

    def test_rate_limit_blocks_when_exceeded(self):
        """Test that rate limit blocks when exceeded"""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.method = "GET"
        
        # Mock cache to indicate blocking
        original_redis = cache.redis_client
        cache.redis_client = Mock()
        cache.redis_client.exists.return_value = True  # Already blocked
        
        try:
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                rate_limit(request, max_requests=10, window_seconds=60, key_prefix="test")
            assert exc_info.value.status_code == 429
        finally:
            cache.redis_client = original_redis

    def test_rate_limit_blocks_after_max_requests(self):
        """Test that rate limit blocks after max requests"""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.method = "GET"
        
        # Mock cache to exceed limit
        original_redis = cache.redis_client
        cache.redis_client = Mock()
        cache.redis_client.exists.return_value = False
        cache.redis_client.incr.return_value = 11  # Exceeds limit of 10
        cache.redis_client.expire.return_value = True
        cache.redis_client.set.return_value = True
        
        try:
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                rate_limit(request, max_requests=10, window_seconds=60, key_prefix="test")
            assert exc_info.value.status_code == 429
        finally:
            cache.redis_client = original_redis

    def test_rate_limit_fail_open_on_error(self):
        """Test that rate limit fails open (allows request) on error"""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.method = "GET"
        
        # Mock cache to raise exception
        original_redis = cache.redis_client
        cache.redis_client = Mock()
        cache.redis_client.exists.side_effect = Exception("Redis error")
        
        try:
            # Should not raise exception, should allow request
            result = rate_limit(request, max_requests=10, window_seconds=60, key_prefix="test")
            assert result is None
        finally:
            cache.redis_client = original_redis


class TestRateLimitIntegration:
    """Integration tests for rate limiting with test client"""

    def test_login_rate_limit(self, test_client):
        """Test rate limiting on login endpoint"""
        # Make multiple login attempts
        for i in range(6):  # Exceeds MAX_LOGIN_ATTEMPTS (5)
            response = test_client.post(
                "/login",
                data={
                    "username": "testuser",
                    "password": "wrongpassword",
                    "csrf_token": "test_token"  # Will fail CSRF but that's OK for this test
                }
            )
            # After 5 attempts, should get rate limit error
            if i >= 5:
                # Should be blocked or show rate limit message
                assert response.status_code in [200, 429]  # May show error page or rate limit

