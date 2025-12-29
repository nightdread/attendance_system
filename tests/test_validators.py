"""
Tests for input validation
"""
import pytest
from utils.validators import (
    validate_username, validate_password, validate_fio,
    validate_token, validate_email, validate_role,
    validate_department, validate_position, sanitize_string
)


class TestUsernameValidation:
    """Test username validation"""

    def test_valid_username(self):
        """Test valid usernames"""
        assert validate_username("testuser")[0] is True
        assert validate_username("user123")[0] is True
        assert validate_username("test_user")[0] is True
        assert validate_username("user-test")[0] is True
        assert validate_username("аdmin")[0] is True  # Cyrillic

    def test_username_too_short(self):
        """Test username too short"""
        is_valid, error = validate_username("ab")
        assert is_valid is False
        assert "минимум 3" in error.lower()

    def test_username_too_long(self):
        """Test username too long"""
        long_username = "a" * 51
        is_valid, error = validate_username(long_username)
        assert is_valid is False
        assert "50" in error

    def test_username_starts_with_digit(self):
        """Test username starting with digit"""
        is_valid, error = validate_username("123user")
        assert is_valid is False
        assert "начинаться" in error.lower() or "letter" in error.lower()

    def test_username_invalid_characters(self):
        """Test username with invalid characters"""
        is_valid, error = validate_username("user@name")
        assert is_valid is False
        is_valid, error = validate_username("user name")
        assert is_valid is False

    def test_empty_username(self):
        """Test empty username"""
        is_valid, error = validate_username("")
        assert is_valid is False
        assert "пустым" in error.lower() or "empty" in error.lower()


class TestPasswordValidation:
    """Test password validation"""

    def test_valid_password(self):
        """Test valid passwords"""
        assert validate_password("password123")[0] is True
        assert validate_password("Test1234")[0] is True
        assert validate_password("MyP@ssw0rd")[0] is True

    def test_password_too_short(self):
        """Test password too short"""
        is_valid, error = validate_password("pass1", min_length=8)
        assert is_valid is False
        assert "8" in error

    def test_password_too_long(self):
        """Test password too long"""
        long_password = "a" * 129
        is_valid, error = validate_password(long_password)
        assert is_valid is False
        assert "128" in error

    def test_password_without_letters(self):
        """Test password without letters (with complexity check)"""
        is_valid, error = validate_password("12345678", require_complexity=True)
        assert is_valid is False
        assert "букву" in error.lower() or "letter" in error.lower()

    def test_password_without_digits(self):
        """Test password without digits (with complexity check)"""
        is_valid, error = validate_password("password", require_complexity=True)
        assert is_valid is False
        assert "цифру" in error.lower() or "digit" in error.lower()

    def test_password_no_complexity_check(self):
        """Test password validation without complexity check"""
        assert validate_password("12345678", require_complexity=False)[0] is True
        assert validate_password("password", require_complexity=False)[0] is True

    def test_empty_password(self):
        """Test empty password"""
        is_valid, error = validate_password("")
        assert is_valid is False


class TestFIOValidation:
    """Test FIO validation"""

    def test_valid_fio(self):
        """Test valid FIO"""
        assert validate_fio("Иванов Иван Иванович")[0] is True
        assert validate_fio("Smith John")[0] is True
        assert validate_fio("О'Коннор Мария")[0] is True
        assert validate_fio("Петров-Сидоров Алексей")[0] is True

    def test_fio_too_short(self):
        """Test FIO too short"""
        is_valid, error = validate_fio("Ив", min_length=3)
        assert is_valid is False
        assert "3" in error

    def test_fio_too_long(self):
        """Test FIO too long"""
        long_fio = "И" * 201
        is_valid, error = validate_fio(long_fio)
        assert is_valid is False
        assert "200" in error

    def test_fio_invalid_characters(self):
        """Test FIO with invalid characters"""
        is_valid, error = validate_fio("Иванов@123")
        assert is_valid is False

    def test_fio_only_spaces(self):
        """Test FIO with only spaces"""
        is_valid, error = validate_fio("   ")
        assert is_valid is False


class TestTokenValidation:
    """Test token validation"""

    def test_valid_token(self):
        """Test valid tokens"""
        assert validate_token("abc12345")[0] is True
        assert validate_token("token-123_test")[0] is True

    def test_token_too_short(self):
        """Test token too short"""
        is_valid, error = validate_token("abc", min_length=8)
        assert is_valid is False
        assert "8" in error

    def test_token_invalid_characters(self):
        """Test token with invalid characters"""
        is_valid, error = validate_token("token@123")
        assert is_valid is False


class TestEmailValidation:
    """Test email validation"""

    def test_valid_email(self):
        """Test valid emails"""
        assert validate_email("test@example.com")[0] is True
        assert validate_email("user.name@domain.co.uk")[0] is True

    def test_invalid_email(self):
        """Test invalid emails"""
        assert validate_email("invalid")[0] is False
        assert validate_email("@example.com")[0] is False
        assert validate_email("test@")[0] is False


class TestRoleValidation:
    """Test role validation"""

    def test_valid_role(self):
        """Test valid roles"""
        assert validate_role("admin")[0] is True
        assert validate_role("user")[0] is True
        assert validate_role("manager")[0] is True

    def test_invalid_role(self):
        """Test invalid role"""
        is_valid, error = validate_role("invalid_role")
        assert is_valid is False
        assert "роль" in error.lower() or "role" in error.lower()

    def test_custom_allowed_roles(self):
        """Test with custom allowed roles"""
        assert validate_role("custom", allowed_roles=["custom", "other"])[0] is True
        assert validate_role("admin", allowed_roles=["custom", "other"])[0] is False


class TestSanitizeString:
    """Test string sanitization"""

    def test_sanitize_control_characters(self):
        """Test sanitization of control characters"""
        result = sanitize_string("test\x00\x01string")
        assert "\x00" not in result
        assert "\x01" not in result
        assert "test" in result
        assert "string" in result

    def test_sanitize_max_length(self):
        """Test max length truncation"""
        long_string = "a" * 100
        result = sanitize_string(long_string, max_length=50)
        assert len(result) == 50

    def test_sanitize_trim(self):
        """Test trimming whitespace"""
        result = sanitize_string("  test  ")
        assert result == "test"

    def test_sanitize_empty(self):
        """Test empty string"""
        assert sanitize_string("") == ""
        assert sanitize_string(None) == ""

