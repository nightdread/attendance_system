#!/usr/bin/env python3
"""
Database backup script for attendance system
Supports local backups and optional S3 upload
"""
import os
import sys
import sqlite3
import shutil
import gzip
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import json

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


def _resolve_db_path(path, root: Path) -> str:
    """Resolve database path; if not found, try common host paths (e.g. when .env has container path)."""
    p = Path(path)
    if p.is_file():
        return str(p)
    for candidate in (root / "attendance.db", root / "data" / "attendance.db"):
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(
        f"Database file not found. Tried: {p}, {root / 'attendance.db'}, {root / 'data' / 'attendance.db'}. "
        "Create the database or set DB_PATH in .env to the correct path (e.g. ./attendance.db)."
    )


def create_backup(db_path: str, backup_dir: str, compress: bool = True, keep_days: int = 30) -> str:
    """
    Create a backup of the SQLite database
    
    Args:
        db_path: Path to the database file
        backup_dir: Directory to store backups
        compress: Whether to compress the backup
        keep_days: Number of days to keep backups
    
    Returns:
        Path to the created backup file
    """
    # Ensure backup directory exists
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"attendance_backup_{timestamp}.db"
    if compress:
        backup_filename += ".gz"
    
    backup_file = backup_path / backup_filename
    
    # Create backup using SQLite backup API (more reliable than file copy)
    try:
        source_conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(str(backup_file).replace('.gz', ''))
        
        # Use SQLite backup API
        source_conn.backup(backup_conn)
        
        backup_conn.close()
        source_conn.close()
        
        # Compress if requested
        if compress:
            with open(str(backup_file).replace('.gz', ''), 'rb') as f_in:
                with gzip.open(str(backup_file), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            # Remove uncompressed file
            os.remove(str(backup_file).replace('.gz', ''))
        
        print(f"✅ Backup created: {backup_file}")
        
        # Clean up old backups
        cleanup_old_backups(backup_path, keep_days, compress)
        
        return str(backup_file)
        
    except Exception as e:
        print(f"❌ Error creating backup: {e}", file=sys.stderr)
        # Clean up partial backup if exists
        if backup_file.exists():
            backup_file.unlink()
        raise


def cleanup_old_backups(backup_dir: Path, keep_days: int, compressed: bool = True):
    """
    Remove backups older than keep_days
    
    Args:
        backup_dir: Directory containing backups
        keep_days: Number of days to keep backups
    """
    cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
    removed_count = 0
    
    pattern = "attendance_backup_*.db"
    if compressed:
        pattern += ".gz"
    
    for backup_file in backup_dir.glob(pattern):
        try:
            # Extract timestamp from filename
            # Format: attendance_backup_YYYYMMDD_HHMMSS.db[.gz]
            filename = backup_file.stem if compressed else backup_file.name
            timestamp_str = filename.replace("attendance_backup_", "").replace(".db", "")
            backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            
            if backup_date < cutoff_date:
                backup_file.unlink()
                removed_count += 1
                print(f"🗑️  Removed old backup: {backup_file.name}")
        except Exception as e:
            print(f"⚠️  Warning: Could not process {backup_file.name}: {e}")
    
    if removed_count > 0:
        print(f"✅ Cleaned up {removed_count} old backup(s)")


def upload_to_s3(backup_file: str, s3_bucket: str, s3_key: str = None):
    """
    Upload backup to S3 (optional)
    
    Args:
        backup_file: Path to backup file
        s3_bucket: S3 bucket name
        s3_key: S3 key (path) - if None, uses filename
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        s3_client = boto3.client('s3')
        
        if s3_key is None:
            s3_key = Path(backup_file).name
        
        s3_client.upload_file(backup_file, s3_bucket, s3_key)
        print(f"✅ Uploaded to S3: s3://{s3_bucket}/{s3_key}")
        
    except ImportError:
        print("⚠️  boto3 not installed. Skipping S3 upload.")
    except ClientError as e:
        print(f"❌ Error uploading to S3: {e}", file=sys.stderr)
        raise


def verify_backup(backup_file: str) -> bool:
    """
    Verify backup integrity by checking if it can be opened
    
    Args:
        backup_file: Path to backup file
    
    Returns:
        True if backup is valid, False otherwise
    """
    try:
        # Handle compressed backups
        if backup_file.endswith('.gz'):
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                with gzip.open(backup_file, 'rb') as f_in:
                    shutil.copyfileobj(f_in, tmp)
                tmp_path = tmp.name
            
            try:
                conn = sqlite3.connect(tmp_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                conn.close()
                
                os.unlink(tmp_path)
                return table_count > 0
            except:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return False
        else:
            conn = sqlite3.connect(backup_file)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            conn.close()
            return table_count > 0
            
    except Exception as e:
        print(f"❌ Backup verification failed: {e}", file=sys.stderr)
        return False


def list_backups(backup_dir: str):
    """
    List all available backups
    
    Args:
        backup_dir: Directory containing backups
    """
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        print(f"❌ Backup directory does not exist: {backup_dir}")
        return
    
    backups = []
    for backup_file in sorted(backup_path.glob("attendance_backup_*.db*"), reverse=True):
        try:
            stat = backup_file.stat()
            size_mb = stat.st_size / (1024 * 1024)
            
            # Extract timestamp
            filename = backup_file.stem if backup_file.suffix == '.gz' else backup_file.name
            timestamp_str = filename.replace("attendance_backup_", "").replace(".db", "")
            backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            
            backups.append({
                'file': backup_file.name,
                'date': backup_date,
                'size_mb': size_mb,
                'compressed': backup_file.suffix == '.gz'
            })
        except Exception as e:
            print(f"⚠️  Could not process {backup_file.name}: {e}")
    
    if not backups:
        print("No backups found.")
        return
    
    print(f"\n📦 Found {len(backups)} backup(s):\n")
    print(f"{'Date':<20} {'Size (MB)':<12} {'Compressed':<12} {'Filename'}")
    print("-" * 70)
    for backup in backups:
        compressed_str = "Yes" if backup['compressed'] else "No"
        print(f"{backup['date'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
              f"{backup['size_mb']:.2f} MB{'':<6} {compressed_str:<12} {backup['file']}")


def main():
    parser = argparse.ArgumentParser(description="Database backup utility")
    parser.add_argument("--db-path", default=DB_PATH, help="Path to database file")
    parser.add_argument("--backup-dir", default="backups", help="Backup directory")
    parser.add_argument("--no-compress", action="store_true", help="Don't compress backup")
    parser.add_argument("--keep-days", type=int, default=30, help="Days to keep backups")
    parser.add_argument("--verify", action="store_true", help="Verify backup after creation")
    parser.add_argument("--s3-bucket", help="S3 bucket for backup upload")
    parser.add_argument("--s3-key", help="S3 key (path) for backup")
    parser.add_argument("--list", action="store_true", help="List all backups")
    
    args = parser.parse_args()
    
    if args.list:
        list_backups(args.backup_dir)
        return
    
    try:
        db_path = _resolve_db_path(args.db_path, project_root)
        backup_file = create_backup(
            db_path,
            args.backup_dir,
            compress=not args.no_compress,
            keep_days=args.keep_days
        )
        
        # Verify backup if requested
        if args.verify:
            if verify_backup(backup_file):
                print("✅ Backup verification passed")
            else:
                print("❌ Backup verification failed", file=sys.stderr)
                sys.exit(1)
        
        # Upload to S3 if requested
        if args.s3_bucket:
            upload_to_s3(backup_file, args.s3_bucket, args.s3_key)
        
        print(f"\n✅ Backup completed successfully: {backup_file}")
        
    except Exception as e:
        print(f"❌ Backup failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

