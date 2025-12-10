#!/usr/bin/env python3
"""
Initialize users in clean database
"""
import sys
import os
sys.path.append('.')

from database import Database
from auth.jwt_handler import JWTHandler

def init_roles():
    """Initialize system roles"""
    db = Database('attendance.db')

    roles = [
        {
            'name': 'admin',
            'display_name': 'Администратор',
            'description': 'Полный доступ ко всем функциям',
            'permissions': '["all"]'
        },
        {
            'name': 'manager',
            'display_name': 'Менеджер',
            'description': 'Управление пользователями и просмотр аналитики',
            'permissions': '["view_analytics", "manage_users", "view_reports"]'
        },
        {
            'name': 'hr',
            'display_name': 'HR специалист',
            'description': 'Управление сотрудниками и отчетами',
            'permissions': '["view_analytics", "manage_employees", "view_reports"]'
        },
        {
            'name': 'user',
            'display_name': 'Сотрудник',
            'description': 'Базовый доступ для отметки посещаемости',
            'permissions': '["check_attendance", "view_own_stats"]'
        }
    ]

    print("👥 Creating roles...")

    with db.get_connection() as conn:
        cursor = conn.cursor()
        for role in roles:
            cursor.execute('''
                INSERT INTO roles (name, display_name, description, permissions, is_system, created_at)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
            ''', (role['name'], role['display_name'], role['description'], role['permissions']))
        conn.commit()
        print("   ✅ Roles created")

def create_users():
    """Create initial users: admin, director, hr"""
    db = Database('attendance.db')

    users_data = [
        {
            'username': 'admin',
            'password': 'admin123',
            'full_name': 'System Administrator',
            'role': 'admin',
            'department': 'IT',
            'position': 'Administrator'
        },
        {
            'username': 'director',
            'password': 'director123',
            'full_name': 'Company Director',
            'role': 'manager',  # Using manager role for director
            'department': 'Management',
            'position': 'Director'
        },
        {
            'username': 'hr',
            'password': 'hr123',
            'full_name': 'HR Manager',
            'role': 'hr',
            'department': 'HR',
            'position': 'HR Manager'
        }
    ]

    print("👤 Creating users...")

    for user_data in users_data:
        # Hash password
        hashed_password = JWTHandler.get_password_hash(user_data['password'])

        # Insert user
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO web_users
                (username, password_hash, full_name, role, department, position, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'))
            ''', (
                user_data['username'],
                hashed_password,
                user_data['full_name'],
                user_data['role'],
                user_data['department'],
                user_data['position']
            ))
            conn.commit()

        print(f"   ✅ Created user: {user_data['username']} ({user_data['role']}) - password: {user_data['password']}")

def create_initial_token():
    """Create initial QR token"""
    db = Database('attendance.db')

    print("🎫 Creating initial QR token...")
    token = db.create_token()
    print(f"   ✅ Created token: {token}")

def show_summary():
    """Show database summary"""
    db = Database('attendance.db')

    with db.get_connection() as conn:
        cursor = conn.cursor()

        print("\n📊 Database Summary:")
        cursor.execute("SELECT COUNT(*) FROM roles")
        roles_count = cursor.fetchone()[0]
        print(f"   👥 Roles: {roles_count}")

        cursor.execute("SELECT COUNT(*) FROM web_users")
        users_count = cursor.fetchone()[0]
        print(f"   👤 Web users: {users_count}")

        cursor.execute("SELECT COUNT(*) FROM people")
        people_count = cursor.fetchone()[0]
        print(f"   🧑 Employees: {people_count}")

        cursor.execute("SELECT COUNT(*) FROM tokens")
        tokens_count = cursor.fetchone()[0]
        print(f"   🎫 Active tokens: {tokens_count}")

        cursor.execute("SELECT COUNT(*) FROM events")
        events_count = cursor.fetchone()[0]
        print(f"   📝 Events: {events_count}")

        print("\n🔑 User Credentials:")
        cursor.execute("SELECT username, role FROM web_users ORDER BY id")
        users = cursor.fetchall()
        for user in users:
            username = user[0]
            role = user[1]
            password = {
                'admin': 'admin123',
                'director': 'director123',
                'hr': 'hr123'
            }.get(username, 'unknown')
            print(f"   {username} ({role}): {password}")

if __name__ == "__main__":
    print("🚀 Initializing Attendance System Database")
    print("=" * 50)

    init_roles()
    create_users()
    create_initial_token()
    show_summary()

    print("\n🎉 Database initialization complete!")
    print("🔗 Access the system at: http://localhost:8000")
