# Linux-Vollinstallation

Installation & Einstieg · 1.0.0.1

1. Die Vollinstallation ist für Ubuntu 26.04 amd64 mit systemd, mdadm, Docker Engine und Compose geprüft. Rootless Docker und UID-Remapping werden vom Host-Adapter nicht unterstützt. Bestehende RAID- und Alarmkonfiguration vorher prüfen.

2. Quellpaket herunterladen oder Repository klonen. Im Projektverzeichnis sudo python3 tools/install.py ausführen. Eigene Telegram-/Discord-Identitäten und Tokens im Terminal eingeben; OpenAI und Healthchecks sind optional. Zugangsdaten niemals in Clone-URLs oder Chats einfügen.

3. Der Installer sichert und migriert eine kompatible Einrichtung. Ein vorhandenes Docker-Projekt wird nicht blind überschrieben. Host-Agenten bleiben außerhalb der Container. SSH-Zugang und RAID-Mitglieder werden nicht verändert. Danach /status und /automatik_status in beiden Bots prüfen.

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
