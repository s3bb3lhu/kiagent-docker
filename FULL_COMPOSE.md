# Vollinstallation per Docker Compose — 1.1.0.0

Diese Variante installiert und startet Telegram, Discord, Weboberfläche, Host-Lebenszeichen, begrenzte Serveraktionen und lokale Sicherungen. Die festen Root-Agenten werden vom einmaligen Installer als systemd-Dienste auf dem Linux-Host eingerichtet. Im laufenden Betrieb erhalten Bots und Weboberfläche weder einen privilegierten Container noch einen Docker-Socket.

## Voraussetzungen

- Dedizierter Ubuntu-24.04-/26.04-Server, amd64, mit systemd, Python >=3.10, Docker Engine und Compose. Kein rootless Docker und kein UID-Remapping; vorhandene Schutzoptionen werden nicht abgeschaltet.
- Öffentlich erreichbare IPv4-Adresse des Servers. Für das vertrauenswürdige IP-Zertifikat muss **TCP 80** von außen erreichbar bleiben. Der Webzugang nutzt standardmäßig **TCP 8443**, alternativ einen gewählten freien Port. Port 8787 bleibt intern.
- Eigener Telegram-Bot samt Benutzer-ID; Discord-Anwendung, Bot, Benutzer-, Server- und private Kanal-ID. Die Tokens werden verdeckt im eigenen Terminal abgefragt. OpenAI und Healthchecks sind optional. Niemand muss Zugangsdaten im Chat oder Repository veröffentlichen.
- Die IP-Adresse des Browsers für die erste Passwort-Einrichtung. Diese IP wird für `/setup` freigegeben; später schützt das selbst gewählte Passwort die Anmeldung.
- RAID-Funktionen benötigen tatsächlich vorhandenes mdadm/RAID und eingerichtete Alarmempfänger. Ohne RAID-Geräte das Feld leer lassen; die Automatik bleibt bei einer Neuinstallation ausgeschaltet. Es werden keine Laufwerke formatiert und kein RAID angelegt.

Windows Server benötigt eine entsprechende Linux-VM. Docker Desktop beziehungsweise ein nativer Windows-Container ist kein unterstützter Host für die vollständige Serversteuerung. Das reine Konfigurationsportal bleibt separat verfügbar.

## Installation und Start

Auf einem frischen, geeigneten Server:

```bash
git clone --branch v1.1.0.0 --depth 1 https://github.com/s3bb3lhu/kiagent-docker.git kiagent-docker-1.1.0.0
cd kiagent-docker-1.1.0.0
docker compose -f compose.install.yaml run --rm --build installer
```

Falls dein Benutzer Docker nicht direkt bedienen darf, denselben Compose-Befehl mit `sudo` ausführen. `run` ist absichtlich interaktiv: Der Installer fragt nach Server-IPv4, Administrator-IP und anschließend den eigenen Dienstzugängen. Die Zustimmung zu den Zertifikatsbedingungen erfolgt im eigenen Terminal. Nicht mit `up -d` starten; das Installationsprofil ist gegen einen versehentlichen automatischen Start geschützt.

**Dieser einmalige Installer hat Administratorrechte:** privilegierter Container, Host-PID-Namensraum und schreibbarer Mount `/` nach `/host`. Er installiert Host-Dienste, startet den verwalteten Compose-Stack und richtet nginx/Certbot ein. Der Container endet danach und wird durch `--rm` entfernt. Diese Rechte gehen nicht an die laufenden App-Container. Der Installer hat keinen unbeaufsichtigten Wiederanlauf und speichert keine Docker-Protokolle; Eingaben erfolgen im Terminal.

Er prüft vor dem Schreiben Betriebssystem, Docker-Modus, belegte Ports und vorhandene Installationen. Ein vorhandenes `/opt/kiagent-docker/project`, `/etc/kiagent-docker` oder eine fremde nginx-Konfiguration wird nicht blind überschrieben. Für bestehende Installationen ist eine gesondert geprüfte Migration nötig. Die Installation verändert keine SSH-Anmeldeverfahren und keine Cloud-Firewall.

Nach erfolgreicher Installation:

```text
https://DEINE-SERVER-IP:8443/setup
```

