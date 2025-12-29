#!/bin/bash
# Setup cron job for automatic database backups
# Usage: ./setup_backup_cron.sh [backup_dir] [keep_days]

BACKUP_DIR="${1:-backups}"
KEEP_DAYS="${2:-30}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/backup_db.py"

# Create backup directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/$BACKUP_DIR"

# Create cron job (runs daily at 2 AM)
CRON_JOB="0 2 * * * cd $PROJECT_ROOT && python3 $BACKUP_SCRIPT --backup-dir $BACKUP_DIR --keep-days $KEEP_DAYS --verify >> $PROJECT_ROOT/logs/backup.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$BACKUP_SCRIPT"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job installed successfully!"
echo "   Schedule: Daily at 2:00 AM"
echo "   Backup directory: $PROJECT_ROOT/$BACKUP_DIR"
echo "   Keep days: $KEEP_DAYS"
echo ""
echo "To view cron jobs: crontab -l"
echo "To remove cron job: crontab -e (then delete the line)"

