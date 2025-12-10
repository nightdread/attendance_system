"""
Tests for database operations
"""
import pytest

class TestDatabase:
    """Test database operations"""

    def test_database_initialization(self, test_db):
        """Test database initialization"""
        assert test_db is not None
        # Database should be initialized with tables
        # We can test this by trying to execute some operations

    def test_web_user_operations(self, test_db, sample_user_data):
        """Test web user CRUD operations"""
        # Create user
        user_id = test_db.create_web_user(
            username=sample_user_data["username"],
            password=sample_user_data["password"],
            full_name=sample_user_data["full_name"],
            role=sample_user_data["role"]
        )
        assert user_id is not None
        assert user_id > 0

        # Get user by username
        user = test_db.get_web_user_by_username(sample_user_data["username"])
        assert user is not None
        assert user["username"] == sample_user_data["username"]
        assert user["full_name"] == sample_user_data["full_name"]
        assert user["role"] == sample_user_data["role"]

        # Test authentication
        authenticated = test_db.authenticate_web_user(
            sample_user_data["username"],
            sample_user_data["password"]
        )
        assert authenticated is not None
        assert authenticated["username"] == sample_user_data["username"]

        # Test wrong password
        wrong_auth = test_db.authenticate_web_user(
            sample_user_data["username"],
            "wrong_password"
        )
        assert wrong_auth is None

    def test_token_operations(self, test_db):
        """Test token generation and validation"""
        # Create token
        token = test_db.create_token()
        assert token is not None
        assert len(token) > 0

        # Check if token is valid
        is_valid = test_db.is_token_valid(token)
        assert is_valid is True

        # Get token location
        token_location = test_db.get_token_location(token)
        assert token_location == "global"

        # Mark token as used
        test_db.mark_token_used(token)

        # Check if token is still valid (should be invalid now)
        is_valid_after_use = test_db.is_token_valid(token)
        assert is_valid_after_use is False

    def test_person_operations(self, test_db):
        """Test person (Telegram user) operations"""
        tg_user_id = 123456789
        fio = "Тестов Тест Тестович"
        username = "test_user"

        # Create person
        person_id = test_db.create_person(tg_user_id, fio, username)
        assert person_id is not None

        # Get person by Telegram ID
        person = test_db.get_person_by_tg_id(tg_user_id)
        assert person is not None
        assert person["fio"] == fio
        assert person["username"] == username

    def test_attendance_events(self, test_db):
        """Test attendance event logging"""
        # First create a person
        tg_user_id = 987654321
        fio = "Иванов Иван Иванович"
        person_id = test_db.create_person(tg_user_id, fio, "ivanov")

        # Create check-in event
        event_id = test_db.create_event(tg_user_id, "office_main", "in", "ivanov", fio)
        assert event_id is not None

        # Create check-out event
        event_id2 = test_db.create_event(tg_user_id, "office_main", "out", "ivanov", fio)
        assert event_id2 is not None
        assert event_id2 != event_id

        # Get user events
        events = test_db.get_user_events(tg_user_id, limit=10)
        assert len(events) >= 2

        # Check that events are in correct order (newest first)
        assert events[0]["action"] == "out"
        assert events[1]["action"] == "in"

    def test_currently_present(self, test_db):
        """Test getting currently present users"""
        # Create test user
        tg_user_id = 111111111
        fio = "Петров Петр Петрович"
        test_db.create_person(tg_user_id, fio, "petrov")

        # Check-in user
        test_db.create_event(tg_user_id, "office_main", "in", "petrov", fio)

        # Get currently present
        present_users = test_db.get_currently_present()
        assert len(present_users) >= 1

        # Find our test user
        test_user = None
        for user in present_users:
            if user["user_id"] == tg_user_id:
                test_user = user
                break

        assert test_user is not None
        assert test_user["full_name"] == fio
