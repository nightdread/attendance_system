#!/usr/bin/env python3
"""
Script to reset passwords for web users without deleting data
"""
import sys
import os
import secrets
sys.path.append('.')

from database import Database
from auth.jwt_handler import JWTHandler

def reset_passwords():
    """Reset passwords for all web users and create terminal user if missing"""
    db = Database('attendance.db')

    print("🔑 Resetting passwords for web users")
    print("=" * 50)

    # Default users with new passwords
    default_users = [
        {
            'username': 'admin',
            'password': 'admin123',
            'full_name': 'System Administrator',
            'role': 'admin',
            'department': 'IT',
            'position': 'Administrator'
        },
        {
            'username': 'manager',
            'password': 'manager123',
            'full_name': 'Manager User',
            'role': 'manager',
            'department': 'Management',
            'position': 'Manager'
        },
        {
            'username': 'hr',
            'password': 'hr123',
            'full_name': 'HR User',
            'role': 'hr',
            'department': 'HR',
            'position': 'HR Manager'
        },
        {
            'username': 'terminal',
            'password': secrets.token_urlsafe(10),  # Random password for terminal
            'full_name': 'Terminal Service',
            'role': 'terminal',
            'department': 'IT',
            'position': 'Terminal'
        }
    ]

    print("\n👤 Updating/Creating users...")

    with db.get_connection() as conn:
        cursor = conn.cursor()

        for user_data in default_users:
            username = user_data['username']
            password = user_data['password']
            
            # Check if user exists
            cursor.execute("SELECT id FROM web_users WHERE username = ?", (username,))
            existing = cursor.fetchone()

            # Hash password
            hashed_password = JWTHandler.get_password_hash(password)

            if existing:
                # Update existing user password
                cursor.execute('''
                    UPDATE web_users 
                    SET password_hash = ?, full_name = ?, role = ?, department = ?, position = ?
                    WHERE username = ?
                ''', (
                    hashed_password,
                    user_data['full_name'],
                    user_data['role'],
                    user_data['department'],
                    user_data['position'],
                    username
                ))
                print(f"   ✅ Updated user: {username} ({user_data['role']}) - password: {password}")
            else:
                # Create new user
                import json
                from config.config import USER_ROLES
                role_permissions = USER_ROLES.get(user_data['role'], {}).get("permissions", [])
                permissions_json = json.dumps(role_permissions)
                
                from datetime import datetime
                now = datetime.utcnow().isoformat()
                
                cursor.execute('''
                    INSERT INTO web_users 
                    (username, password_hash, full_name, role, permissions, department, position, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                ''', (
                    username,
                    hashed_password,
                    user_data['full_name'],
                    user_data['role'],
                    permissions_json,
                    user_data['department'],
                    user_data['position'],
                    now
                ))
                print(f"   ✅ Created user: {username} ({user_data['role']}) - password: {password}")

        conn.commit()

    print("\n📋 All user credentials:")
    print("-" * 50)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM web_users WHERE is_active = 1 ORDER BY id")
        users = cursor.fetchall()
        
        for user in users:
            username = user[0]
            role = user[1]
            # Find password from our list
            password = next((u['password'] for u in default_users if u['username'] == username), 'unknown')
            print(f"   👤 {username} ({role}): {password}")

    print("\n✅ Password reset complete!")
    print("🔗 Access the system at: https://your-domain.com or http://localhost:8000")

if __name__ == "__main__":
    reset_passwords()

