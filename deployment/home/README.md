# Home server deployment

Runs Django and PostgreSQL using Docker Compose. Access is available through
localhost and the server's Headscale/Tailscale IPv4 address.

## Requirements

- Linux server with Docker Engine and Docker Compose 2.24.4 or newer.
- Docker access for the deployment user.
- Git, Python 3, and age.
- Server and phone connected to the same Headscale network.
- Repository cloned to ~/apps/progress-tracker.

The systemd templates assume the user's home directory is /home/USERNAME.

## Private configuration

Store credentials outside the repository:

    install -d -m 700 ~/.config/progress-tracker

For a new installation only, copy the example:

    cp deployment/home/home.env.example ~/.config/progress-tracker/home.env
    chmod 600 ~/.config/progress-tracker/home.env

Edit that private file before starting containers:

- Generate separate random values for DJANGO_SECRET_KEY and POSTGRES_PASSWORD.
- Set TAILNET_IP to the server's Headscale IPv4 address.
- Include that address in DJANGO_ALLOWED_HOSTS, without a scheme or port.
- Set APP_PORT to an available port; the default is 18743.
- Optionally provide YOUTUBE_API_KEY.

Generate each secret separately with:

    python3 -c 'import secrets; print(secrets.token_hex(32))'

For an existing installation, preserve its credentials and add only missing
settings. Do not overwrite the private environment file with the example.

The example image name is progress-tracker:home. Release-specific image tags
are recommended for subsequent updates.

## First deployment

Run from the repository root:

    docker build -t progress-tracker:home .
    bash deployment/home/compose.sh config --quiet
    bash deployment/home/compose.sh up -d --wait --wait-timeout 120 db
    bash deployment/home/compose.sh run --rm --no-deps web python manage.py migrate --noinput
    bash deployment/home/compose.sh run --rm --no-deps web python manage.py import_exercise_catalog data/free-exercise-db/exercises.json
    bash deployment/home/compose.sh run --rm --no-deps web python manage.py createsuperuser
    bash deployment/home/compose.sh up -d --wait --wait-timeout 120 web
    bash deployment/home/compose.sh ps

Check readiness using the configured port:

    curl --fail --show-error http://127.0.0.1:18743/health/ready/

On a connected phone, open:

    http://SERVER_HEADSCALE_IP:18743/gym/

The connection uses HTTP inside the encrypted Headscale/Tailscale tunnel.
HTTPS is not configured by this setup. Access also depends on Headscale ACLs;
binding to the tailnet address does not restrict access to one particular user.

For PC access without a Headscale client:

    ssh -N -L 8081:127.0.0.1:18743 home-server

Then open http://localhost:8081/gym/. The SSH alias must already be configured
on the PC.

## Storage

PostgreSQL uses the progress-tracker project's postgres_data named volume.
Its location follows Docker's storage configuration. Verify that Docker's
data directory is on the intended SSD before deployment.

Container recreation preserves this volume. Do not use down --volumes or
delete the database volume unless intentionally removing the data.

Container logs are limited to three 10 MB files per service.

## Encrypted backups

For a new backup setup only:

    age-keygen -o ~/.config/progress-tracker/backup-key.txt
    chmod 600 ~/.config/progress-tracker/backup-key.txt
    age-keygen -y ~/.config/progress-tracker/backup-key.txt > ~/.config/progress-tracker/backup-recipient.txt
    install -d -m 700 ~/.local/share/progress-tracker/backups

Keep a secure copy of the private key outside the server. Losing every copy
of the key makes the backups unrecoverable.

Create a backup from the repository root:

    (
        set -a
        source "$HOME/.config/progress-tracker/home.env"
        set +a
        bash deployment/backup.sh \
            "$PWD/deployment/compose.yml" \
            "$HOME/.config/progress-tracker/backup-recipient.txt" \
            "$HOME/.local/share/progress-tracker/backups"
    )

The environment file is trusted shell input for this command. Do not enable
shell tracing, which could expose credentials.

Backups cover the PostgreSQL database, including all activity categories.
They do not include uploaded files, private configuration, or encryption keys.

## Daily backup timer

Inspect the templates before installing. Replace DEPLOY_USER with the actual
server username in the service template, then install both units under
/etc/systemd/system/.

Validate the installed units:

    sudo systemd-analyze verify /etc/systemd/system/progress-tracker-backup.service /etc/systemd/system/progress-tracker-backup.timer
    sudo systemctl daemon-reload
    sudo systemctl start progress-tracker-backup.service
    sudo journalctl -u progress-tracker-backup.service -n 20 --no-pager

