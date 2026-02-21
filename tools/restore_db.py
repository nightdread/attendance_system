#!/usr/bin/env python3
"""
Database restore script for attendance system
"""
import os
import sys
import sqlite3
import shutil
import gzip
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _load_dotenv(env_path: Path) -> None:
    """Load .env file into os.environ (setdefault so existing env wins)."""
    if not env_path.is_file():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"").strip()
            if key:
                os.environ.setdefault(key, value)


_load_dotenv(project_root / ".env")
from config.config import DB_PATH


def _resolve_target_db_path(path, root: Path) -> str:
    """Resolve target DB path for restore; use host path when config has container path."""
    p = Path(path)
    if p.is_file():
        return str(p)
    if p.is_absolute() and not p.parent.exists():
        for candidate in (root / "attendance.db", root / "data" / "attendance.db"):
            candidate.parent.mkdir(parents=True, exist_ok=True)
            return str(candidate)
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def restore_backup(backup_file: str, target_db: str, create_backup: bool = True) -> bool:
    """
    Restore database from backup
    
    Args:
        backup_file: Path to backup file
        target_db: Path to target database file
        create_backup: Whether to create backup of current DB before restore
    
    Returns:
        True if restore successful, False otherwise
    """
    backup_path = Path(backup_file)
    target_path = Path(target_db)
    
    # Check backup file exists
    if not backup_path.exists():
        print(f"❌ Backup file not found: {backup_file}", file=sys.stderr)
        return False
    
    # Create backup of current database if it exists
    if target_path.exists() and create_backup:
        backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup = target_path.parent / f"{target_path.stem}_before_restore_{backup_timestamp}{target_path.suffix}"
        print(f"📦 Creating backup of current database: {current_backup}")
        try:
            shutil.copy2(target_path, current_backup)
            print(f"✅ Current database backed up to: {current_backup}")
        except Exception as e:
            print(f"⚠️  Warning: Could not backup current database: {e}")
            response = input("Continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                return False
    
    try:
        # Handle compressed backups
        if backup_file.endswith('.gz'):
            print(f"📦 Decompressing backup...")
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                tmp_path = tmp.name
                with gzip.open(backup_file, 'rb') as f_in:
                    shutil.copyfileobj(f_in, tmp)
            
            try:
                # Verify backup integrity
                print("🔍 Verifying backup integrity...")
                conn = sqlite3.connect(tmp_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                conn.close()
                
                if table_count == 0:
                    print("❌ Backup appears to be empty or corrupted", file=sys.stderr)
                    os.unlink(tmp_path)
                    return False
                
                print(f"✅ Backup verified: {table_count} tables found")
                
                # Restore using SQLite backup API
                print(f"📥 Restoring database...")
                backup_conn = sqlite3.connect(tmp_path)
                target_conn = sqlite3.connect(str(target_path))
                
                backup_conn.backup(target_conn)
                
                backup_conn.close()
                target_conn.close()
                
                # Clean up temp file
                os.unlink(tmp_path)
                
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        else:
            # Verify backup integrity
            print("🔍 Verifying backup integrity...")
            conn = sqlite3.connect(backup_file)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            conn.close()
            
            if table_count == 0:
                print("❌ Backup appears to be empty or corrupted", file=sys.stderr)
                return False
            
            print(f"✅ Backup verified: {table_count} tables found")
            
            # Restore using SQLite backup API
            print(f"📥 Restoring database...")
            backup_conn = sqlite3.connect(backup_file)
            target_conn = sqlite3.connect(str(target_path))
            
            backup_conn.backup(target_conn)
            
            backup_conn.close()
            target_conn.close()
        
        # Verify restored database
        print("🔍 Verifying restored database...")
        conn = sqlite3.connect(str(target_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        restored_table_count = cursor.fetchone()[0]
        conn.close()
        
        if restored_table_count == table_count:
            print(f"✅ Database restored successfully: {restored_table_count} tables")
            return True
        else:
            print(f"⚠️  Warning: Table count mismatch. Expected {table_count}, got {restored_table_count}")
            return False
            
    except Exception as e:
        print(f"❌ Error restoring database: {e}", file=sys.stderr)
        return False


def list_backups(backup_dir: str):
    """List available backups for restore"""
    from tools.backup_db import list_backups as list_backups_func
    list_backups_func(backup_dir)


def main():
    parser = argparse.ArgumentParser(description="Database restore utility")
    parser.add_argument("backup_file", nargs="?", help="Path to backup file")
    parser.add_argument("--target-db", default=DB_PATH, help="Target database path")
    parser.add_argument("--backup-dir", default="backups", help="Backup directory (for --list)")
    parser.add_argument("--no-backup", action="store_true", help="Don't backup current DB before restore")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    if args.list:
        list_backups(args.backup_dir)
        return
    
    if not args.backup_file:
        print("❌ Error: backup_file is required (use --list to see available backups)", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    target_db = _resolve_target_db_path(args.target_db, project_root)
    if not args.force:
        print(f"⚠️  WARNING: This will replace the database at {target_db}")
        print(f"   with backup from {args.backup_file}")
        if not args.no_backup:
            print(f"   (Current database will be backed up first)")
        response = input("\nAre you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Restore cancelled.")
            return
    
    success = restore_backup(
        args.backup_file,
        target_db,
        create_backup=not args.no_backup
    )
    
    if success:
        print(f"\n✅ Restore completed successfully!")
        print(f"   Database: {target_db}")
    else:
        print(f"\n❌ Restore failed!", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

