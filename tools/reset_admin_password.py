#!/usr/bin/env python3
"""
Script to reset admin password
"""
import sys
import os
sys.path.append('/app')

from database import Database
from auth.jwt_handler import JWTHandler

def reset_admin_password(new_password: str = "admin123"):
    """Reset admin password"""
    db_path = os.getenv('DB_PATH', '/app/data/attendance.db')
    db = Database(db_path)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if admin user exists
        cursor.execute("SELECT id FROM web_users WHERE username = ?", ('admin',))
        admin_user = cursor.fetchone()
        
        if not admin_user:
            # Create admin user if it doesn't exist
            from datetime import datetime
            import json
            from config.config import USER_ROLES
            
            password_hash = JWTHandler.get_password_hash(new_password)
            now = datetime.utcnow().isoformat()
            role_permissions = USER_ROLES.get('admin', {}).get('permissions', [])
            permissions_json = json.dumps(role_permissions)
            
            cursor.execute('''
                INSERT INTO web_users 
                (username, password_hash, full_name, role, permissions, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            ''', ('admin', password_hash, 'System Administrator', 'admin', permissions_json, now))
            print(f"✅ Created admin user with password: {new_password}")
        else:
            # Update existing admin password
            password_hash = JWTHandler.get_password_hash(new_password)
            cursor.execute(
                "UPDATE web_users SET password_hash = ? WHERE username = ?",
                (password_hash, 'admin')
            )
            print(f"✅ Admin password updated to: {new_password}")
        
        conn.commit()
        print(f"🔑 Username: admin")
        print(f"🔑 Password: {new_password}")
        print(f"🔗 Access at: http://localhost:8000")

if __name__ == "__main__":
    new_password = sys.argv[1] if len(sys.argv) > 1 else "admin123"
    print("🔐 Resetting admin password...")
    print("=" * 50)
    reset_admin_password(new_password)
    print("\n🎉 Password reset complete!")

