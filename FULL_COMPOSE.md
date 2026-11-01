# Vollinstallation per Docker Compose — 1.4.0.0

**Neuer Standard auf main:** Für `docker compose up -d` ohne zusätzliche Installationsbefehle siehe [FIRST_INSTALL.md](FIRST_INSTALL.md). Die folgenden Befehle dokumentieren den weiterhin vorhandenen expliziten Installer und den Host-Betrieb.

Diese Variante installiert und startet Telegram, Discord, Weboberfläche, Host-Lebenszeichen, begrenzte Serveraktionen und lokale Sicherungen. Die festen Root-Agenten werden vom einmaligen Installer als systemd-Dienste auf dem Linux-Host eingerichtet. Im laufenden Betrieb erhalten Bots und Weboberfläche weder einen privilegierten Container noch einen Docker-Socket.

## Voraussetzungen

- Ubuntu-24.04-/26.04-Server, amd64, mit systemd, Python >=3.10, Docker Engine und Compose. Kein rootless Docker und kein UID-Remapping; vorhandene Schutzoptionen werden nicht abgeschaltet.
- Öffentlich erreichbare IPv4-Adresse des Servers. Bei der Einrichtung eines neuen Zertifikats muss **TCP 80** erreichbar sein. Auf belegten Hosts wird ein gültiges vorhandenes IP-Zertifikat übernommen; dort benötigt die Serversteuerung nur ihren neuen HTTPS-Port. Der Standardport auf freien Hosts ist 8443, im Parallelbetrieb ein freier Port ab 9443.
- Eigener Telegram-Bot samt Benutzer-ID; Discord-Anwendung, Bot, Benutzer-, Server- und private Kanal-ID. IDs und Tokens werden erst nach dem Docker-Start in der geschützten Weboberfläche eingegeben. OpenAI und Healthchecks sind optional. Niemand muss Zugangsdaten im Chat oder Repository veröffentlichen.
- Installation aus einer direkten SSH-Sitzung; Browser und SSH verwenden denselben Internetzugang. Die Adresse für die Ersteinrichtung wird automatisch erkannt. Bei `sudo` nutzt der Installer ersatzweise die eindeutige aktive SSH-Anmeldung des Hosts.
- RAID-Funktionen benötigen tatsächlich vorhandenes mdadm/RAID und eingerichtete Alarmempfänger. Ohne RAID-Geräte das Feld leer lassen; die Automatik bleibt bei einer Neuinstallation ausgeschaltet. Es werden keine Laufwerke formatiert und kein RAID angelegt.

Windows Server benötigt eine entsprechende Linux-VM. Docker Desktop beziehungsweise ein nativer Windows-Container ist kein unterstützter Host für die vollständige Serversteuerung. Das reine Konfigurationsportal bleibt separat verfügbar.

## Installation und Start

Auf einem geeigneten Server ohne vorhandene vollständige Kiagent-Hostinstallation:

```bash
git clone --branch v1.4.0.0 --depth 1 https://github.com/s3bb3lhu/kiagent-docker.git kiagent-docker-1.4.0.0
cd kiagent-docker-1.4.0.0
docker compose -f compose.install.yaml run --rm --build installer
```

Falls dein Benutzer Docker nicht direkt bedienen darf, denselben Compose-Befehl mit `sudo` ausführen. Im Terminal gibt es keine Eingabeabfragen. Server-IP und die für `/setup` zugelassene Administrator-Adresse werden automatisch aus der SSH-Verbindung beziehungsweise der eindeutigen Host-Anmeldung und den öffentlichen Netzwerkschnittstellen erkannt. Danach wird die fertige Webadresse ausgegeben. Passwort, Dienst-IDs, API-Keys und Bot-Tokens werden ausschließlich auf der Seite eingegeben. Der Installer richtet das HTTPS-Zertifikat automatisch bei Let's Encrypt ein und verwendet dessen veröffentlichte [Nutzungsbedingungen](https://letsencrypt.org/repository/). Nicht mit `up -d` starten; das Installationsprofil ist gegen einen versehentlichen automatischen Start geschützt.

Ohne eindeutig erkennbare SSH-Adresse oder bei mehreren unterschiedlichen angemeldeten Gegenstellen wird vor der Host-Konfiguration abgebrochen. Es wird keine ungeschützte öffentliche Ersteinrichtung freigegeben. Bei NAT oder mehreren öffentlichen Server-Adressen ist dieser automatische Standardweg nicht unterstützt.

