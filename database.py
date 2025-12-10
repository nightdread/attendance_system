import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import secrets
from utils.cache import (
    get_cached_token, set_cached_token, invalidate_token,
    get_cached_analytics_daily, set_cached_analytics_daily,
    get_cached_analytics_weekly, set_cached_analytics_weekly,
    get_cached_analytics_location, set_cached_analytics_location,
    get_cached_analytics_users, set_cached_analytics_users,
    get_cached_analytics_hourly, set_cached_analytics_hourly,
    get_cached_system_health, set_cached_system_health,
    cache
)
from config.config import CACHE_TTL_USER

class Database:
    def __init__(self, db_path: str = "attendance.db"):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # People table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS people (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_user_id  INTEGER UNIQUE NOT NULL,
                    fio         TEXT NOT NULL,
                    username    TEXT,
                    created_at  TEXT NOT NULL
                )
            ''')

            # Events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    username   TEXT,
                    full_name  TEXT,
                    location   TEXT NOT NULL,
                    action     TEXT NOT NULL,
                    ts         TEXT NOT NULL
                )
            ''')

            # Tokens table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tokens (
                    token       TEXT PRIMARY KEY,
                    location    TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    expires_at  TEXT NOT NULL,
                    used        INTEGER NOT NULL DEFAULT 0
                )
            ''')

            # Web users table (extended with permissions)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS web_users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    username    TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name   TEXT,
                    role        TEXT NOT NULL DEFAULT 'user',
                    permissions TEXT,  -- JSON array of permissions
                    department  TEXT,
                    position    TEXT,
                    is_active   INTEGER NOT NULL DEFAULT 1,
                    created_at  TEXT NOT NULL,
                    last_login  TEXT,
                    created_by  INTEGER,  -- Who created this user
                    FOREIGN KEY (created_by) REFERENCES web_users (id)
                )
            ''')

            # Roles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS roles (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    description TEXT,
                    permissions TEXT NOT NULL,  -- JSON array of permissions
                    is_system   INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL
                )
            ''')

            # User permissions table (for custom permissions)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    permission  TEXT NOT NULL,
                    granted_by  INTEGER NOT NULL,
                    granted_at  TEXT NOT NULL,
                    expires_at  TEXT,
                    FOREIGN KEY (user_id) REFERENCES web_users (id),
                    FOREIGN KEY (granted_by) REFERENCES web_users (id),
                    UNIQUE(user_id, permission)
                )
            ''')

            # Useful indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events (user_id, ts)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_used_created ON tokens (used, created_at)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_web_users_username ON web_users (username)")

            # Create default roles
            from config.config import USER_ROLES
            import json

            for role_name, role_data in USER_ROLES.items():
                cursor.execute("SELECT COUNT(*) FROM roles WHERE name = ?", (role_name,))
                if cursor.fetchone()[0] == 0:
                    now = datetime.utcnow().isoformat()
                    cursor.execute(
                        "INSERT INTO roles (name, display_name, description, permissions, is_system, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (role_name, role_data["name"], role_data["description"],
                         json.dumps(role_data["permissions"]), 1, now)
                    )

            # Create default users if DB is empty
            cursor.execute("SELECT COUNT(*) FROM web_users")
            has_users = cursor.fetchone()[0] > 0
            if not has_users:
                from auth.jwt_handler import JWTHandler

                now = datetime.utcnow().isoformat()
                defaults = [
                    ("admin", "Administrator", "admin"),
                    ("manager", "Manager User", "manager"),
                    ("hr", "HR User", "hr"),
                ]

                creds = []
                for username, full_name, role in defaults:
                    password_plain = secrets.token_urlsafe(10)
                    password_hash = JWTHandler.get_password_hash(password_plain)
                    permissions = json.dumps(USER_ROLES[role]["permissions"])
                    cursor.execute(
                        "INSERT INTO web_users (username, password_hash, full_name, role, permissions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (username, password_hash, full_name, role, permissions, now)
                    )
                    creds.append((username, password_plain, role))

                # Print generated credentials to stdout (not stored in container)
                print("[INIT] Default users created (empty DB detected):")
                print(f"[INIT] Generated at: {now}")
                for u, p, r in creds:
                    print(f"[INIT] user={u} role={r} password={p}")

            conn.commit()

    # People operations
    def create_person(self, tg_user_id: int, fio: str, username: Optional[str] = None) -> int:
        """Create new person record"""
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO people (tg_user_id, fio, username, created_at) VALUES (?, ?, ?, ?)",
                (tg_user_id, fio, username, now)
            )
            conn.commit()
            return cursor.lastrowid

    def get_person_by_tg_id(self, tg_user_id: int) -> Optional[Dict[str, Any]]:
        """Get person by Telegram user ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM people WHERE tg_user_id = ?", (tg_user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_person_fio(self, tg_user_id: int, fio: str) -> bool:
        """Update person's FIO"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE people SET fio = ? WHERE tg_user_id = ?", (fio, tg_user_id))
            conn.commit()
            return cursor.rowcount > 0

    # Token operations
    def get_active_token(self) -> Optional[Dict[str, Any]]:
        """Get the active (unused) global token"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tokens WHERE used = 0 ORDER BY created_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_token(self, token_length: int = 8) -> str:
        """Create new global token"""
        token = secrets.token_urlsafe(token_length)
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=24)  # 24 hours expiry

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tokens (token, location, created_at, expires_at, used) VALUES (?, ?, ?, ?, 0)",
                (token, "global", now.isoformat(), expires_at.isoformat())
            )
            conn.commit()
        return token

    def mark_token_used(self, token: str) -> bool:
        """Mark token as used"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tokens SET used = 1 WHERE token = ?", (token,))
            success = cursor.rowcount > 0
            conn.commit()

            # Invalidate cache
            if success:
                invalidate_token(token)

            return success

    def get_token_location(self, token: str) -> Optional[str]:
        """Get location for token"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT location FROM tokens WHERE token = ?", (token,))
            row = cursor.fetchone()
            return row[0] if row else None

    def is_token_valid(self, token: str) -> bool:
        """Check if token exists and is not used"""
        # Check cache first
        cached_result = get_cached_token(token)
        if cached_result is not None:
            return cached_result.get("valid", False)

        # Check database
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT used FROM tokens WHERE token = ? AND used = 0", (token,))
            row = cursor.fetchone()
            is_valid = row is not None

            # Cache the result
            set_cached_token(token, {"valid": is_valid})

            return is_valid

    # Event operations
    def create_event(self, user_id: int, location: str, action: str,
                    username: Optional[str] = None, full_name: Optional[str] = None) -> int:
        """Create new event"""
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO events (user_id, username, full_name, location, action, ts) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, full_name, location, action, now)
            )
            conn.commit()
            return cursor.lastrowid

    # Reporting operations
    def get_user_events(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's recent events"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM events WHERE user_id = ? ORDER BY ts DESC LIMIT ?",
                (user_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_events_by_period(self, user_id: int, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get user's events in date range"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM events WHERE user_id = ? AND ts >= ? AND ts <= ? ORDER BY ts",
                (user_id, start_date, end_date)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_currently_present(self) -> List[Dict[str, Any]]:
        """Get users who are currently in office (last event is 'in')"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Get the latest event for each user
            cursor.execute('''
                SELECT e.*, p.fio
                FROM events e
                JOIN people p ON e.user_id = p.tg_user_id
                WHERE e.id IN (
                    SELECT MAX(id)
                    FROM events
                    GROUP BY user_id
                ) AND e.action = 'in'
                ORDER BY e.ts DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def get_work_time(self, user_id: int, date: str) -> float:
        """Calculate work time for user on specific date (in hours)"""
        date_start = f"{date}T00:00:00"
        date_end = f"{date}T23:59:59"

        events = self.get_events_by_period(user_id, date_start, date_end)

        total_seconds = 0
        checkin_time = None

        for event in events:
            if event['action'] == 'in':
                checkin_time = datetime.fromisoformat(event['ts'])
            elif event['action'] == 'out' and checkin_time:
                checkout_time = datetime.fromisoformat(event['ts'])
                total_seconds += (checkout_time - checkin_time).total_seconds()
                checkin_time = None

        return total_seconds / 3600  # Convert to hours

    # Web user operations
    def authenticate_web_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate web user"""
        from auth.jwt_handler import JWTHandler

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM web_users WHERE username = ? AND is_active = 1",
                (username,)
            )
            user = cursor.fetchone()

            if user and JWTHandler.verify_password(password, user['password_hash']):
                # Update last login
                now = datetime.utcnow().isoformat()
                cursor.execute(
                    "UPDATE web_users SET last_login = ? WHERE id = ?",
                    (now, user['id'])
                )
                conn.commit()

                return dict(user)
            return None

    def create_web_user(self, username: str, password: str, full_name: str = None, role: str = "user",
                        department: str = None, position: str = None) -> int:
        """Create new web user"""
        from auth.jwt_handler import JWTHandler
        import json

        # Get role permissions
        from config.config import USER_ROLES
        role_permissions = USER_ROLES.get(role, {}).get("permissions", [])
        permissions_json = json.dumps(role_permissions)

        password_hash = JWTHandler.get_password_hash(password)
        now = datetime.utcnow().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO web_users (username, password_hash, full_name, role, permissions, department, position, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (username, password_hash, full_name, role, permissions_json, department, position, now)
            )
            user_id = cursor.lastrowid
            conn.commit()

            return user_id

    def get_web_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get web user by username"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM web_users WHERE username = ?", (username,))
            user = cursor.fetchone()
            return dict(user) if user else None

    def get_all_web_users(self) -> List[Dict[str, Any]]:
        """Get all web users"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, full_name, role, department, position, is_active, created_at, last_login FROM web_users ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]

    def update_web_user_role(self, user_id: int, role: str, updated_by: int = None) -> bool:
        """Update user role"""
        import json
        from config.config import USER_ROLES

        # Get role permissions
        role_permissions = USER_ROLES.get(role, {}).get("permissions", [])
        permissions_json = json.dumps(role_permissions)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE web_users SET role = ?, permissions = ? WHERE id = ?",
                (role, permissions_json, user_id)
            )
            return cursor.rowcount > 0

    def get_user_permissions(self, user_id: int) -> List[str]:
        """Get all permissions for a user (from role + custom permissions)"""
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get user role permissions
            cursor.execute(
                "SELECT permissions FROM web_users WHERE id = ? AND is_active = 1",
                (user_id,)
            )
            user_row = cursor.fetchone()
            if not user_row:
                return []

            role_permissions = json.loads(user_row['permissions'] or '[]')

            # Get custom permissions (not expired)
            cursor.execute(
                "SELECT permission FROM user_permissions WHERE user_id = ? AND (expires_at IS NULL OR expires_at > datetime('now'))",
                (user_id,)
            )
            custom_permissions = [row['permission'] for row in cursor.fetchall()]

            # Combine and deduplicate
            all_permissions = list(set(role_permissions + custom_permissions))
            return all_permissions

    def grant_user_permission(self, user_id: int, permission: str, granted_by: int, expires_at: str = None) -> bool:
        """Grant custom permission to user"""
        now = datetime.utcnow().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT OR REPLACE INTO user_permissions (user_id, permission, granted_by, granted_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, permission, granted_by, now, expires_at)
                )
                return True
            except Exception:
                return False

    def revoke_user_permission(self, user_id: int, permission: str) -> bool:
        """Revoke custom permission from user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM user_permissions WHERE user_id = ? AND permission = ?",
                (user_id, permission)
            )
            return cursor.rowcount > 0

    def get_all_roles(self) -> List[Dict[str, Any]]:
        """Get all available roles"""
        import json

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM roles ORDER BY name")
            roles = []
            for row in cursor.fetchall():
                role_dict = dict(row)
                role_dict['permissions'] = json.loads(row['permissions'] or '[]')
                roles.append(role_dict)
            return roles

    def create_role(self, name: str, display_name: str, description: str, permissions: List[str]) -> int:
        """Create new custom role"""
        import json
        now = datetime.utcnow().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO roles (name, display_name, description, permissions, is_system, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, display_name, description, json.dumps(permissions), 0, now)
            )
            return cursor.lastrowid

    def get_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Get all users with specific role"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, full_name, department, position, created_at FROM web_users WHERE role = ? AND is_active = 1",
                (role,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_users_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get all users in specific department"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, full_name, role, position, created_at FROM web_users WHERE department = ? AND is_active = 1",
                (department,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_user_profile(self, user_id: int, full_name: str = None, department: str = None, position: str = None) -> bool:
        """Update user profile information"""
        updates = []
        params = []

        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name)

        if department is not None:
            updates.append("department = ?")
            params.append(department)

        if position is not None:
            updates.append("position = ?")
            params.append(position)

        if not updates:
            return False

        params.append(user_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE web_users SET {', '.join(updates)} WHERE id = ?",
                params
            )
            return cursor.rowcount > 0

    # Analytics methods
    def get_daily_stats(self, date: str) -> Dict[str, Any]:
        """Get daily attendance statistics"""
        # Check cache first
        cached_data = get_cached_analytics_daily(date)
        if cached_data is not None:
            return cached_data

        # Get from database
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Count check-ins and check-outs for the day
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts,
                    COUNT(DISTINCT user_id) as unique_users
                FROM events
                WHERE DATE(ts) = ?
            ''', (date,))

            result = cursor.fetchone()
            data = dict(result) if result else {'checkins': 0, 'checkouts': 0, 'unique_users': 0}

            # Cache the result
            set_cached_analytics_daily(date, data)

            return data

    def get_weekly_stats(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get attendance statistics for date range"""
        # Check cache first (use a composite key for the date range)
        cache_key = f"{start_date}_{end_date}"
        cached_data = get_cached_analytics_weekly()
        if cached_data is not None and cached_data.get("key") == cache_key:
            return cached_data["data"]

        # Get from database
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    DATE(ts) as date,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts,
                    COUNT(DISTINCT user_id) as unique_users
                FROM events
                WHERE DATE(ts) BETWEEN ? AND ?
                GROUP BY DATE(ts)
                ORDER BY DATE(ts)
            ''', (start_date, end_date))

            data = [dict(row) for row in cursor.fetchall()]

            # Cache the result
            set_cached_analytics_weekly({"key": cache_key, "data": data})

            return data

    def get_location_stats(self, date: str = None) -> List[Dict[str, Any]]:
        """Get attendance statistics by location (now shows global stats)"""
        # Check cache first
        cached_data = get_cached_analytics_location(date)
        if cached_data is not None:
            return cached_data

        # Get from database - now shows overall statistics since locations are unified
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = '''
                SELECT
                    'global' as location,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts,
                    COUNT(DISTINCT user_id) as unique_users
                FROM events
            '''
            params = []

            if date:
                query += ' WHERE DATE(ts) = ?'
                params.append(date)

            cursor.execute(query, params)
            data = [dict(row) for row in cursor.fetchall()]

            # Cache the result
            set_cached_analytics_location(data, date)

            return data

    def get_user_stats(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most active users statistics"""
        # Check cache first
        cached_data = get_cached_analytics_users(limit)
        if cached_data is not None:
            return cached_data

        # Get from database
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    e.user_id,
                    p.fio as full_name,
                    p.username,
                    COUNT(*) as total_events,
                    COUNT(CASE WHEN e.action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN e.action = 'out' THEN 1 END) as checkouts,
                    MAX(e.ts) as last_activity
                FROM events e
                LEFT JOIN people p ON e.user_id = p.tg_user_id
                GROUP BY e.user_id, p.fio, p.username
                ORDER BY total_events DESC
                LIMIT ?
            ''', (limit,))

            data = [dict(row) for row in cursor.fetchall()]

            # Cache the result
            set_cached_analytics_users(data, limit)

            return data

    def get_hourly_stats(self, date: str) -> List[Dict[str, Any]]:
        """Get hourly attendance distribution for a date"""
        # Check cache first
        cached_data = get_cached_analytics_hourly(date)
        if cached_data is not None:
            return cached_data

        # Get from database
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    strftime('%H', ts) as hour,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts
                FROM events
                WHERE DATE(ts) = ?
                GROUP BY strftime('%H', ts)
                ORDER BY hour
            ''', (date,))

            data = [dict(row) for row in cursor.fetchall()]

            # Cache the result
            set_cached_analytics_hourly(date, data)

            return data

    def get_monthly_report(self, year: int, month: int) -> Dict[str, Any]:
        """Get comprehensive monthly report"""
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year+1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month+1:02d}-01"

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Monthly totals
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as total_checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as total_checkouts,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT DATE(ts)) as active_days
                FROM events
                WHERE DATE(ts) >= ? AND DATE(ts) < ?
            ''', (start_date, end_date))

            monthly_stats = dict(cursor.fetchone())

            # Daily breakdown
            cursor.execute('''
                SELECT
                    DATE(ts) as date,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts,
                    COUNT(DISTINCT user_id) as unique_users
                FROM events
                WHERE DATE(ts) >= ? AND DATE(ts) < ?
                GROUP BY DATE(ts)
                ORDER BY DATE(ts)
            ''', (start_date, end_date))

            daily_stats = [dict(row) for row in cursor.fetchall()]

            return {
                'period': {'year': year, 'month': month},
                'monthly_totals': monthly_stats,
                'daily_breakdown': daily_stats
            }

    def get_system_health_stats(self) -> Dict[str, Any]:
        """Get system health and usage statistics"""
        # Check cache first
        cached_data = get_cached_system_health()
        if cached_data is not None:
            return cached_data

        # Get from database
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # User counts
            cursor.execute("SELECT COUNT(*) as total_users FROM people")
            total_users = cursor.fetchone()['total_users']

            cursor.execute("SELECT COUNT(*) as total_web_users FROM web_users")
            total_web_users = cursor.fetchone()['total_web_users']

            # Event counts
            cursor.execute("SELECT COUNT(*) as total_events FROM events")
            total_events = cursor.fetchone()['total_events']

            # Recent activity (last 24 hours)
            cursor.execute('''
                SELECT COUNT(*) as recent_events
                FROM events
                WHERE ts >= datetime('now', '-1 day')
            ''')
            recent_events = cursor.fetchone()['recent_events']

            # Token stats
            cursor.execute("SELECT COUNT(*) as active_tokens FROM tokens WHERE used = 0")
            active_tokens = cursor.fetchone()['active_tokens']

            data = {
                'users': {
                    'telegram_users': total_users,
                    'web_users': total_web_users
                },
                'events': {
                    'total': total_events,
                    'recent_24h': recent_events
                },
                'tokens': {
                    'active': active_tokens
                },
                'generated_at': datetime.utcnow().isoformat()
            }

            # Cache the result
            set_cached_system_health(data)

            return data

    # Analytics methods
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get overall analytics summary"""
        # Check cache first
        cache_key = "analytics_summary"
        cached_data = get_cached_analytics_weekly()
        if cached_data:
            return cached_data

        # Get from database
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total users
            cursor.execute("SELECT COUNT(*) FROM people")
            total_users = cursor.fetchone()[0]

            # Currently present
            present_users = len(self.get_currently_present())

            # Today's visits
            today = datetime.utcnow().date().isoformat()
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) FROM events
                WHERE date(ts) = ? AND action = 'in'
            """, (today,))
            today_visits = cursor.fetchone()[0]

            # Average work time (simplified calculation)
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            cursor.execute("""
                SELECT AVG(work_hours) FROM (
                    SELECT
                        user_id,
                        date(ts) as work_date,
                        (strftime('%s', MAX(CASE WHEN action = 'out' THEN ts END)) -
                         strftime('%s', MIN(CASE WHEN action = 'in' THEN ts END))) / 3600.0 as work_hours
                    FROM events
                    WHERE ts >= ? AND action IN ('in', 'out')
                    GROUP BY user_id, date(ts)
                    HAVING work_hours > 0 AND work_hours < 24
                )
            """, (thirty_days_ago,))
            avg_work_time_result = cursor.fetchone()
            avg_work_time = round(avg_work_time_result[0], 1) if avg_work_time_result and avg_work_time_result[0] else 0

            result = {
                'total_users': total_users,
                'currently_present': present_users,
                'today_visits': today_visits,
                'avg_work_time': avg_work_time
            }

            # Cache the result
            set_cached_analytics_weekly(result)

            return result

    def get_daily_visits_chart(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily visits data for chart"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            start_date = (datetime.utcnow() - timedelta(days=days)).date()

            cursor.execute("""
                SELECT
                    date(ts) as visit_date,
                    COUNT(DISTINCT user_id) as visits
                FROM events
                WHERE date(ts) >= ? AND action = 'in'
                GROUP BY date(ts)
                ORDER BY date(ts)
            """, (start_date.isoformat(),))

            return [{'date': row[0], 'visits': row[1]} for row in cursor.fetchall()]

    def get_hourly_distribution(self) -> List[Dict[str, Any]]:
        """Get hourly distribution of visits"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    strftime('%H', ts) as hour,
                    COUNT(*) as count
                FROM events
                WHERE action = 'in'
                GROUP BY strftime('%H', ts)
                ORDER BY hour
            """)

            return [{'hour': int(row[0]), 'count': row[1]} for row in cursor.fetchall()]

    def get_top_workers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top workers by total work time (last 30 days)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

            cursor.execute("""
                SELECT
                    p.fio,
                    COUNT(DISTINCT date(daily_work.work_date)) as work_days,
                    ROUND(AVG(daily_work.work_hours), 1) as total_hours
                FROM (
                    SELECT
                        user_id,
                        date(ts) as work_date,
                        (strftime('%s', MAX(CASE WHEN action = 'out' THEN ts END)) -
                         strftime('%s', MIN(CASE WHEN action = 'in' THEN ts END))) / 3600.0 as work_hours
                    FROM events
                    WHERE ts >= ? AND action IN ('in', 'out')
                    GROUP BY user_id, date(ts)
                    HAVING work_hours > 0 AND work_hours < 24
                ) daily_work
                JOIN people p ON daily_work.user_id = p.tg_user_id
                GROUP BY daily_work.user_id, p.fio
                HAVING AVG(daily_work.work_hours) > 0
                ORDER BY AVG(daily_work.work_hours) DESC
                LIMIT ?
            """, (thirty_days_ago, limit))

            return [{'name': row[0], 'work_days': row[1], 'total_hours': row[2]} for row in cursor.fetchall()]

    def get_department_stats(self) -> List[Dict[str, Any]]:
        """Get statistics by department (includes both web users and regular employees)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get stats for web users by department
            cursor.execute("""
                SELECT
                    COALESCE(wu.department, 'Администраторы') as department,
                    COUNT(DISTINCT wu.id) as user_count,
                    COUNT(DISTINCT CASE WHEN wu.id IN (
                        SELECT DISTINCT CAST(user_id AS TEXT) FROM events WHERE action = 'in'
                    ) THEN wu.id END) as active_users,
                    'web' as user_type
                FROM web_users wu
                GROUP BY wu.department
            """)

            web_stats = cursor.fetchall()

            # Get stats for regular employees (from people table)
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT p.id) as user_count,
                    COUNT(DISTINCT CASE WHEN p.tg_user_id IN (
                        SELECT DISTINCT user_id FROM events WHERE action = 'in'
                    ) THEN p.id END) as active_users
                FROM people p
            """)

            employee_stats = cursor.fetchone()
            if employee_stats and employee_stats[0] > 0:
                # Add regular employees as separate category
                web_stats.append(('Сотрудники', employee_stats[0], employee_stats[1], 'regular'))

            # Sort by user count descending
            result = []
            for row in sorted(web_stats, key=lambda x: x[1], reverse=True):
                result.append({
                    'department': row[0],
                    'user_count': row[1],
                    'active_users': row[2],
                    'user_type': row[3]
                })

            return result

    def get_employee_list(self) -> List[Dict[str, Any]]:
        """Get list of all employees for selection"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    p.id,
                    p.tg_user_id,
                    p.fio,
                    p.username,
                    p.created_at,
                    COUNT(DISTINCT date(e.ts)) as work_days,
                    COUNT(CASE WHEN e.action = 'in' THEN 1 END) as checkins_count,
                    COUNT(CASE WHEN e.action = 'out' THEN 1 END) as checkouts_count
                FROM people p
                LEFT JOIN events e ON p.tg_user_id = e.user_id
                GROUP BY p.id, p.tg_user_id, p.fio, p.username, p.created_at
                ORDER BY p.fio
            """)

            return [dict(row) for row in cursor.fetchall()]

    def get_employee_detailed_stats(self, employee_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a specific employee"""
        # Check cache first
        cache_key = f"employee_stats_{employee_id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        # Get from database
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Basic info
            cursor.execute("""
                SELECT id, tg_user_id, fio, username, created_at
                FROM people
                WHERE id = ?
            """, (employee_id,))

            employee = cursor.fetchone()
            if not employee:
                return None

            result = dict(employee)

            # Current status (last event)
            cursor.execute("""
                SELECT action, ts
                FROM events
                WHERE user_id = ?
                ORDER BY ts DESC
                LIMIT 1
            """, (result['tg_user_id'],))

            last_event = cursor.fetchone()
            result['current_status'] = dict(last_event) if last_event else None
            result['is_present'] = last_event and last_event[0] == 'in'

            # Total statistics
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT date(ts)) as total_work_days,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as total_checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as total_checkouts,
                    MIN(date(ts)) as first_visit,
                    MAX(date(ts)) as last_visit
                FROM events
                WHERE user_id = ?
            """, (result['tg_user_id'],))

            stats = cursor.fetchone()
            result.update(dict(stats))

            # Monthly statistics (last 12 months)
            cursor.execute("""
                SELECT
                    strftime('%Y-%m', ts) as month,
                    COUNT(DISTINCT date(ts)) as work_days,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins
                FROM events
                WHERE user_id = ? AND ts >= date('now', '-12 months')
                GROUP BY strftime('%Y-%m', ts)
                ORDER BY month DESC
            """, (result['tg_user_id'],))

            result['monthly_stats'] = [dict(row) for row in cursor.fetchall()]

            # Daily work time statistics (last 10 days)
            cursor.execute("""
                SELECT
                    date(ts) as work_date,
                    strftime('%H:%M', MIN(CASE WHEN action = 'in' THEN ts END)) as checkin_time,
                    strftime('%H:%M', MAX(CASE WHEN action = 'out' THEN ts END)) as checkout_time,
                    ROUND((strftime('%s', MAX(CASE WHEN action = 'out' THEN ts END)) -
                           strftime('%s', MIN(CASE WHEN action = 'in' THEN ts END))) / 3600.0, 2) as work_hours
                FROM events
                WHERE user_id = ? AND ts >= date('now', '-30 days')
                GROUP BY date(ts)
                HAVING work_hours > 0
                ORDER BY work_date DESC
                LIMIT 10
            """, (result['tg_user_id'],))

            result['recent_sessions'] = [dict(row) for row in cursor.fetchall()]

            # Average work time
            cursor.execute("""
                SELECT ROUND(AVG(work_hours), 2) as avg_work_time
                FROM (
                    SELECT
                        date(ts) as work_date,
                        (strftime('%s', MAX(CASE WHEN action = 'out' THEN ts END)) -
                         strftime('%s', MIN(CASE WHEN action = 'in' THEN ts END))) / 3600.0 as work_hours
                    FROM events
                    WHERE user_id = ?
                    GROUP BY date(ts)
                    HAVING work_hours > 0 AND work_hours < 24
                )
            """, (result['tg_user_id'],))

            avg_result = cursor.fetchone()
            result['avg_work_time'] = avg_result[0] if avg_result and avg_result[0] else 0

            # Cache the result
            cache.set(cache_key, result, CACHE_TTL_USER)

            return result
