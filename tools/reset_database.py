#!/usr/bin/env python3
"""
Script to reset the attendance database and create initial users
"""
import sys
import os
sys.path.append('.')

from database import Database
from auth.jwt_handler import JWTHandler

def reset_database():
    """Reset database and create initial users"""
    db = Database('attendance.db')

    with db.get_connection() as conn:
        cursor = conn.cursor()

        print("🗑️  Clearing all data...")

        # Clear all tables (keep structure)
        tables_to_clear = ['people', 'events', 'tokens', 'web_users', 'user_permissions']
        for table in tables_to_clear:
            cursor.execute(f'DELETE FROM {table}')
            print(f"   Cleared {table}")

        # Reset sequences
        cursor.execute("DELETE FROM sqlite_sequence")
        print("   Reset auto-increment counters")

        conn.commit()
        print("✅ Database cleared successfully")

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

    print("\n👤 Creating users...")

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

    print("\n🎫 Creating initial QR token...")
    token = db.create_token()
    print(f"   ✅ Created token: {token}")

def show_summary():
    """Show database summary"""
    db = Database('attendance.db')

    with db.get_connection() as conn:
        cursor = conn.cursor()

        print("\n📊 Database Summary:")
        cursor.execute("SELECT COUNT(*) FROM web_users")
        users_count = cursor.fetchone()[0]
        print(f"   👥 Web users: {users_count}")

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
    print("🚀 Resetting Attendance System Database")
    print("=" * 50)

    reset_database()
    create_users()
    create_initial_token()
    show_summary()

    print("\n🎉 Database reset complete!")
    print("🔗 Access the system at: http://localhost:8000")
