import sqlite3
from datetime import datetime, timedelta, timezone
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
        self.initial_credentials = []  # runtime-only: show once in admin UI
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
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

            # Meta table (key/value)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT
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
            
            # Audit log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    user_id     INTEGER,
                    username    TEXT,
                    target_type TEXT,
                    target_id   INTEGER,
                    details     TEXT,
                    ip_address  TEXT,
                    user_agent  TEXT,
                    created_at  TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES web_users (id)
                )
            ''')
            
            # Vacations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vacations (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    start_date  TEXT NOT NULL,
                    end_date    TEXT NOT NULL,
                    days_count  INTEGER NOT NULL,
                    vacation_type TEXT DEFAULT 'annual',
                    status      TEXT DEFAULT 'pending',
                    created_by  INTEGER,
                    approved_by INTEGER,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT,
                    notes       TEXT,
                    FOREIGN KEY (user_id) REFERENCES people (id),
                    FOREIGN KEY (created_by) REFERENCES web_users (id),
                    FOREIGN KEY (approved_by) REFERENCES web_users (id)
                )
            ''')
            
            # Sick leaves table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sick_leaves (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    start_date  TEXT NOT NULL,
                    end_date    TEXT NOT NULL,
                    days_count  INTEGER NOT NULL,
                    status      TEXT DEFAULT 'pending',
                    created_by  INTEGER,
                    approved_by INTEGER,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT,
                    notes       TEXT,
                    FOREIGN KEY (user_id) REFERENCES people (id),
                    FOREIGN KEY (created_by) REFERENCES web_users (id),
                    FOREIGN KEY (approved_by) REFERENCES web_users (id)
                )
            ''')
            
            # Report templates table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS report_templates (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL,
                    description TEXT,
                    template_type TEXT NOT NULL,
                    config      TEXT NOT NULL,
                    created_by  INTEGER,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT,
                    FOREIGN KEY (created_by) REFERENCES web_users (id)
                )
            ''')

            # Useful indexes for performance optimization
            # Events table indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events (user_id, ts)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_action ON events (action)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_action_ts ON events (action, ts)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_location ON events (location)")
            
            # People table indexes
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_people_tg_user_id ON people (tg_user_id)")
            
            # Tokens table indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_used_created ON tokens (used, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_token_used ON tokens (token, used)")
            
            # Web users table indexes
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_web_users_username ON web_users (username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web_users_role_active ON web_users (role, is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web_users_department ON web_users (department)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_web_users_is_active ON web_users (is_active)")
            
            # User permissions table indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_permissions_expires ON user_permissions (expires_at)")
            
            # Audit log indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_action_type ON audit_log (action_type)")
            
            # Vacations indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vacations_user_id ON vacations (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vacations_dates ON vacations (start_date, end_date)")
            
            # Sick leaves indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sick_leaves_user_id ON sick_leaves (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sick_leaves_dates ON sick_leaves (start_date, end_date)")

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
                    ("terminal", "Terminal Service", "terminal"),
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

                # Store for one-time display (not persisted)
                self.initial_credentials = creds

                # Log that credentials were created (passwords shown only in admin UI on first load)
                import logging
                _init_logger = logging.getLogger("attendance.init")
                _init_logger.warning("[INIT] Default users created (empty DB). Credentials available on first admin page load only.")
            else:
                self.initial_credentials = []

            conn.commit()

    def consume_initial_credentials(self):
        """Return and clear one-time initial credentials."""
        creds = self.initial_credentials
        self.initial_credentials = []
        return creds

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

    def get_employee_stats_by_tg(self, tg_user_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed stats using Telegram user id"""
        person = self.get_person_by_tg_id(tg_user_id)
        if not person:
            return None
        return self.get_employee_detailed_stats(person["id"])

    def provision_web_credentials(self, tg_user_id: int, fio: str) -> Dict[str, str]:
        """
        Create a linked web user with role 'user' and return generated credentials.
        Username основан на tg_user_id (стабилен, даже если @username меняется).
        """
        base_username = f"user{tg_user_id}"

        candidate = base_username
        suffix = 1
        while self.get_web_user_by_username(candidate):
            candidate = f"{base_username}{suffix}"
            suffix += 1

        password_plain = secrets.token_urlsafe(8)
        self.create_web_user(
            username=candidate,
            password=password_plain,
            full_name=fio,
            role="user"
        )

        return {"username": candidate, "password": password_plain}

    def ensure_web_user_for_person(self, tg_user_id: int, fio: str) -> Optional[Dict[str, str]]:
        """
        Ensure a web user exists for given tg_user_id. If not, create and return creds.
        Returns None if user already exists.
        """
        base_username = f"user{tg_user_id}"
        existing = self.get_web_user_by_username(base_username)
        if existing:
            return None

        return self.provision_web_credentials(tg_user_id=tg_user_id, fio=fio)

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

    def mark_token_used_if_valid(self, token: str) -> bool:
        """Atomically check if token is valid and mark it as used.
        Prevents race condition where two users use the same token."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Atomic UPDATE with WHERE conditions ensures only one caller succeeds
            cursor.execute(
                "UPDATE tokens SET used = 1 WHERE token = ? AND used = 0 AND (expires_at IS NULL OR expires_at > datetime('now'))",
                (token,)
            )
            success = cursor.rowcount > 0
            conn.commit()
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
        # Сохраняем время в UTC с timezone info
        now = datetime.now(timezone.utc).isoformat()
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

    def get_open_sessions_older_than(self, hours: float) -> List[Dict[str, Any]]:
        """Get users with open sessions (last event is 'in') older than specified hours"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Get users with last event 'in' older than N hours
            cursor.execute('''
                SELECT e.*, p.fio, p.username, p.tg_user_id,
                       (julianday('now') - julianday(e.ts)) * 24 as hours_open
                FROM events e
                JOIN people p ON e.user_id = p.tg_user_id
                WHERE e.id IN (
                    SELECT MAX(id)
                    FROM events
                    GROUP BY user_id
                ) AND e.action = 'in'
                AND (julianday('now') - julianday(e.ts)) * 24 >= ?
                ORDER BY e.ts ASC
            ''', (hours,))
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
                checkin_time = datetime.fromisoformat(event['ts'].replace('Z', '+00:00'))
            elif event['action'] == 'out' and checkin_time:
                checkout_time = datetime.fromisoformat(event['ts'].replace('Z', '+00:00'))
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
            conn.commit()
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
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def revoke_user_permission(self, user_id: int, permission: str) -> bool:
        """Revoke custom permission from user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM user_permissions WHERE user_id = ? AND permission = ?",
                (user_id, permission)
            )
            conn.commit()
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
            conn.commit()
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
            conn.commit()
            return cursor.rowcount > 0

    def get_web_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get web user by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM web_users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            return dict(user) if user else None

    def update_web_user(self, user_id: int, full_name: str = None, role: str = None, 
                       department: str = None, position: str = None, 
                       is_active: bool = None, password: str = None,
                       updated_by: int = None) -> bool:
        """Update web user information"""
        import json
        from config.config import USER_ROLES
        
        updates = []
        params = []

        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name)

        if role is not None:
            updates.append("role = ?")
            params.append(role)
            # Update permissions based on role
            role_permissions = USER_ROLES.get(role, {}).get("permissions", [])
            updates.append("permissions = ?")
            params.append(json.dumps(role_permissions))

        if department is not None:
            updates.append("department = ?")
            params.append(department)

        if position is not None:
            updates.append("position = ?")
            params.append(position)

        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if password is not None:
            from auth.jwt_handler import JWTHandler
            password_hash = JWTHandler.get_password_hash(password)
            updates.append("password_hash = ?")
            params.append(password_hash)

        if not updates:
            return False

        params.append(user_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE web_users SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
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
            # Optimized: use date range instead of DATE() function for better index usage
            date_start = f"{date}T00:00:00"
            date_end = f"{date}T23:59:59"
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts,
                    COUNT(DISTINCT user_id) as unique_users
                FROM events
                WHERE ts >= ? AND ts <= ?
            ''', (date_start, date_end))

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

            # Optimized: use date range with DATE() only in GROUP BY for better performance
            start_datetime = f"{start_date}T00:00:00"
            end_datetime = f"{end_date}T23:59:59"
            cursor.execute('''
                SELECT
                    DATE(ts) as date,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts,
                    COUNT(DISTINCT user_id) as unique_users
                FROM events
                WHERE ts >= ? AND ts <= ?
                GROUP BY DATE(ts)
                ORDER BY DATE(ts)
            ''', (start_datetime, end_datetime))

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
                # Optimized: use date range instead of DATE() function
                date_start = f"{date}T00:00:00"
                date_end = f"{date}T23:59:59"
                query += ' WHERE ts >= ? AND ts <= ?'
                params.extend([date_start, date_end])

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

            # Optimized: use date range instead of DATE() function
            date_start = f"{date}T00:00:00"
            date_end = f"{date}T23:59:59"
            cursor.execute('''
                SELECT
                    strftime('%H', ts) as hour,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts
                FROM events
                WHERE ts >= ? AND ts <= ?
                GROUP BY strftime('%H', ts)
                ORDER BY hour
            ''', (date_start, date_end))

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

            # Monthly totals (optimized: use date range in WHERE, DATE() only in SELECT)
            start_datetime = f"{start_date}T00:00:00"
            end_datetime = f"{end_date}T00:00:00"
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as total_checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as total_checkouts,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT DATE(ts)) as active_days
                FROM events
                WHERE ts >= ? AND ts < ?
            ''', (start_datetime, end_datetime))

            monthly_stats = dict(cursor.fetchone())

            # Daily breakdown (optimized: use date range in WHERE)
            start_datetime = f"{start_date}T00:00:00"
            end_datetime = f"{end_date}T00:00:00"
            cursor.execute('''
                SELECT
                    DATE(ts) as date,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts,
                    COUNT(DISTINCT user_id) as unique_users
                FROM events
                WHERE ts >= ? AND ts < ?
                GROUP BY DATE(ts)
                ORDER BY DATE(ts)
            ''', (start_datetime, end_datetime))

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

            # Today's visits (optimized: use date range instead of DATE() function)
            today = datetime.utcnow().date().isoformat()
            today_start = f"{today}T00:00:00"
            today_end = f"{today}T23:59:59"
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) FROM events
                WHERE ts >= ? AND ts <= ? AND action = 'in'
            """, (today_start, today_end))
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
            # Optimized: use date range instead of DATE() in WHERE clause
            start_datetime = f"{start_date.isoformat()}T00:00:00"

            cursor.execute("""
                SELECT
                    date(ts) as visit_date,
                    COUNT(DISTINCT user_id) as visits
                FROM events
                WHERE ts >= ? AND action = 'in'
                GROUP BY date(ts)
                ORDER BY date(ts)
            """, (start_datetime,))

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

    def get_employees_by_date(self, date: str) -> List[Dict[str, Any]]:
        """Get list of employees who visited on a specific date with all work intervals"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Получаем все события за день по пользователям сразу, чтобы собрать интервалы
            cursor.execute(
                """
                SELECT
                    e.user_id,
                    e.action,
                    e.ts,
                    p.fio,
                    p.username,
                    p.tg_user_id
                FROM events e
                JOIN people p ON e.user_id = p.tg_user_id
                WHERE e.ts >= ? AND e.ts <= ?
                ORDER BY e.user_id, e.ts
                """,
                (f"{date}T00:00:00", f"{date}T23:59:59")
            )

            employees: Dict[int, Dict[str, Any]] = {}

            for row in cursor.fetchall():
                user_id = row["user_id"]
                action = row["action"]
                ts = row["ts"]

                if user_id not in employees:
                    employees[user_id] = {
                        "fio": row["fio"],
                        "username": row["username"],
                        "tg_user_id": row["tg_user_id"],
                        "checkins_count": 0,
                        "checkouts_count": 0,
                        "checkin_time": None,
                        "checkout_time": None,
                        "intervals": [],
                        "_open_start": None,  # служебное поле для сборки интервалов
                    }

                emp = employees[user_id]

                # Подсчет приходов/уходов и запоминание первого/последнего времени
                if action == "in":
                    emp["checkins_count"] += 1
                    if not emp["checkin_time"]:
                        emp["checkin_time"] = ts
                    emp["_open_start"] = ts
                elif action == "out":
                    emp["checkouts_count"] += 1
                    emp["checkout_time"] = ts
                    if emp.get("_open_start"):
                        emp["intervals"].append(
                            {"start": emp["_open_start"], "end": ts}
                        )
                        emp["_open_start"] = None

            # Завершаем сборку: форматируем времена и приводим интервалы к HH:MM
            result: List[Dict[str, Any]] = []
            for emp in employees.values():
                # Если смена открыта и не было выхода — добавляем незавершённый интервал
                if emp.get("_open_start"):
                    emp["intervals"].append({"start": emp["_open_start"], "end": None})

                # Форматирование времени (конвертация из UTC в MSK)
                msk_offset = timedelta(hours=3)  # MSK = UTC+3

                def format_time_utc_to_msk(iso_time: str) -> str:
                    """Convert UTC ISO time to MSK HH:MM format"""
                    if not iso_time:
                        return None
                    # Парсим как UTC время
                    utc_time = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
                    if utc_time.tzinfo is None:
                        utc_time = utc_time.replace(tzinfo=timezone.utc)
                    # Конвертируем в MSK
                    msk_time = utc_time + msk_offset
                    return msk_time.strftime("%H:%M")

                if emp["checkin_time"]:
                    emp["checkin_time"] = format_time_utc_to_msk(emp["checkin_time"])
                if emp["checkout_time"]:
                    emp["checkout_time"] = format_time_utc_to_msk(emp["checkout_time"])

                formatted_intervals = []
                for interval in emp["intervals"]:
                    start_fmt = format_time_utc_to_msk(interval["start"])
                    end_fmt = format_time_utc_to_msk(interval["end"]) if interval["end"] else None
                    formatted_intervals.append({"start": start_fmt, "end": end_fmt})

                emp["intervals"] = formatted_intervals

                # Удаляем служебное поле
                emp.pop("_open_start", None)
                result.append(emp)

            # Сортируем по первому приходу (checkin_time) для стабильного порядка
            result.sort(key=lambda x: x["checkin_time"] or "")
            return result

    def get_top_workers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top workers by total work time (last 30 days)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

            # Используем Python для точного расчета времени работы с учетом всех интервалов
            cursor.execute("""
                SELECT
                    p.id,
                    p.fio,
                    p.tg_user_id,
                    e.ts,
                    e.action
                FROM events e
                JOIN people p ON e.user_id = p.tg_user_id
                WHERE e.ts >= ? AND e.action IN ('in', 'out')
                ORDER BY p.tg_user_id, e.ts
            """, (thirty_days_ago,))

            # Группируем события по пользователям и дням, считаем время работы
            user_stats = {}
            current_user = None
            current_date = None
            checkin_time = None
            daily_hours = {}
            
            for row in cursor.fetchall():
                user_id = row[2]  # tg_user_id (правильный индекс)
                fio = row[1]      # fio (правильный индекс)
                ts_str = row[3]   # ts
                action = row[4]   # action
                
                # Парсим дату
                event_time = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                event_date = event_time.date()
                
                key = (user_id, event_date)
                
                if key not in daily_hours:
                    daily_hours[key] = {'fio': fio, 'total_seconds': 0, 'checkin_time': None}
                
                if action == 'in':
                    daily_hours[key]['checkin_time'] = event_time
                elif action == 'out' and daily_hours[key]['checkin_time']:
                    checkout_time = event_time
                    work_seconds = (checkout_time - daily_hours[key]['checkin_time']).total_seconds()
                    if 0 < work_seconds < 86400:  # Валидация: от 0 до 24 часов
                        daily_hours[key]['total_seconds'] += work_seconds
                    daily_hours[key]['checkin_time'] = None
            
            # Агрегируем по пользователям
            user_totals = {}
            for (user_id, date), data in daily_hours.items():
                if data['total_seconds'] > 0:
                    if user_id not in user_totals:
                        user_totals[user_id] = {
                            'fio': data['fio'],
                            'work_days': 0,
                            'total_hours': 0.0
                        }
                    user_totals[user_id]['work_days'] += 1
                    user_totals[user_id]['total_hours'] += data['total_seconds'] / 3600.0
            
            # Сортируем и возвращаем топ
            sorted_users = sorted(
                user_totals.values(),
                key=lambda x: x['total_hours'],
                reverse=True
            )[:limit]
            
            return [
                {
                    'name': user['fio'],
                    'work_days': user['work_days'],
                    'total_hours': round(user['total_hours'], 1)
                }
                for user in sorted_users
            ]

    def get_department_stats(self) -> List[Dict[str, Any]]:
        """Get statistics by department (includes both web users and regular employees)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get stats for web users by role (group admin users separately)
            cursor.execute("""
                SELECT
                    CASE 
                        WHEN wu.role = 'admin' THEN 'Администраторы'
                        WHEN wu.role = 'manager' THEN 'Менеджеры'
                        WHEN wu.role = 'hr' THEN 'HR'
                        WHEN wu.role = 'user' THEN 'Пользователи'
                        WHEN wu.role = 'terminal' THEN 'Терминал'
                        ELSE COALESCE(wu.department, 'Прочие')
                    END as department,
                    COUNT(DISTINCT wu.id) as user_count,
                    COUNT(DISTINCT CASE WHEN wu.id IN (
                        SELECT DISTINCT CAST(user_id AS TEXT) FROM events WHERE action = 'in'
                    ) THEN wu.id END) as active_users,
                    'web' as user_type
                FROM web_users wu
                GROUP BY 
                    CASE 
                        WHEN wu.role = 'admin' THEN 'Администраторы'
                        WHEN wu.role = 'manager' THEN 'Менеджеры'
                        WHEN wu.role = 'hr' THEN 'HR'
                        WHEN wu.role = 'user' THEN 'Пользователи'
                        WHEN wu.role = 'terminal' THEN 'Терминал'
                        ELSE COALESCE(wu.department, 'Прочие')
                    END
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
                    strftime('%H:%M', datetime(MIN(CASE WHEN action = 'in' THEN ts END), '+3 hours')) as checkin_time,
                    strftime('%H:%M', datetime(MAX(CASE WHEN action = 'out' THEN ts END), '+3 hours')) as checkout_time,
                    ROUND((strftime('%s', datetime(MAX(CASE WHEN action = 'out' THEN ts END), '+3 hours')) -
                           strftime('%s', datetime(MIN(CASE WHEN action = 'in' THEN ts END), '+3 hours'))) / 3600.0, 2) as work_hours
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

    def get_pivot_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Получить отчет в формате сводной таблицы (pivot table).
        
        Формат: фамилии слева, дни сверху, часы на пересечении.
        
        Args:
            start_date: Начальная дата в формате YYYY-MM-DD
            end_date: Конечная дата в формате YYYY-MM-DD
        
        Returns:
            Dict с ключами:
            - employees: список сотрудников с id, tg_user_id, fio
            - days: список дат в формате YYYY-MM-DD
            - data: словарь {employee_id: {date: hours, ...}, ...}
            - totals: словарь {employee_id: total_hours, ...}
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем список всех сотрудников, у которых есть события в периоде
            cursor.execute("""
                SELECT DISTINCT p.id, p.tg_user_id, p.fio
                FROM people p
                WHERE EXISTS (
                    SELECT 1 FROM events e
                    WHERE e.user_id = p.tg_user_id
                    AND e.ts >= ? AND e.ts <= ?
                )
                ORDER BY p.fio
            """, (f"{start_date}T00:00:00", f"{end_date}T23:59:59"))
            
            employees = [dict(row) for row in cursor.fetchall()]
            
            # Генерируем список всех дней в периоде
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            days = []
            current = start
            while current <= end:
                days.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)
            
            # Fetch all events in the date range in a single query (avoids N+1)
            tg_id_to_employee_id = {emp['tg_user_id']: emp['id'] for emp in employees}
            tg_ids = list(tg_id_to_employee_id.keys())

            data = {emp['id']: {} for emp in employees}
            totals = {emp['id']: 0.0 for emp in employees}

            if tg_ids:
                placeholders = ','.join('?' * len(tg_ids))
                cursor.execute(f"""
                    SELECT user_id, action, ts
                    FROM events
                    WHERE user_id IN ({placeholders})
                    AND ts >= ? AND ts <= ?
                    ORDER BY user_id, ts
                """, (*tg_ids, f"{start_date}T00:00:00", f"{end_date}T23:59:59"))

                # Group events by (user_id, date) and calculate work hours via interval pairing
                from collections import defaultdict
                user_day_events = defaultdict(list)
                for row in cursor.fetchall():
                    uid = row[0]
                    ts_str = row[2][:10]  # Extract YYYY-MM-DD
                    user_day_events[(uid, ts_str)].append({'action': row[1], 'ts': row[2]})

                for (tg_uid, day_str), events_list in user_day_events.items():
                    employee_id = tg_id_to_employee_id.get(tg_uid)
                    if employee_id is None:
                        continue
                    # Pair check-in/check-out intervals
                    events_list.sort(key=lambda e: e['ts'])
                    total_secs = 0
                    checkin_time = None
                    for ev in events_list:
                        if ev['action'] == 'in':
                            try:
                                checkin_time = datetime.fromisoformat(ev['ts'].replace('Z', '+00:00'))
                            except Exception:
                                checkin_time = None
                        elif ev['action'] == 'out' and checkin_time:
                            try:
                                checkout_time = datetime.fromisoformat(ev['ts'].replace('Z', '+00:00'))
                                total_secs += (checkout_time - checkin_time).total_seconds()
                            except Exception:
                                pass
                            checkin_time = None
                    hours = total_secs / 3600
                    data[employee_id][day_str] = hours
                    totals[employee_id] += hours
            
            return {
                "employees": employees,
                "days": days,
                "data": data,
                "totals": totals
            }

    def compare_periods(self, period1_start: str, period1_end: str, period2_start: str, period2_end: str) -> Dict[str, Any]:
        """
        Сравнить два периода по различным метрикам.
        
        Args:
            period1_start, period1_end: Первый период (YYYY-MM-DD)
            period2_start, period2_end: Второй период (YYYY-MM-DD)
        
        Returns:
            Dict с сравнением метрик
        """
        def get_period_stats(start: str, end: str):
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT user_id) as unique_users,
                        COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                        COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts,
                        COUNT(DISTINCT date(ts)) as work_days
                    FROM events
                    WHERE ts >= ? AND ts <= ?
                """, (f"{start}T00:00:00", f"{end}T23:59:59"))
                
                row = cursor.fetchone()
                return {
                    "unique_users": row[0],
                    "checkins": row[1],
                    "checkouts": row[2],
                    "work_days": row[3]
                }
        
        stats1 = get_period_stats(period1_start, period1_end)
        stats2 = get_period_stats(period2_start, period2_end)
        
        return {
            "period1": {
                "start": period1_start,
                "end": period1_end,
                "stats": stats1
            },
            "period2": {
                "start": period2_start,
                "end": period2_end,
                "stats": stats2
            },
            "comparison": {
                "unique_users_diff": stats2["unique_users"] - stats1["unique_users"],
                "checkins_diff": stats2["checkins"] - stats1["checkins"],
                "checkouts_diff": stats2["checkouts"] - stats1["checkouts"],
                "work_days_diff": stats2["work_days"] - stats1["work_days"]
            }
        }

    def get_late_arrivals_stats(self, start_date: str, end_date: str, late_threshold_hours: int = 9) -> List[Dict[str, Any]]:
        """
        Получить статистику опозданий (приход после указанного часа).
        
        Args:
            start_date, end_date: Период (YYYY-MM-DD)
            late_threshold_hours: Час, после которого считается опозданием (по умолчанию 9)
        
        Returns:
            Список записей с информацией об опозданиях
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    p.fio,
                    date(e.ts) as work_date,
                    strftime('%H:%M', datetime(e.ts, '+3 hours')) as arrival_time,
                    COUNT(*) as late_count
                FROM events e
                JOIN people p ON e.user_id = p.tg_user_id
                WHERE e.action = 'in'
                AND e.ts >= ? AND e.ts <= ?
                AND CAST(strftime('%H', datetime(e.ts, '+3 hours')) AS INTEGER) >= ?
                GROUP BY p.fio, date(e.ts), strftime('%H:%M', datetime(e.ts, '+3 hours'))
                ORDER BY work_date DESC, arrival_time DESC
            """, (f"{start_date}T00:00:00", f"{end_date}T23:59:59", late_threshold_hours))
            
            return [dict(row) for row in cursor.fetchall()]

    def get_overtime_report(self, start_date: str, end_date: str, standard_hours_per_day: float = 8.0) -> List[Dict[str, Any]]:
        """
        Получить отчет по переработкам.
        
        Args:
            start_date, end_date: Период (YYYY-MM-DD)
            standard_hours_per_day: Стандартное количество часов в день
        
        Returns:
            Список записей с информацией о переработках
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    p.fio,
                    date(e.ts) as work_date,
                    (strftime('%s', MAX(CASE WHEN e2.action = 'out' THEN e2.ts END)) -
                     strftime('%s', MIN(CASE WHEN e2.action = 'in' THEN e2.ts END))) / 3600.0 as work_hours
                FROM events e
                JOIN people p ON e.user_id = p.tg_user_id
                JOIN events e2 ON e2.user_id = e.user_id AND date(e2.ts) = date(e.ts)
                WHERE e.ts >= ? AND e.ts <= ?
                AND e.action = 'in'
                GROUP BY p.fio, date(e.ts)
                HAVING work_hours > ?
                ORDER BY work_hours DESC
            """, (f"{start_date}T00:00:00", f"{end_date}T23:59:59", standard_hours_per_day))
            
            results = []
            for row in cursor.fetchall():
                work_hours = row[2]
                overtime = work_hours - standard_hours_per_day
                results.append({
                    "fio": row[0],
                    "work_date": row[1],
                    "work_hours": round(work_hours, 2),
                    "standard_hours": standard_hours_per_day,
                    "overtime": round(overtime, 2)
                })
            
            return results

    def get_weekly_distribution(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Получить распределение рабочего времени по дням недели.
        
        Args:
            start_date, end_date: Период (YYYY-MM-DD)
        
        Returns:
            Dict с распределением по дням недели
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    CASE CAST(strftime('%w', date(ts)) AS INTEGER)
                        WHEN 0 THEN 'Воскресенье'
                        WHEN 1 THEN 'Понедельник'
                        WHEN 2 THEN 'Вторник'
                        WHEN 3 THEN 'Среда'
                        WHEN 4 THEN 'Четверг'
                        WHEN 5 THEN 'Пятница'
                        WHEN 6 THEN 'Суббота'
                    END as day_of_week,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(CASE WHEN action = 'in' THEN 1 END) as checkins,
                    COUNT(CASE WHEN action = 'out' THEN 1 END) as checkouts
                FROM events
                WHERE ts >= ? AND ts <= ?
                GROUP BY strftime('%w', date(ts))
                ORDER BY strftime('%w', date(ts))
            """, (f"{start_date}T00:00:00", f"{end_date}T23:59:59"))
            
            distribution = {}
            for row in cursor.fetchall():
                distribution[row[0]] = {
                    "unique_users": row[1],
                    "checkins": row[2],
                    "checkouts": row[3]
                }
            
            return distribution

    def add_audit_log_entry(
        self,
        action_type: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> int:
        """
        Добавить запись в журнал аудита.
        
        Args:
            action_type: Тип действия (например, 'user_created', 'user_updated', 'export_report')
            user_id: ID пользователя, выполнившего действие
            username: Имя пользователя
            target_type: Тип объекта действия (например, 'user', 'report')
            target_id: ID объекта действия
            details: Дополнительные детали (JSON строка)
            ip_address: IP адрес
            user_agent: User-Agent заголовок
        
        Returns:
            ID созданной записи
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO audit_log 
                (action_type, user_id, username, target_type, target_id, details, ip_address, user_agent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (action_type, user_id, username, target_type, target_id, details, ip_address, user_agent, now))
            
            conn.commit()
            return cursor.lastrowid

    def get_audit_log(
        self,
        limit: int = 100,
        offset: int = 0,
        action_type: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить записи из журнала аудита.
        
        Args:
            limit: Максимальное количество записей
            offset: Смещение для пагинации
            action_type: Фильтр по типу действия
            user_id: Фильтр по ID пользователя
            start_date, end_date: Фильтр по дате (YYYY-MM-DD)
        
        Returns:
            Список записей аудита
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM audit_log WHERE 1=1"
            params = []
            
            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if start_date:
                query += " AND created_at >= ?"
                params.append(f"{start_date}T00:00:00")
            
            if end_date:
                query += " AND created_at <= ?"
                params.append(f"{end_date}T23:59:59")
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def create_vacation(
        self,
        user_id: int,
        start_date: str,
        end_date: str,
        vacation_type: str = "annual",
        created_by: Optional[int] = None,
        notes: Optional[str] = None
    ) -> int:
        """Создать запись об отпуске"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            days_count = (end - start).days + 1
            
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO vacations 
                (user_id, start_date, end_date, days_count, vacation_type, status, created_by, created_at, notes)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """, (user_id, start_date, end_date, days_count, vacation_type, created_by, now, notes))
            
            conn.commit()
            return cursor.lastrowid

    def get_vacations(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить список отпусков"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT v.*, p.fio as employee_name
                FROM vacations v
                JOIN people p ON v.user_id = p.id
                WHERE 1=1
            """
            params = []
            
            if user_id:
                query += " AND v.user_id = ?"
                params.append(user_id)
            
            if status:
                query += " AND v.status = ?"
                params.append(status)
            
            if start_date:
                query += " AND v.end_date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND v.start_date <= ?"
                params.append(end_date)
            
            query += " ORDER BY v.start_date DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def create_sick_leave(
        self,
        user_id: int,
        start_date: str,
        end_date: str,
        created_by: Optional[int] = None,
        notes: Optional[str] = None
    ) -> int:
        """Создать запись о больничном"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            days_count = (end - start).days + 1
            
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO sick_leaves 
                (user_id, start_date, end_date, days_count, status, created_by, created_at, notes)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            """, (user_id, start_date, end_date, days_count, created_by, now, notes))
            
            conn.commit()
            return cursor.lastrowid

    def get_sick_leaves(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить список больничных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT s.*, p.fio as employee_name
                FROM sick_leaves s
                JOIN people p ON s.user_id = p.id
                WHERE 1=1
            """
            params = []
            
            if user_id:
                query += " AND s.user_id = ?"
                params.append(user_id)
            
            if status:
                query += " AND s.status = ?"
                params.append(status)
            
            if start_date:
                query += " AND s.end_date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND s.start_date <= ?"
                params.append(end_date)
            
            query += " ORDER BY s.start_date DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def create_report_template(
        self,
        name: str,
        template_type: str,
        config: str,
        created_by: Optional[int] = None,
        description: Optional[str] = None
    ) -> int:
        """Создать шаблон отчета"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO report_templates 
                (name, description, template_type, config, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, description, template_type, config, created_by, now))
            
            conn.commit()
            return cursor.lastrowid

    def get_report_templates(self, template_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить список шаблонов отчетов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if template_type:
                cursor.execute("""
                    SELECT * FROM report_templates 
                    WHERE template_type = ?
                    ORDER BY created_at DESC
                """, (template_type,))
            else:
                cursor.execute("SELECT * FROM report_templates ORDER BY created_at DESC")
            
            return [dict(row) for row in cursor.fetchall()]

    def delete_report_template(self, template_id: int) -> bool:
        """Удалить шаблон отчета"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM report_templates WHERE id = ?", (template_id,))
            conn.commit()
            return cursor.rowcount > 0
