# Weitergabe und Serverunterstützung

Der Quellstand enthält keine Zugangsdaten, persönliche IDs, Server-IP oder fertigen Passwörter. Gib ausschließlich diesen Quellstand weiter, niemals deine laufenden Container-Volumes, `/etc/kiagent-docker`, Auth-Dateien oder Backups.

## Portable Weboberfläche

Die portable Variante benötigt einen Docker-Daemon für **Linux-Container** und Docker Compose. Sie benutzt ein benanntes Volume, keine Ubuntu-Hostpfade, keinen Docker-Socket und keine systemd-Dienste. Der Web-Lockfile enthält Wheels für Linux amd64 und arm64; die automatische Funktionsprüfung läuft auf amd64.

- Linux: Docker Engine und Compose.
- Windows-PC: eine geeignete Linux-Container-Umgebung, beispielsweise Docker Desktop mit Linux-Backend, soweit vom Hersteller auf diesem System unterstützt.
- Windows Server: eine Linux-VM mit Docker Engine. Dieses Python-Linux-Image läuft nicht als nativer Windows-Container. Es installiert keine VM und schaltet keine Windows-Schutzmechanismen ab.

Auf dem jeweiligen Docker-Rechner im entpackten Projektverzeichnis:

```text
docker compose -f compose.portable.yaml up -d --build --wait
```

Danach auf **diesem Rechner** `http://127.0.0.1:8787/setup` öffnen und das eigene Passwort festlegen. Es gibt keinen Einrichtungscode und kein Standardpasswort. Die Anforderungen sind mindestens 8 Zeichen, ein Großbuchstabe, eine Zahl und ein Sonderzeichen; höchstens 256 Zeichen, keine Leerzeichen. Die Ersteinrichtung ist nach erfolgreichem Abschluss gesperrt. Passwortänderung erfolgt später über „Administrator-Passwort ändern“ und erfordert das bisherige Passwort. Sitzungen werden bei Änderung ungültig.

Der Port ist absichtlich nur auf Loopback veröffentlicht. Für einen entfernten Docker-Server ist ein administrativer Tunnel für die Ersteinrichtung oder ein HTTPS-Reverse-Proxy erforderlich. Beim öffentlichen HTTPS-Betrieb `CONFIG_SETUP_LOCAL_ONLY=0`, `CONFIG_SETUP_PROXY=1` und die eigene öffentliche `CONFIG_SETUP_ALLOWED_IP` setzen. Der Proxy muss `/setup` auf diese IP beschränken und `X-Kiagent-Setup-IP` selbst mit der tatsächlichen Client-IP überschreiben; niemals vom Besucher übernehmen. `CONFIG_ORIGIN` ist dann die genaue HTTPS-Adresse. Ein ungeschützt öffentliches „erster Besucher wird Administrator“ wird nicht unterstützt.

Die portable Variante speichert und validiert die eingegebenen Einstellungen. Sie startet **keine Chat-Bots und führt keine Host-Aktionen aus**. Dies wird in der Oberfläche ausdrücklich angezeigt. Die Konfiguration bleibt im Volume `portal-state`, einschließlich Passwort-Hash und lokalen Sicherungen. Das Volume enthält vertrauliche Daten und gehört nicht in ein weitergegebenes Paket.

## Vollständige Linux-Serversteuerung

Die bestehende Vollinstallation in `compose.yaml` enthält Telegram, Discord, Lebenszeichen, bestätigte Installationen aller APT-Pakete und RAID-Monitor-Reparaturen. Sie wurde für Ubuntu 26.04 amd64 mit systemd/mdadm geprüft. Die Host-Agenten bleiben außerhalb der Container; sie authentifizieren Verbindungen anhand fester Host-UIDs. Rootless-/UID-Remapping wird nicht unterstützt. Auf einem anderen Linux-System ist vor Installation die Kompatibilität der Host-Adapter zu prüfen.

Diese Linux-Reparaturen dürfen auf Windows nicht als ausführbare Aktionen angeboten werden. Ein Windows-Host-Adapter ist noch nicht implementiert. Die portable Oberfläche bildet die Grundlage für solche weiteren Adapter; sie ersetzt diese nicht.

## Passwort-Reset einer verwalteten HTTPS-Installation

```bash
sudo --preserve-env=SSH_CONNECTION python3 tools/install_password_setup.py
```

Der Installer übernimmt die Administrator-IP aus deiner aktuellen SSH-Verbindung oder fragt sie im Terminal ab. Er sichert den Stand, aktualisiert ausschließlich die Oberfläche, sperrt alte Web-Sitzungen und setzt den Zugang auf die IP-beschränkte Passwort-Ersteinrichtung zurück. Bot-Tokens, Reparaturhistorie und Sperrzeiten werden nicht geändert. Danach `/setup` von diesem Zugang aus öffnen. Bei einem Wechsel der öffentlichen Administrator-IP den Reset erneut mit `--admin-ip DEINE-NEUE-IP` vorbereiten.

Ein vergessener Zugang ist absichtlich kein öffentlich aufrufbarer Reset ohne Eigentumsprüfung. Der Serveradministrator aktiviert den Reset über seinen bestehenden Serverzugang; es wird kein Code erzeugt.