**Dieser einmalige Installer hat Administratorrechte:** privilegierter Container, Host-PID-Namensraum und schreibbarer Mount `/` nach `/host`. Er installiert Host-Dienste, startet den verwalteten Compose-Stack und richtet nginx/Certbot ein. Der Container endet danach und wird durch `--rm` entfernt. Diese Rechte gehen nicht an die laufenden App-Container. Der Installer hat keinen unbeaufsichtigten Wiederanlauf und speichert keine Docker-Protokolle; Es werden keine Zugangsdaten im Terminal eingegeben.

Er prüft vor dem Schreiben Betriebssystem, Docker-Modus, belegte Ports und vorhandene Installationen. Ein vorhandenes `/opt/kiagent-docker/project` oder `/etc/kiagent-docker` wird nicht überschrieben. Fremde nginx-Konfigurationen werden nicht verändert; auf belegten Hosts wird der unten beschriebene Parallelbetrieb verwendet. Für bestehende Installationen ist eine gesondert geprüfte Migration nötig. Die Installation verändert keine SSH-Anmeldeverfahren und keine Cloud-Firewall.

Nach erfolgreicher Installation:

```text
https://DEINE-SERVER-IP:8443/setup
```

Im Browser zuerst das eigene Administrator-Passwort anlegen. Danach öffnet sich die gemeinsame Dienst-Einrichtung unter `/settings/setup`: Telegram-/Discord-IDs und Bot-Tokens eingeben, optional OpenAI und Healthchecks ergänzen und **Prüfen und aktivieren** wählen. Bis dahin laufen nur Weboberfläche und Konfigurationsdienst; Bots und Host-Aktionen bleiben auch nach Neustarts gesperrt. Erst nach erfolgreicher Providerprüfung werden die Host-Agenten und Bots gestartet. Ein fehlgeschlagener Start setzt die neue Dienstkonfiguration zurück; unklare Rücksetzungen sperren weitere Änderungen zur manuellen Prüfung. Danach unter Einstellungen die Dienstkonfiguration prüfen. `/status` und `/automatik_status` in beiden Bots testen. Bei einem abweichenden Port entsprechend die ausgegebene HTTPS-Adresse verwenden. Es wird kein Standardpasswort und kein Einrichtungscode erzeugt.

## Parallelbetrieb neben vorhandenen Anwendungen

Sind nginx oder die üblichen Ports bereits belegt, wählt der Installer automatisch einen freien eigenen HTTPS-Port ab 9443 sowie vorübergehend einen freien internen Port ab 18787. Das alte Konfigurationsportal auf 8787 und andere Container bleiben unverändert. Der Installer führt für fremde Dienste weder Stop, Neustart noch Reload aus und schreibt keine vorhandene nginx-Konfiguration um. Die neu angelegten begrenzten Host-Agenten gehören nur zur Serversteuerung; eine vorhandene vollständige Kiagent-Installation wird weiterhin abgewiesen.

Das Zertifikat wird automatisch in `/etc/letsencrypt` oder in einem Ordner gefunden, den ein laufender Container nach `/etc/letsencrypt` eingebunden hat. Zertifikat, öffentliche IP, Vertrauenskette, Gültigkeit, Schlüsselzuordnung und rootgeschützte Pfade werden vor der Hostinstallation geprüft. Es werden ausschließlich eigene rootgeschützte Kopien angelegt; die bestehenden Zertifikatsdateien werden nicht verändert. Ein eigener Timer übernimmt Erneuerungen alle sechs Stunden und lädt ausschließlich die neue Weboberfläche neu. Läuft die vorhandene Zertifikatserneuerung nicht mehr, meldet der eigene Timer einen Fehler; sie wird nicht automatisch umkonfiguriert.

Der neue Webcontainer spricht auf diesem Weg direkt TLS. Die Ersteinrichtung bleibt auf die automatisch erkannte Administrator-IP beschränkt; interne Healthchecks prüfen ebenfalls TLS und den Zertifikatsnamen. Gibt es kein geeignetes Zertifikat, bricht der Installer vor der eigentlichen Hostinstallation ab. Es wird kein selbst signiertes Zertifikat oder unverschlüsselter öffentlicher Zugang als Ersatz eingerichtet.

Nach Abschluss die **tatsächlich ausgegebene URL** verwenden, zum Beispiel `https://SERVER-IP:9443/setup`. Nur diesen neuen Port bei Bedarf zusätzlich in der Cloud-Firewall erlauben. Diese Firewall wird nicht automatisch geändert. Bereits gespeicherte Einstellungen des alten Portal-Volumes werden nicht kopiert; die neue vollständige Installation wird im Browser eingerichtet.

## Anderer Port

Zum Beispiel 9443 vor dem Installationsbefehl festlegen:

