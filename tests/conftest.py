"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
import os
import tempfile
import shutil
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary database for testing"""
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_attendance.db")

    # Initialize test database
    db = Database(db_path)

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
    shutil.rmtree(temp_dir)

@pytest.fixture
def test_db(test_db_path):
    """Get test database instance"""
    return Database(test_db_path)

@pytest.fixture
def test_client():
    """Create test client for FastAPI app"""
    from main import app
    return TestClient(app)

@pytest.fixture
def auth_headers(test_client):
    """Get authentication headers for admin user"""
    # Login to get token
    response = test_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "username": "testuser",
        "password": "testpass123",
        "full_name": "Test User",
        "role": "user"
    }
