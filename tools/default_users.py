"""
Shared default user definitions for init_users, reset_database, reset_passwords.
"""
import secrets

# Users for init_users.py and reset_database.py (fresh DB init)
DEFAULT_USERS_INIT = [
    {
        "username": "admin",
        "password": "admin123",
        "full_name": "System Administrator",
        "role": "admin",
        "department": "IT",
        "position": "Administrator",
    },
    {
        "username": "director",
        "password": "director123",
        "full_name": "Company Director",
        "role": "manager",
        "department": "Management",
        "position": "Director",
    },
    {
        "username": "hr",
        "password": "hr123",
        "full_name": "HR Manager",
        "role": "hr",
        "department": "HR",
        "position": "HR Manager",
    },
]

# Username -> password mapping for init/reset (for show_summary display)
INIT_PASSWORDS = {
    "admin": "admin123",
    "director": "director123",
    "hr": "hr123",
}


def get_default_users_for_init():
    """Return default users for init_users and reset_database."""
    return list(DEFAULT_USERS_INIT)


def get_default_users_for_reset_passwords():
    """Return default users for reset_passwords (includes terminal with random password)."""
    return [
        {
            "username": "admin",
            "password": "admin123",
            "full_name": "System Administrator",
            "role": "admin",
            "department": "IT",
            "position": "Administrator",
        },
        {
            "username": "manager",
            "password": "manager123",
            "full_name": "Manager User",
            "role": "manager",
            "department": "Management",
            "position": "Manager",
        },
        {
            "username": "hr",
            "password": "hr123",
            "full_name": "HR User",
            "role": "hr",
            "department": "HR",
            "position": "HR Manager",
        },
        {
            "username": "terminal",
            "password": secrets.token_urlsafe(10),
            "full_name": "Terminal Service",
            "role": "terminal",
            "department": "IT",
            "position": "Terminal",
        },
    ]
