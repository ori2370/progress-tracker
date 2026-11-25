# Encrypted offsite backups

The home server uploads encrypted PostgreSQL backups to an Oracle VM
over Tailscale using a dedicated SSH key.

## Layout

Home server:

- Backups: ~/.local/share/progress-tracker/backups/
- Transfer key: ~/.config/progress-tracker/oracle-backup-key
- Upload script: deployment/home/upload-backups.sh

Oracle:

- Tailscale IP: 100.64.0.4
- Account: tracker-backup
- Destination: /srv/progress-tracker-backups/
- Account home: /var/lib/tracker-backup/

These addresses and paths describe this installation. Adapt them for a
different environment.

Only database-*.dump.age files are uploaded. The database decryption key,
application credentials, and uploaded media are not included.

## Prerequisites

Both machines need rsync and SSH. Oracle also needs /usr/bin/rrsync.
Verify Oracle's SSH host fingerprint before accepting it on the home server.

The home server must have working SSH access to Oracle over Tailscale.

## Restricted transfer account

Create the Oracle account using /bin/sh as its shell:

```bash
sudo useradd --system --user-group --create-home \
  --home-dir /var/lib/tracker-backup \
  --shell /bin/sh tracker-backup

sudo install -d -m 700 -o tracker-backup -g tracker-backup \
  /srv/progress-tracker-backups

sudo install -d -m 755 -o root -g root \
  /var/lib/tracker-backup/.ssh
```

Generate a dedicated automation key on the home server:

```bash
ssh-keygen -t ed25519 \
  -f ~/.config/progress-tracker/oracle-backup-key \
  -N '' -C "home-server-encrypted-backups"
```

Do not overwrite an existing key.

On Oracle, put the public key in the account's authorized_keys file,
prefixed with:

```text
restrict,from="100.64.0.1",command="/usr/bin/rrsync -wo -no-del /srv/progress-tracker-backups"
```

The prefix and complete public key must be on one line.

Set ownership and permissions:

```bash
sudo chown root:root /var/lib/tracker-backup/.ssh/authorized_keys
sudo chmod 644 /var/lib/tracker-backup/.ssh/authorized_keys
```

This root-owned file contains a public key and must be readable by the
backup account. The account cannot edit the authorization restrictions.

The key permits rsync uploads within the destination directory, without
interactive shell access, forwarding, or rsync deletion options.
It does not prevent overwriting an existing backup with the same name.
Backup filenames contain timestamps and random suffixes.

## Upload schedule

Install these templates on the home server under /etc/systemd/system/,
replacing DEPLOY_USER with the deployment username:

- home/systemd/progress-tracker-backup-upload.service
- home/systemd/progress-tracker-backup-upload.timer

The Telegram notification script must include the backup-upload service
in its allowed services.

After validating the units and running daemon-reload, test manually:

```bash
sudo systemctl start progress-tracker-backup-upload.service
sudo journalctl -u progress-tracker-backup-upload.service -n 30 --no-pager
```

After a successful transfer:

```bash
sudo systemctl enable --now progress-tracker-backup-upload.timer
```

Transfers run five minutes after startup, then one hour after each run
finishes. Failed transfers trigger Telegram notification and retry at the
next scheduled run. There is no automatic remote deletion.

## Oracle retention

Install the service and timer from oracle/systemd/ on Oracle.

The retention service removes matching encrypted backups at least
30 days old. It uses the file modification time preserved by rsync.

Preview eligible files before enabling retention:

```bash
sudo find /srv/progress-tracker-backups \
  -maxdepth 1 -type f -name 'database-*.dump.age' \
  -mtime +29 -print
```

After validating the units and running daemon-reload:

```bash
sudo systemctl start progress-tracker-backup-retention.service
sudo systemctl enable --now progress-tracker-backup-retention.timer
```

Retention runs at 04:00 Asia/Jerusalem. Its failures are logged on Oracle;
Telegram failure hooks are not configured for this retention service.

Retention runs independently of uploads. If uploads stop for over 30 days,
all retained backups can eventually expire.

## Verification and recovery

Compare SHA-256 hashes on both machines after the first transfer.

Keep the age decryption key securely outside Oracle. This installation
keeps copies on the home server and the administrator's PC.

Retrieve a chosen encrypted file using the Oracle administrator account,
then use deployment/restore-test.sh with the decryption key to restore it
into a separate test database. The restricted upload key cannot download
files.

A matching hash proves transfer integrity. A successful restore test
provides stronger evidence that a backup is usable.

Local retention is 14 days; Oracle retention is 30 days. Offsite copies
share the age key used by the local backup process.