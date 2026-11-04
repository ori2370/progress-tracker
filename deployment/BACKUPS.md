# Database backup and restore

These scripts back up the entire application database, including all
Tennis, Gym, and Posture tables as they are added.

Photo files are not included. Media backup must be added when uploads
are implemented.

## Requirements

Run from the repository root in a Linux environment with:

- Docker Compose and a running PostgreSQL `db` service
- age installed
- A public recipient file for backups
- The corresponding private key for restores

Keep private keys and backup files outside the repository.
Keep a separate secure copy of the private key: losing it makes
the encrypted backups unrecoverable.

## Create a backup

For the local runtime environment:

```bash
bash deployment/backup.sh \
  compose.runtime.yml \
  "$HOME/.config/progress-tracker/backup-recipient.txt" \
  "$HOME/.local/share/progress-tracker/backups"
```

The script streams a compressed PostgreSQL custom-format dump directly
into age encryption. It publishes the final file only after both
commands succeed.

No unencrypted dump file is written to disk.

## Test a restore

Replace BACKUP_FILENAME with the filename printed by the backup command:

```bash
bash deployment/restore-test.sh \
  compose.runtime.yml \
  "$HOME/.config/progress-tracker/backup-key.txt" \
  "$HOME/.local/share/progress-tracker/backups/BACKUP_FILENAME"
```

This creates a new database named `restore_test_...` and restores into it.
It does not overwrite the application database.

A successful restore confirms the archive can be decrypted and loaded.
Verify important records and relationships before considering recovery
fully tested.

The test database remains available for inspection.

## Remove a test database

Replace RESTORE_TEST_DATABASE with the exact name printed by the
restore script. Do not use the application database name.

```bash
docker compose -f compose.runtime.yml exec -T db \
  sh -c 'exec dropdb -U "$POSTGRES_USER" "$1"' \
  sh RESTORE_TEST_DATABASE
```

## Current limitations

- Backups are manual; scheduling is not configured.
- Backups on the same computer do not protect against losing that computer.
- Off-host storage and retention are not configured.
- Database roles and server configuration are not backed up.
- These scripts encrypt backups, not the running database or photo storage.
- The restore script is a recovery test, not a production cutover procedure.