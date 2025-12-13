#!/usr/bin/env python3
"""
Script to reset all default user passwords to known values
"""
import sys
import os
sys.path.append('/app')

from database import Database
from auth.jwt_handler import JWTHandler

def reset_passwords():
    """Reset passwords for default users"""
    db_path = os.getenv('DB_PATH', '/app/data/attendance.db')
    db = Database(db_path)
    
    # Default passwords
    passwords = {
        'admin': 'admin123',
        'manager': 'manager123',
        'hr': 'hr123'
    }
    
    print("🔐 Resetting passwords for default users...")
    print("=" * 60)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        for username, new_password in passwords.items():
            # Check if user exists
            cursor.execute("SELECT id FROM web_users WHERE username = ?", (username,))
            user = cursor.fetchone()
            
            if user:
                # Update password
                password_hash = JWTHandler.get_password_hash(new_password)
                cursor.execute(
                    "UPDATE web_users SET password_hash = ? WHERE username = ?",
                    (password_hash, username)
                )
                print(f"✅ {username:10} -> password: {new_password}")
            else:
                print(f"❌ User '{username}' not found")
        
        conn.commit()
    
    print("=" * 60)
    print("🔑 Default credentials:")
    for username, password in passwords.items():
        print(f"   Username: {username}")
        print(f"   Password: {password}")
    print("=" * 60)
    print("✅ Passwords reset complete!")
    print("🔗 Access at: http://localhost:8000")

if __name__ == "__main__":
    reset_passwords()

