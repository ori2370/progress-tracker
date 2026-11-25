# Home monitoring and media notifications

## Components

- Uptime Kuma on the home server checks application availability.
- A lightweight Python monitor on Oracle checks home-server connectivity
  and Progress Tracker readiness independently.
- qBittorrent reports torrent additions and download completions.
- Sonarr and Radarr report successful imports.
- Tracker systemd jobs have separate Telegram failure notifications.

Credentials and monitoring databases are not stored in Git.

## Uptime Kuma

Install compose.yml in ~/apps/uptime-kuma/ on the home server.

```bash
docker compose config --quiet
docker compose up -d
```

The dashboard is available at:

    http://100.64.0.1:18744

Create an administrator account and choose SQLite. Its database and
notification credentials persist in the uptime_data named volume.

Port 18744 is bound to localhost and the home server's Tailscale address.
Change the address before using this configuration on another server.

Configure a Telegram notification through the dashboard. Keep its token
private and enable it for each monitor.

### Application checks

| Name | URL |
|---|---|
| Jellyfin | http://192.168.31.79:8096/health |
| Sonarr | http://192.168.31.79:8989/ping |
| Radarr | http://192.168.31.79:7878/ping |
| qBittorrent | http://192.168.31.79:8585/ |
| Progress Tracker | http://100.64.0.1:18743/health/ready/ |
| Headscale | http://151.145.92.0:8080/health |

These addresses describe this installation; adapt them as needed.

Use a 60-second interval, two retries, a 30-second retry interval, and
disable repeated notifications. Verify both down and recovery notifications.

The qBittorrent check verifies WebUI availability, not download progress.
Tracker readiness includes database connectivity.

A local monitor cannot report loss of power or internet on its own host.
The Headscale endpoint currently uses public HTTP; HTTPS remains a follow-up.

## External monitor on Oracle

Source files:

- ../oracle/home-monitor.py
- ../oracle/systemd/home-monitor.service
- ../oracle/systemd/home-monitor.timer

Install the Python script as:

    /home/ubuntu/apps/home-monitor/monitor.py

The supplied units use the ubuntu account. Adapt their paths and user
for another installation.

Store Telegram credentials in:

    ~/.config/home-monitor/notifications.env

Format:

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Protect the directory with mode 700 and the file with mode 600.

The script checks TCP port 22 on 100.64.0.1 and the tracker's readiness
endpoint. Oracle must already be connected to the same Headscale network.

Test manually:

```bash
python3 ~/apps/home-monitor/monitor.py --test
python3 ~/apps/home-monitor/monitor.py
```

Install both units under /etc/systemd/system/, validate them, and reload:

```bash
sudo systemd-analyze verify /etc/systemd/system/home-monitor.service /etc/systemd/system/home-monitor.timer
sudo systemctl daemon-reload
sudo systemctl start home-monitor.service
sudo journalctl -u home-monitor.service -n 20 --no-pager
sudo systemctl enable --now home-monitor.timer
```

Checks run every minute after the previous run finishes. Three failed
checks trigger an alert. Recovery triggers one message. Failed deliveries
are retried on subsequent checks.

State is stored in ~/.local/state/home-monitor/. Routine healthy checks
do not send notifications.

A failed SSH-port check means the SSH service is unreachable from Oracle.
It does not establish whether the cause is power, SSH, internet, or Tailscale.

The monitor cannot report its own Oracle host going offline.

## qBittorrent events

This installation uses qBittorrent 5.1.4.

Install torrent_notify.py in the host directory:

    ~/media-server/config/qbittorrent/notifications/

That directory appears inside the container as:

    /config/notifications/

Place a separate private telegram.env beside the script using the Telegram
environment-file format above. In this installation, the container user
has UID/GID 1000:1000. Use directory mode 750, script mode 640, and
credential-file mode 600, with ownership allowing that user to read them.

Test from the container:

```bash
docker exec --user 1000:1000 qbittorrent \
  /usr/bin/python3 /config/notifications/torrent_notify.py \
  test "Notification setup"
```

Configure Tools → Options → Downloads → Run external program.

On torrent added:

```text
/usr/bin/python3 /config/notifications/torrent_notify.py added -- "%N"
```

On torrent finished:

```text
/usr/bin/python3 /config/notifications/torrent_notify.py finished -- "%N"
```

Preserve any existing hooks before changing them. No container restart
is required. Torrent names are sent to Telegram.

A torrent-added event does not imply downloading started immediately.
A completed event does not imply Sonarr or Radarr finished importing.

Validate the hooks with a future legitimate torrent addition/completion.
A successful manual script test alone does not verify the hooks.

## Sonarr and Radarr imports

In each application's Settings → Connect, add Telegram:

- Enable On Import / On Download.
- Leave On Grab disabled to avoid duplicating torrent-added messages.
- Test and save the connection.

Credentials remain in each application's persistent configuration.

## Maintenance

Existing Homarr unhealthy status is not included in these monitors and
requires separate investigation.

Back up Uptime Kuma's configuration database using a supported consistent
backup procedure. Its volume contains credentials and is not covered by
the tracker's PostgreSQL backups.

The external monitor, media notification script, and systemd units require
deliberate installation when changed in Git. Tracker image updates do not
install these files.