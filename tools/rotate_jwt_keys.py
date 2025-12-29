#!/usr/bin/env python3
"""
JWT Secret Key Rotation Script
Safely rotates JWT secret keys with support for zero-downtime rotation
"""
import os
import sys
import secrets
import argparse
from pathlib import Path
from datetime import datetime
import shutil

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def generate_secret_key(length: int = 64) -> str:
    """
    Generate a secure random secret key
    
    Args:
        length: Length of the key in bytes (will be base64 encoded)
    
    Returns:
        Base64-encoded secret key
    """
    return secrets.token_urlsafe(length)


def backup_env_file(env_file: Path) -> Path:
    """
    Create a backup of .env file before modification
    
    Args:
        env_file: Path to .env file
    
    Returns:
        Path to backup file
    """
    if not env_file.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = env_file.parent / f".env.backup_{timestamp}"
    shutil.copy2(env_file, backup_file)
    return backup_file


def read_env_file(env_file: Path) -> dict:
    """
    Read .env file and return as dictionary
    
    Args:
        env_file: Path to .env file
    
    Returns:
        Dictionary of key-value pairs
    """
    env_vars = {}
    if not env_file.exists():
        return env_vars
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars


def write_env_file(env_file: Path, env_vars: dict):
    """
    Write environment variables to .env file
    
    Args:
        env_file: Path to .env file
        env_vars: Dictionary of key-value pairs
    """
    with open(env_file, 'w', encoding='utf-8') as f:
        for key, value in sorted(env_vars.items()):
            # Escape special characters in value
            if ' ' in value or '#' in value or '$' in value:
                value = f'"{value}"'
            f.write(f"{key}={value}\n")


def rotate_jwt_keys(env_file: Path, dry_run: bool = False) -> dict:
    """
    Rotate JWT secret keys
    
    Args:
        env_file: Path to .env file
        dry_run: If True, only show what would be changed
    
    Returns:
        Dictionary with old and new key information
    """
    env_vars = read_env_file(env_file)
    
    # Get current keys
    current_key = env_vars.get('JWT_SECRET_KEY')
    prev_key = env_vars.get('JWT_SECRET_KEY_PREV')
    
    if not current_key:
        print("❌ Error: JWT_SECRET_KEY not found in .env file", file=sys.stderr)
        sys.exit(1)
    
    # Generate new key
    new_key = generate_secret_key(64)
    
    result = {
        'old_current': current_key,
        'old_prev': prev_key,
        'new_current': new_key,
        'new_prev': current_key  # Current becomes previous
    }
    
    if dry_run:
        print("🔍 DRY RUN - No changes will be made\n")
        print("Current JWT_SECRET_KEY:", current_key[:20] + "..." if len(current_key) > 20 else current_key)
        if prev_key:
            print("Current JWT_SECRET_KEY_PREV:", prev_key[:20] + "..." if len(prev_key) > 20 else prev_key)
        print("\nAfter rotation:")
        print("New JWT_SECRET_KEY:", new_key[:20] + "...")
        print("New JWT_SECRET_KEY_PREV:", current_key[:20] + "..." if len(current_key) > 20 else current_key)
        return result
    
    # Backup .env file
    backup_file = backup_env_file(env_file)
    if backup_file:
        print(f"✅ Backed up .env to: {backup_file}")
    
    # Update keys
    env_vars['JWT_SECRET_KEY'] = new_key
    env_vars['JWT_SECRET_KEY_PREV'] = current_key  # Current becomes previous
    
    # Write updated .env file
    write_env_file(env_file, env_vars)
    
    print(f"✅ JWT keys rotated successfully!")
    print(f"   New JWT_SECRET_KEY: {new_key[:20]}...")
    print(f"   New JWT_SECRET_KEY_PREV: {current_key[:20]}...")
    
    return result