After a successful manual run:

    sudo systemctl enable --now progress-tracker-backup.timer
    systemctl list-timers --all progress-tracker-backup.timer

The timer runs at 03:00 Asia/Jerusalem and catches a missed run after downtime.
After a successful backup, files matching database-*.dump.age older than
14 days are deleted from the configured backup directory.

Scheduled backups remain on the server. Automatic off-server copying and
failure notifications are not configured.

## Restore testing

Use deployment/restore-test.sh with the Compose file, private key, and the
specific encrypted backup path. Load home.env as in the backup example.

The script restores into a separate database and prints its generated name.
Check restored records, then remove only that test database. It does not
replace the live application database.

See ../BACKUPS.md for further backup and restore instructions.

## Updating the application

1. Create a successful backup and note its exact filename.
2. Record the current Git commit and APP_IMAGE value.
3. Pull reviewed changes with git pull --ff-only.
4. Build a new image with a distinct tag, for example progress-tracker:COMMIT_SHA.
5. Change only APP_IMAGE in the private home.env file to the new tag.
6. Run migrations using the new image:
   bash deployment/home/compose.sh run --rm --no-deps web python manage.py migrate --noinput
7. Refresh the catalog if its snapshot changed.
8. Recreate the web service:
   bash deployment/home/compose.sh up -d --no-deps --wait --wait-timeout 120 web
9. Check readiness, login, saved records, and the feature that changed.

Preserve the database volume, credentials, and previous image during updates.

Updates may briefly interrupt access. Migrations must be compatible with
the running application, or an appropriate maintenance window is needed.

An older application image is safe to reuse only if it supports the current
database schema. Database restoration is a separate recovery operation and
may discard changes made after the backup.

## Operational checks

    bash deployment/home/compose.sh ps
    bash deployment/home/compose.sh logs --tail 50 web
    sudo journalctl -u progress-tracker-backup.service -n 30 --no-pager
    systemctl list-timers --all progress-tracker-backup.timer

Do not publish rendered Compose configuration: it contains resolved secrets.


## Automatic application updates

GitHub Actions publishes the home image after Django, container, backup,
and updater checks pass. The server checks GHCR every five minutes and
deploys the resolved image digest.

The updater creates an encrypted database backup before migrations,
refreshes the catalog, recreates only the web service, and checks readiness.
On success, it saves the deployed digest in the private home.env file.

The first GHCR package must be made public to allow anonymous server pulls.
The image contains application code and the catalog, not the live database
or private server configuration.

Install the update service and timer from systemd/, replacing DEPLOY_USER
with the server username. Test the service manually before enabling its timer.

Inspect updates:

```bash
sudo journalctl -u progress-tracker-update.service -n 60 --no-pager
systemctl list-timers --all progress-tracker-update.timer
```

Pause future checks:

```bash
sudo systemctl disable --now progress-tracker-update.timer
```

Stopping the timer does not interrupt a service run already in progress.

If deployment fails after migrations begin, the updater leaves this marker:

```text
~/.local/state/progress-tracker/update-blocked
```

Further attempts stop until the failure is investigated. Inspect service
logs, container health, and migration state before removing the marker.

The previous image reference is recorded in:

```text
~/.local/state/progress-tracker/previous-image
```

There is no automatic image or database rollback. An older image may be
incompatible with the migrated database.

Application updates do not run git pull. Changes to deployment scripts,
Compose configuration, or systemd units require a deliberate installation.

Automatic updates may briefly interrupt access. Old Docker images are not
automatically removed; monitor disk usage and preserve recovery images.

## Telegram failure notifications

Private credentials belong in:

    ~/.config/progress-tracker/notifications.env

Use notifications.env.example as the format reference. Keep the real file
outside Git with permissions 600.

Install progress-tracker-notify@.service after replacing DEPLOY_USER with
the server username. Reinstall the backup and update service templates to
apply their OnFailure hooks, then run systemctl daemon-reload.

Send a test notification:

```bash
sudo systemctl start progress-tracker-notify@test.service
sudo journalctl -u progress-tracker-notify@test.service -n 20 --no-pager
```

Failed backup or update jobs trigger an alert containing the hostname,
service name, UTC timestamp, and a command for inspecting local logs.
Application records, credentials, and log contents are not sent.

Repeated alerts for the same service are suppressed for one hour after
successful delivery. Test notifications bypass this cooldown.

Notifications require working internet access and Telegram availability.
A powered-off server cannot report its own outage. Failed notification
attempts are logged locally; persistent delivery retries and external
uptime monitoring are not configured.