```bash
SERVER_WEB_PORT=9443 docker compose -f compose.install.yaml run --rm --build installer
```

Alternativ eine `.env` im Projektverzeichnis anlegen:

```text
SERVER_WEB_PORT=9443
```

Die Server- und Administrator-IP werden nicht per `.env` abgefragt. `.env` ist nicht für Git vorgesehen. Zulässig sind Port 443 oder 1024–65535 außer dem intern reservierten 8787. Ein belegter Port wird nicht übernommen. Cloud-Firewall beziehungsweise NAT müssen TCP 80 und den gewählten Web-Port durchlassen.

## Laufenden Stack bedienen

Vor abgeschlossener Web-Einrichtung nicht alle Dienste von Hand mit `compose up` starten. Der verwaltete systemd-Start verwendet eine Sperre und startet während der Ersteinrichtung nur die Weboberfläche. Die folgenden direkten Compose-Startbefehle sind erst **nach erfolgreicher Einrichtung** vorgesehen.

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

Bei Version 1.3.0.0 kann nach erfolgreicher Web-Grundinstallation `getwd: no such file or directory` auftreten. Der laufende Installer hat dann ein im Host-Namensraum nicht erreichbares Arbeitsverzeichnis geerbt. Für genau diesen Fehler die vorhandene Installation direkt auf dem Host aus einem gültigen Ordner fortsetzen, ohne neue Dateien über die Installation zu kopieren:

```bash
sudo sh -c 'cd /opt/kiagent-docker/project && exec /usr/bin/python3 -I -B tools/host_compose_install.py --resume-network'
```

Der vorhandene Installationsnachweis, Port und Zertifikat werden weiterverwendet. Keine Secret-Verzeichnisse oder Container löschen. Ab Version 1.3.0.1 setzt der Installer ausdrücklich ein erreichbares Host-Arbeitsverzeichnis; die CI prüft den TLS-Schritt zusätzlich aus einem zuvor entfernten Arbeitsverzeichnis.

Ist die Web-Grundinstallation vorhanden, aber Zertifikat oder Erreichbarkeit scheitern, zuerst den ausgegebenen Web-Port, die Zertifikatsquelle und die automatisch erkannten Adressen prüfen. Bei einem neu ausgestellten Zertifikat zusätzlich TCP 80 prüfen. Nicht neu installieren und keine Secret-Verzeichnisse löschen. Der Installer hinterlässt einen rootgeschützten Nachweis und nennt dann ausdrücklich diese Wiederaufnahme:

```bash
docker compose -f compose.install.yaml run --rm --build installer --resume-network
```

Die Wiederaufnahme übernimmt Port und Adressen aus dem gespeicherten Installationsnachweis. Nur der ausstehende HTTPS-Schritt wird wiederholt; der Installer verlangt einen passenden Installationsnachweis und übereinstimmenden Quellstand. Ist bereits die Grundinstallation fehlgeschlagen, ist diese Wiederaufnahme absichtlich nicht möglich: den Zustand zuerst administrativ prüfen.

## Was geprüft wird

Die CI prüft die Installationsquellen, Host-/Portvalidierung, Überschreibschutz, Compose-Dateien, Docker-Builds, Bot-Zugriffsregeln und die echte Host-Namensraum-Verbindung des einmaligen Installers im rein lesenden `--check`-Modus. Sie startet beide Portal-Compose-Varianten mit isolierten Daten und testet Einrichtung sowie Neustart. Ein zusätzlicher CI-Test installiert die Web-Grundlage auf dem frischen CI-Host, setzt ein Testpasswort und prüft den gemeinsamen Dialog, leere Provider-Dateien und gesperrte Bots/Agenten/Aktionen. Ein weiterer CI-Test belegt absichtlich einen fremden Port, richtet den getrennten TLS-Zugang mit Testzertifikat ein und prüft sichere Anmeldung, unveränderte Quelldateien und den eigenen Erneuerungstimer. Eine vollständige Aktivierung mit echten Bot-Tokens und einem öffentlich ausgestellten Zertifikat ist ein eigener Betreiber-Test; in CI werden keine echten Zugangsdaten oder Host-Reparaturen benutzt.

Technischer Hinweis: `docker compose -f compose.install.yaml run --rm --build -T installer --check` prüft den Linux-Host lesend und installiert keine Dienste. Auch dieser kurze Prüflauf benötigt den ausdrücklich beschriebenen Hostzugriff.

Die bisherigen Installations- und Upgrade-Werkzeuge bleiben erhalten. Bereits laufende Installationen werden durch die Veröffentlichung dieser Datei nicht umgestellt.
