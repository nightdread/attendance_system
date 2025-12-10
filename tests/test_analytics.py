"""
Tests for analytics functionality
"""
import pytest
from datetime import datetime

class TestAnalyticsAPI:
    """Test analytics API endpoints"""

    def test_get_daily_analytics(self, test_client, auth_headers):
        """Test daily analytics endpoint"""
        # Use today's date
        today = datetime.now().strftime('%Y-%m-%d')

        response = test_client.get(f"/api/analytics/daily/{today}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "date" in data
        assert "checkins" in data
        assert "checkouts" in data
        assert "unique_users" in data
        assert isinstance(data["checkins"], int)
        assert isinstance(data["checkouts"], int)
        assert isinstance(data["unique_users"], int)

    def test_get_weekly_analytics(self, test_client, auth_headers):
        """Test weekly analytics endpoint"""
        response = test_client.get("/api/analytics/weekly", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "period" in data
        assert "daily_stats" in data
        assert "start" in data["period"]
        assert "end" in data["period"]
        assert isinstance(data["daily_stats"], list)

    def test_get_location_analytics(self, test_client, auth_headers):
        """Test location analytics endpoint"""
        response = test_client.get("/api/analytics/locations", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "locations" in data
        assert isinstance(data["locations"], list)

        # Check structure of location data
        if data["locations"]:
            location = data["locations"][0]
            assert "location" in location
            assert "checkins" in location
            assert "checkouts" in location
            assert "unique_users" in location

    def test_get_user_analytics(self, test_client, auth_headers):
        """Test user analytics endpoint"""
        response = test_client.get("/api/analytics/users", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "users" in data
        assert isinstance(data["users"], list)

    def test_get_hourly_analytics(self, test_client, auth_headers):
        """Test hourly analytics endpoint"""
        today = datetime.now().strftime('%Y-%m-%d')

        response = test_client.get(f"/api/analytics/hourly/{today}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "date" in data
        assert "hourly_stats" in data
        assert isinstance(data["hourly_stats"], list)

    def test_get_monthly_analytics(self, test_client, auth_headers):
        """Test monthly analytics endpoint"""
        year = datetime.now().year
        month = datetime.now().month

        response = test_client.get(f"/api/analytics/monthly/{year}/{month}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "period" in data
        assert "monthly_totals" in data
        assert "daily_breakdown" in data

    def test_get_system_health(self, test_client, auth_headers):
        """Test system health analytics endpoint"""
        response = test_client.get("/api/analytics/health", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "users" in data
        assert "events" in data
        assert "tokens" in data
        assert "generated_at" in data

    def test_analytics_unauthorized(self, test_client):
        """Test analytics endpoints require authentication"""
        endpoints = [
            "/api/analytics/daily/2025-12-09",
            "/api/analytics/weekly",
            "/api/analytics/locations",
            "/api/analytics/users",
            "/api/analytics/health"
        ]

        for endpoint in endpoints:
            response = test_client.get(endpoint)
            assert response.status_code == 401

class TestAnalyticsDatabase:
    """Test analytics database methods"""

    def test_get_daily_stats_empty(self, test_db):
        """Test daily stats with no data"""
        stats = test_db.get_daily_stats("2025-12-09")
        assert stats["checkins"] == 0
        assert stats["checkouts"] == 0
        assert stats["unique_users"] == 0

    def test_get_weekly_stats_empty(self, test_db):
        """Test weekly stats with no data"""
        stats = test_db.get_weekly_stats("2025-12-01", "2025-12-07")
        assert stats == []

    def test_get_location_stats_empty(self, test_db):
        """Test location stats with no data"""
        stats = test_db.get_location_stats()
        assert stats == []

    def test_get_user_stats_empty(self, test_db):
        """Test user stats with no data"""
        stats = test_db.get_user_stats()
        assert stats == []

    def test_get_hourly_stats_empty(self, test_db):
        """Test hourly stats with no data"""
        stats = test_db.get_hourly_stats("2025-12-09")
        assert stats == []

    def test_system_health_stats(self, test_db):
        """Test system health stats"""
        stats = test_db.get_system_health_stats()
        assert "users" in stats
        assert "events" in stats
        assert "tokens" in stats
        assert "generated_at" in stats

        assert "telegram_users" in stats["users"]
        assert "web_users" in stats["users"]
        assert "total" in stats["events"]
        assert "recent_24h" in stats["events"]
        assert "active" in stats["tokens"]
