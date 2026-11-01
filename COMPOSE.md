# Docker Compose — 1.4.0.0

Für **Telegram, Discord und echte Serversteuerung mit `docker compose up -d`** zuerst [FIRST_INSTALL.md](FIRST_INSTALL.md) verwenden. Die folgenden Portal-Befehle sind die ausdrücklich eingeschränkte Alternative.

## Einfacher Portalstart / Portable portal

```bash
git clone --branch v1.4.0.0 --depth 1 https://github.com/s3bb3lhu/kiagent-docker.git
cd kiagent-docker
docker compose -f compose.quickstart.yaml up -d --build --wait
```

Auf dem Docker-Rechner / on the Docker machine: **http://127.0.0.1:8787/setup**.
Das eigene Passwort im Browser festlegen und danach die eigenen Dienstschlüssel unter Einstellungen eintragen. Keine Standardzugangsdaten, keine mitgelieferten Tokens. Das benannte Volume enthält vertrauliche Daten und bleibt bei normalen Container-Neustarts erhalten.

Set your password in the browser, then enter your service credentials under Settings. There is no default password and no bundled token. The named volume holds private data and persists across normal container restarts.

**Diese portable Variante verwaltet nur Konfiguration. Sie startet keine Bots und führt keine Host-Aktionen aus.** The portable variant manages configuration only: it does not run bots or host actions. Windows requires Linux containers; Windows Server requires a suitable Linux VM. For remote access use a regular SSH tunnel or configure a trusted HTTPS proxy as described in [DISTRIBUTION.md](DISTRIBUTION.md). Do not expose the plain-HTTP setup port publicly.

```bash
docker compose -f compose.quickstart.yaml ps
docker compose -f compose.quickstart.yaml down
```

`down` ohne `--volumes` erhält die Konfiguration. `down` without `--volumes` preserves configuration. Do not run a second stack against an already occupied port 8787.

**Die Dateiangabe `-f compose.quickstart.yaml` bei jedem Portal-Befehl beibehalten.** Ein einfaches `docker compose down` betrifft auf dem aktuellen main-Zweig den Erstinstallations-Container, nicht das Portal oder den separat verwalteten Host-Stack.

**Keep `-f compose.quickstart.yaml` on every portal command.** On current main, plain `docker compose down` selects the first-install container, not the portal or the separately managed host runtime.

## Vollständige Linux-Steuerung / Full Linux control

Die vollständige Datei ist [compose.runtime.yaml](compose.runtime.yaml). Sie enthält Telegram, Discord, Host-Lebenszeichen und Weboberfläche. Sie benötigt die von den Installationswerkzeugen angelegten Benutzer, Secret-Dateien und festen Host-Sockets. Die Root-Agenten laufen als systemd-Dienste außerhalb der Container; ein Docker-Socket oder privilegierter Container ist nicht erforderlich.

The full [compose.runtime.yaml](compose.runtime.yaml) includes Telegram, Discord, host heartbeat and web UI. It requires users, secret files and fixed host sockets created by the installer. Root agents run as systemd services outside containers; a Docker socket or privileged container is not needed.

Auf einem kompatiblen, geprüften Ubuntu-Host aus dem entpackten Release-Verzeichnis / on a compatible, reviewed Ubuntu host from the release directory:

```bash
sudo python3 tools/install.py
```

Danach / afterwards:

```bash
sudo docker compose --env-file /etc/kiagent-docker/deployment.env \
  -f /opt/kiagent-docker/project/compose.yaml ps
```

Use [README.md](README.md) for prerequisites, existing RAID configuration and the optional HTTPS installer. Do not use the fresh installer to overwrite an existing managed deployment. Native Windows host actions are not included.

## Anleitungen / Guides

[Deutsch](docs/de/README.md) · [English](docs/en/README.md) · [Español](docs/es/README.md) · [Français](docs/fr/README.md)

The images are built locally from the release source. No unverified registry image or credential-bearing download URL is required.
