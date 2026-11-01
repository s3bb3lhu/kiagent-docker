# Linux-Vollinstallation

Installation & Einstieg · 1.2.0.1

1. Die Vollinstallation ist für Ubuntu 26.04 amd64 mit systemd, mdadm, Docker Engine und Compose geprüft. Rootless Docker und UID-Remapping werden vom Host-Adapter nicht unterstützt. Bestehende RAID- und Alarmkonfiguration vorher prüfen.

2. Neu: Die vollständige Einrichtung und der Start sind interaktiv mit docker compose -f compose.install.yaml run --rm --build installer möglich. Der ausdrücklich privilegierte Einmal-Installer richtet die festen Host-Agenten ein und wird danach entfernt. Frische Ubuntu-24.04-/26.04-amd64-Hosts werden geprüft; vorhandene Installationen werden nicht überschrieben. Nach dem Web-Start dort das Passwort festlegen und unter /settings/setup alle Dienst-IDs und Tokens eingeben. Die Webadresse wird nach automatischer IP-Erkennung ausgegeben; im Terminal gibt es keine Eingabeabfragen. Browser und SSH müssen denselben Internetzugang verwenden; Bots und Aktionen bleiben bis zur erfolgreichen Prüfung gesperrt. Zugang standardmäßig https://SERVER-IP:8443; TCP 80 und der gewählte Web-Port müssen erreichbar sein. Details im verlinkten Vollinstallations-Leitfaden.

3. Quellpaket herunterladen oder Repository klonen. Im Projektverzeichnis sudo python3 tools/install.py ausführen. Eigene Telegram-/Discord-Identitäten und Tokens im Terminal eingeben; OpenAI und Healthchecks sind optional. Zugangsdaten niemals in Clone-URLs oder Chats einfügen.

4. Der Installer sichert und migriert eine kompatible Einrichtung. Ein vorhandenes Docker-Projekt wird nicht blind überschrieben. Host-Agenten bleiben außerhalb der Container. SSH-Zugang und RAID-Mitglieder werden nicht verändert. Danach /status und /automatik_status in beiden Bots prüfen.

```text
docker compose -f compose.install.yaml run --rm --build installer
```

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Vollinstallation per Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/v1.2.0.1/FULL_COMPOSE.md)