Im Browser das eigene Administrator-Passwort anlegen. Danach unter Einstellungen die Dienstkonfiguration prüfen. `/status` und `/automatik_status` in beiden Bots testen. Bei einem abweichenden Port entsprechend die ausgegebene HTTPS-Adresse verwenden. Es wird kein Standardpasswort und kein Einrichtungscode erzeugt.

## Anderer Port

Zum Beispiel 9443 vor dem Installationsbefehl festlegen:

```bash
SERVER_WEB_PORT=9443 docker compose -f compose.install.yaml run --rm --build installer
```

Alternativ eine `.env` im Projektverzeichnis anlegen:

```text
SERVER_WEB_PORT=9443
```

Optional können dort `SERVER_ADDRESS` und `SERVER_ADMIN_IP` stehen. Das sind eigene öffentliche Netzwerkangaben, keine Tokens. `.env` ist nicht für Git vorgesehen. Zulässig sind Port 443 oder 1024–65535 außer dem intern reservierten 8787. Ein belegter Port wird nicht übernommen. Cloud-Firewall beziehungsweise NAT müssen TCP 80 und den gewählten Web-Port durchlassen.

## Laufenden Stack bedienen

Die tatsächlichen Laufzeitdateien liegen rootgeschützt auf dem Host. Status:

```bash
sudo docker compose --env-file /etc/kiagent-docker/deployment.env -f /opt/kiagent-docker/project/compose.yaml ps
```

Start beziehungsweise Wiederanlauf:

```bash
sudo docker compose --env-file /etc/kiagent-docker/deployment.env -f /opt/kiagent-docker/project/compose.yaml up -d --wait
```

Für einen gewollten dauerhaften Wartungsstopp des verwalteten Stacks:

```bash
sudo systemctl stop kiagent-docker.service
```

Danach mit `sudo systemctl start kiagent-docker.service` wieder starten. Die systemd-Einbindung und die Container-Neustartregeln sorgen im regulären Betrieb für Start nach einem Serverneustart. `compose.install.yaml` ist nur für die Einrichtung, `compose.quickstart.yaml` weiterhin nur für das Portal. Die jeweilige Datei bei Compose-Befehlen immer ausdrücklich angeben.

## Wenn nur HTTPS fehlschlägt

Sind die vollständigen Dienste bereits eingerichtet, aber Zertifikat oder Erreichbarkeit scheitern, zuerst TCP 80, den Web-Port und die eingegebene IPv4/Administrator-IP prüfen. Nicht neu installieren und keine Secret-Verzeichnisse löschen. Der Installer hinterlässt einen rootgeschützten Nachweis und nennt dann ausdrücklich diese Wiederaufnahme:

```bash
docker compose -f compose.install.yaml run --rm --build installer --resume-network
```

Dabei dieselben Netzwerkangaben verwenden. Nur der ausstehende HTTPS-Schritt wird wiederholt; der Installer verlangt einen passenden Installationsnachweis und übereinstimmenden Quellstand. Ist bereits die Grundinstallation fehlgeschlagen, ist diese Wiederaufnahme absichtlich nicht möglich: den Zustand zuerst administrativ prüfen.

## Was geprüft wird

Die CI prüft die Installationsquellen, Host-/Portvalidierung, Überschreibschutz, Compose-Dateien, Docker-Builds, Bot-Zugriffsregeln und die echte Host-Namensraum-Verbindung des einmaligen Installers im rein lesenden `--check`-Modus. Sie startet beide Portal-Compose-Varianten mit isolierten Daten und testet Einrichtung sowie Neustart. Eine vollständige Neuinstallation mit echten Bot-Tokens und einem öffentlich ausgestellten Zertifikat ist ein eigener Betreiber-Test; in CI werden keine echten Zugangsdaten oder Host-Reparaturen benutzt.

Technischer Hinweis: `docker compose -f compose.install.yaml run --rm --build -T installer --check` prüft den Linux-Host lesend und installiert keine Dienste. Auch dieser kurze Prüflauf benötigt den ausdrücklich beschriebenen Hostzugriff.

Die bisherigen Installations- und Upgrade-Werkzeuge bleiben erhalten. Bereits laufende Installationen werden durch die Veröffentlichung dieser Datei nicht umgestellt.
