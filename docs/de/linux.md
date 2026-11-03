# Linux-Vollinstallation

Installation & Einstieg · 1.5.0.0

1. Die Vollinstallation ist für Ubuntu 26.04 amd64 mit systemd, mdadm, Docker Engine und Compose geprüft. Rootless Docker und UID-Remapping werden vom Host-Adapter nicht unterstützt. Bestehende RAID- und Alarmkonfiguration vorher prüfen.

2. Erstinstallation mit dem Helfer auf main: docker compose up -d. Die Anwendung wird dabei immer aus dem neuesten veröffentlichten stabilen GitHub-Release geladen, ohne Vorabversionen oder Rückfall auf einen alten lokalen Stand. Version und Commit stehen in .installation/version.json. Der privilegierte Setup-Container erkennt Adressen und Zertifikate, übernimmt ein gültiges vorhandenes IP-Zertifikat oder stellt auf einem freien Server eines aus. Die HTTPS-Adresse steht nach Abschluss in .installation/WEBADRESSE.txt und im Setup-Protokoll. Docker -d blendet spätere Ausgaben aus. Passwort und Dienstzugänge ausschließlich im Browser einrichten. Ein erneuter Start derselben Installation ist kein Update; andere Installationen werden nicht überschrieben. Unterstützt: Ubuntu 24.04/26.04 amd64 mit systemd und Docker. Browser und SSH verwenden denselben Internetzugang. Details im Erstinstallations-Leitfaden.

3. Repository klonen und im Projektverzeichnis docker compose up -d ausführen. Die Webadressen stehen unter .installation. Dort Benutzername und Passwort setzen, ohne Einrichtungstoken. Bot-IDs und API-Keys erst später auf der Seite eingeben, niemals im Chat.

4. Der Erstinstaller übernimmt keine fremden Projekte und aktualisiert bestehende Installationen nicht automatisch. Die Webcontainer bleiben unprivilegiert; feste Host-Agenten laufen außerhalb. SSH und RAID-Mitglieder bleiben erhalten. Bots erst nach ihrer Konfiguration prüfen.

```text
docker compose up -d
```

```text
docker compose up -d
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Vollinstallation per Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/main/FIRST_INSTALL.md)