def verify_rotation(env_file: Path) -> bool:
    """
    Verify that JWT key rotation was successful
    
    Args:
        env_file: Path to .env file
    
    Returns:
        True if rotation looks correct
    """
    env_vars = read_env_file(env_file)
    
    current_key = env_vars.get('JWT_SECRET_KEY')
    prev_key = env_vars.get('JWT_SECRET_KEY_PREV')
    
    if not current_key:
        print("❌ JWT_SECRET_KEY not found", file=sys.stderr)
        return False
    
    if not prev_key:
        print("⚠️  Warning: JWT_SECRET_KEY_PREV not set (first rotation?)")
        return True
    
    # Check that keys are different
    if current_key == prev_key:
        print("⚠️  Warning: JWT_SECRET_KEY and JWT_SECRET_KEY_PREV are the same")
        return False
    
    # Check key format (should be base64-like)
    if len(current_key) < 32:
        print("⚠️  Warning: JWT_SECRET_KEY seems too short")
        return False
    
    print("✅ Rotation verification passed")
    return True


def show_rotation_status(env_file: Path):
    """
    Show current JWT key rotation status
    
    Args:
        env_file: Path to .env file
    """
    env_vars = read_env_file(env_file)
    
    current_key = env_vars.get('JWT_SECRET_KEY')
    prev_key = env_vars.get('JWT_SECRET_KEY_PREV')
    
    print("📋 Current JWT Key Status:\n")
    
    if current_key:
        print(f"JWT_SECRET_KEY: {current_key[:30]}... (length: {len(current_key)})")
    else:
        print("JWT_SECRET_KEY: ❌ Not set")
    
    if prev_key:
        print(f"JWT_SECRET_KEY_PREV: {prev_key[:30]}... (length: {len(prev_key)})")
        print("\n✅ Key rotation is configured (both keys present)")
        print("   - New tokens will be signed with JWT_SECRET_KEY")
        print("   - Old tokens can still be verified with JWT_SECRET_KEY_PREV")
    else:
        print("JWT_SECRET_KEY_PREV: ⚠️  Not set")
        print("\n⚠️  Key rotation not configured (only current key present)")
        print("   - This is normal for first-time setup")
        print("   - After rotation, both keys will be present")


def main():
    parser = argparse.ArgumentParser(
        description="Rotate JWT secret keys for zero-downtime rotation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (see what would change)
  python3 tools/rotate_jwt_keys.py --dry-run

  # Rotate keys
  python3 tools/rotate_jwt_keys.py

  # Rotate with custom .env file
  python3 tools/rotate_jwt_keys.py --env-file /path/to/.env

  # Show current status
  python3 tools/rotate_jwt_keys.py --status

  # Verify rotation
  python3 tools/rotate_jwt_keys.py --verify

Notes:
  - The current JWT_SECRET_KEY becomes JWT_SECRET_KEY_PREV
  - A new JWT_SECRET_KEY is generated
  - Old tokens continue to work during transition period
  - After rotation, restart the application to apply changes
  - After all old tokens expire, JWT_SECRET_KEY_PREV can be removed
        """
    )
    
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file (default: .env)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current JWT key rotation status"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that rotation was successful"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    args = parser.parse_args()
    
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = project_root / env_file
    
    if args.status:
        show_rotation_status(env_file)
        return
    
    if args.verify:
        success = verify_rotation(env_file)
        sys.exit(0 if success else 1)
    
    # Confirm rotation
    if not args.dry_run and not args.force:
        print("⚠️  WARNING: This will rotate JWT secret keys")
        print("   - Current JWT_SECRET_KEY will become JWT_SECRET_KEY_PREV")
        print("   - A new JWT_SECRET_KEY will be generated")
        print("   - You will need to restart the application after rotation")
        print("   - Old tokens will continue to work during transition")
        response = input("\nAre you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Rotation cancelled.")
            return
    
    try:
        result = rotate_jwt_keys(env_file, dry_run=args.dry_run)
        
        if not args.dry_run:
            print("\n📋 Next Steps:")
            print("1. Review the changes in .env file")
            print("2. Restart the application to apply new keys")
            print("3. Monitor logs for any token verification issues")
            print("4. After all old tokens expire (typically 30 minutes),")
            print("   you can optionally remove JWT_SECRET_KEY_PREV")
            print("\n✅ Rotation completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during rotation: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

