#!/bin/bash
set -euo pipefail
umask 077

BACKUP_DIRECTORY="$HOME/.local/share/progress-tracker/backups"
KEY_FILE="$HOME/.config/progress-tracker/oracle-backup-key"
STATE_DIRECTORY="$HOME/.local/state/progress-tracker"

if [[ ! -d "$BACKUP_DIRECTORY" ]]; then
    echo "Backup directory is missing." >&2
    exit 1
fi

if [[ ! -s "$KEY_FILE" ]]; then
    echo "Backup transfer key is missing." >&2
    exit 1
fi

install -d -m 700 "$STATE_DIRECTORY"

exec 9>"$STATE_DIRECTORY/backup-upload.lock"
flock -n 9 || exit 0

shopt -s nullglob
backups=("$BACKUP_DIRECTORY"/database-*.dump.age)

if [[ "${#backups[@]}" -eq 0 ]]; then
    echo "No encrypted database backups were found." >&2
    exit 1
fi

echo "Uploading encrypted backups to Oracle..."

rsync -rtv \
    --timeout=120 \
    --include='database-*.dump.age' \
    --exclude='*' \
    -e "ssh -i $KEY_FILE -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10" \
    "$BACKUP_DIRECTORY/" \
    tracker-backup@100.64.0.4:.

echo "Encrypted backup upload completed successfully."