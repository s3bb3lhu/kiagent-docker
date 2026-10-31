# Kiagent – Docker für Telegram und Discord

Private, selbst gehostete KI-Steuerung eines Ubuntu-Servers. Zugangsdaten und persönliche IDs sind **nicht enthalten**. Sie werden bei der Installation lokal eingegeben.

## Was enthalten ist

- Telegram: Status, RAM, Speicherplatz, Laufzeit, KI-Diagnose und freie KI-Fragen.
- Discord: Status, freie KI-Fragen und dieselbe begrenzte Paketverwaltung.
- Paketinstallation für **htop und tree**: Vorschau, zweiminütige einmalige Bestätigung, erneuter Planvergleich, Audit und Ergebniskontrolle. Andere Pakete werden abgewiesen.
- RAID-Monitor-Reparatur: nur `mdmonitor.service` und `mdmonitor-oneshot.service`, keine Veränderungen an RAID-Mitgliedern.
- Automatik: 60 Sekunden Prüfintervall, mindestens 120 Sekunden Störung, eine Stunde Abstand, höchstens drei Versuche je 24 Stunden und gemeinsamer 120-Sekunden-Cooldown. Telegram-Vorankündigung vor automatischen Reparaturen; dauerhafte Ergebniszustellung und Sperre bei unklarem Ergebnis.
- Automatikstatus und persistentes Ein-/Ausschalten über Telegram und Discord; Discord-Umschaltungen haben eine eigene Bestätigung.
- Healthchecks-Lebenszeichen für Host und Telegram-Bot, optional.
- Tägliche lokale Sicherung um 03:15 Uhr Europe/Berlin einschließlich SQLite-Online-Snapshot und isolierter Wiederherstellungsprüfung.

## Architektur

```text
Telegram-Container ─┐                 ┌─ Host-Status und RAID-Monitor-Steuerung
                   ├─ Unix-Sockets ──┤
Discord-Container ─┘                 └─ Bestätigte Paketinstallation

Heartbeat-Container ── HTTPS ── Healthchecks (optional)
Host-Backup-Timer ── lokale, nur für root lesbare Sicherungen
```

Die Chat-Dienste laufen ohne root, mit schreibgeschütztem Dateisystem, ohne zusätzliche Linux-Capabilities und ohne veröffentlichte Ports. **Kein Docker-Socket und kein privilegierter Container.** Die Host-Agenten bleiben systemd-Dienste: Eine Paketinstallation im Container würde sonst nur den Container verändern, und RAID/systemd gehören zum Host. Diese Trennung ist beabsichtigt.

Der Host-Agent prüft die tatsächliche UNIX-Benutzerkennung der Verbindung. Telegram und Discord benutzen getrennte Benutzer und Audit-Namensräume. Discord prüft zusätzlich Benutzer, Server, Kanal und die gebundene Bestätigungsnachricht. Die Container erhalten Host-Messwerte ausschließlich über eine feste lesende Operation, ohne Host-Dateisystem-Mount.

Eine allgemeine Root-Shell und Gameserver-Installation sind nicht enthalten. Eine eigene Konfigurationsoberfläche verwaltet Zugangsdaten und Freigaben über einen SSH-Tunnel. Der vorhandene interaktive Codex-CLI-Zugang bleibt ein separates Werkzeug auf dem Host; seine Anmeldung wird nicht übernommen oder eingecheckt.

## Voraussetzungen

- Ubuntu 26.04, Linux amd64, Python 3 und `python3-venv` für den optionalen Codex-Zugang.
- Docker Engine und Docker Compose; dieser Peer-Authentifizierungsaufbau unterstützt aktuell kein Docker-UID-Remapping und keinen rootless Docker-Daemon. Der Installer schaltet diese Schutzmechanismen nicht ab, sondern bricht ab.
- Ein Telegram-Bot und deine numerische Telegram-Benutzer-ID.
- Ein Discord-Bot mit `bot` und `applications.commands`, Zugang zu einem privaten Textkanal, deine Benutzer-ID sowie Anwendungs-, Server- und Kanal-ID. Keine Administratorrechte und keine privilegierten Gateway Intents erforderlich.
- Für die RAID-Funktionen: bereits eingerichtetes mdadm und funktionierende mdmonitor-Dienste einschließlich eines Alarmprogramms oder Mail-Empfängers. Die Migration verändert weder RAID-Konfiguration noch SSH. Der Backup-Satz erwartet `/etc/mdadm/mdadm.conf` und `/usr/local/sbin/kiagent-mdadm-alert` aus der bisherigen Einrichtung.

## Installation / Migration

Repository mit deinem eigenen GitHub-Zugang klonen oder als ZIP herunterladen. **Keine Tokens in Clone-URLs eintragen.** Die folgenden Schritte laufen im Server-Terminal im Projektverzeichnis.

```bash
sudo python3 tools/install.py
```

Der Installer fragt die Zugangsdaten lokal ab und führt anschließend die vorbereitete Migration aus. Die Schritte lassen sich alternativ einzeln ausführen:

```bash
sudo python3 tools/configure.py
sudo python3 tools/install_host.py
sudo python3 /opt/kiagent-docker/project/tools/install_web.py --before-activation
sudo python3 /opt/kiagent-docker/project/tools/activate.py
```

1. `configure.py` fragt IDs und Zugangsdaten ab. Tokens, API-Schlüssel und Ping-URLs werden unsichtbar eingegeben. Ein leerer OpenAI-Schlüssel lässt KI-Antworten deaktiviert; Status und freigegebene Aktionen funktionieren weiterhin. Leere Healthchecks-Felder überspringen die jeweiligen Pings.
2. Konfiguration liegt ausschließlich unter `/etc/kiagent-docker/`. Das Verzeichnis und sein `secrets`-Unterverzeichnis sind nur für root zugänglich. Die einzeln eingebundenen Secret-Dateien sind für die gemeinsame Dienstgruppe lesbar und werden nur den benötigten Containern bereitgestellt. Compose-Secrets sind lokale Dateien, keine automatische Verschlüsselung auf dem Datenträger.
3. `install_host.py` sichert die vorhandene Installation, erhält die SQLite-Datenbank und ihre Sperrzeiten, installiert die Host-Agenten und kehrt zunächst zu den bisherigen Chat-Diensten zurück. Bei einer bestehenden Installation müssen die eingegebenen Identitäten zu den bisherigen passen. Auf einer frischen Installation bleibt die Reparaturautomatik zunächst ausgeschaltet.
4. `activate.py` baut zuerst das Image. Erst dann stoppt es die alten Chat-Dienste und wartet auf die gesunden Chat- und Heartbeat-Container. Bei einem Fehler werden die alten Chat-Dienste wieder gestartet. Alte Zugangsdaten, Dienste und Datenbanken werden nicht gelöscht.

Der Installer überschreibt keine vorhandene Docker-Projektinstallation. Updates werden gezielt vorbereitet; es gibt keinen unbeaufsichtigten Selbst-Update-Mechanismus.

## Konfigurationsseite im Browser

Bei einer Neuinstallation fragt der Installer zusätzlich nach einem eigenen Web-Administratorpasswort mit mindestens 16 Zeichen. Bei einer bestehenden Docker-Installation wird die Oberfläche aus dem geprüften neuen Projektstand ergänzt:

```bash
sudo python3 tools/install_web.py
```

Der Installer baut ein separates Web-Image, sichert den bisherigen Stand und startet die Oberfläche. Die vorhandenen Bot-Tokens werden dabei nicht verändert. Das Passwort wird verdeckt im Server-Terminal eingegeben und nicht ausgegeben. Es wird nur als gesalzener Passwort-Hash gespeichert.

Öffne anschließend auf deinem eigenen Computer einen Tunnel und lasse das Terminal geöffnet:

```bash
ssh -N -L 8787:127.0.0.1:8787 seb@DEIN-SERVER
```

Rufe [http://127.0.0.1:8787](http://127.0.0.1:8787) auf und melde dich mit deinem Web-Passwort an. Die Oberfläche ist ausschließlich an die Loopback-Adresse des Servers gebunden. Es wird kein öffentlicher Web-Port und keine Domain benötigt. Ein SSH-Schlüssel mit der Option `restrict` erlaubt diesen Tunnel möglicherweise nicht; nutze deinen bisherigen regulären SSH-Zugang. Der Installer ändert keine SSH-Einstellungen.

Die Seite erklärt direkt neben den Feldern, wo Telegram- und Discord-Bot-Tokens, der optionale OpenAI-API-Schlüssel, beide optionalen Healthchecks-Ping-URLs und die benötigten IDs zu finden sind. Gespeicherte Tokens werden niemals wieder an den Browser geschickt. Leere Token-Felder behalten vorhandene Werte bei; optionale Schlüssel können ausdrücklich entfernt werden.

Beim Speichern prüft der feste Host-Dienst Eingaben und geänderte Bot-Anmeldungen, erstellt eine rootgeschützte Sicherung und lädt die betroffenen Dienste kontrolliert neu. Chat-Bots und Lebenszeichen können dabei kurz unterbrochen sein. Aktive oder unklare Reparatur-/Paketaktionen verhindern die Änderung. Historie und Sperrzeiten werden beibehalten. Bei einem Startfehler wird die vorherige Konfiguration wiederhergestellt; ein unterbrochener Vorgang wird nicht automatisch wiederholt und muss per SSH geprüft werden. Eine erfolgreiche Übernahme bestätigt keine umfassende Funktionsprüfung aller externen Anbieter.

Die Konfigurationsseite hat weder Docker-Socket noch direkten Zugriff auf die Bot-Schlüssel. Ein eigener Host-Dienst akzeptiert über einen Unix-Socket ausschließlich die festgelegten Konfigurationsoperationen vom getrennten Dienstbenutzer. Der normale Desktop- oder Chat-Zugang erhält keine Root-Shell.

## Prüfung

```bash
sudo docker compose --env-file /etc/kiagent-docker/deployment.env \
  -f /opt/kiagent-docker/project/compose.yaml ps
```

Danach Telegram `/status`, `/automatik_status` und Discord `/status`, `/automatik_status` prüfen. `/ki_install htop` erkennt eine vorhandene Installation ohne erneute Ausführung. Änderungen erst nach Prüfung des Plans bestätigen. Unklare Paketversuche bleiben gesperrt, bis sie per SSH überprüft wurden.

## Rückkehr zu den nativen Chat-Diensten

```bash
sudo python3 /opt/kiagent-docker/project/tools/rollback.py
```

Die Datenbank wird dabei nicht auf einen alten Stand zurückgesetzt. Bestätigungen, Historie und verbrauchte Cooldowns dürfen nicht durch Wiederherstellen einer älteren Datenbank erneut verwendbar werden. Bei einer frischen Installation ohne frühere native Frontends gibt es diesen Rückweg nicht.

## Sicherungen

Archive liegen unter `/var/backups/kiagent-daily/`, nur für root lesbar. Sie enthalten die lokal eingegebenen Zugangsdaten und dürfen **niemals** ins Repository oder in öffentliche Artefakte hochgeladen werden. Online-Snapshot und isolierte Restore-Prüfung prüfen Konsistenz; eine vollständige Wiederherstellung auf einem neuen Server ist ein gesonderter Test. Backups auf demselben RAID ersetzen keine externe Sicherung. Es gibt keine automatische Löschung alter Archive.

## Entwicklung und Sicherheitsprüfung

```bash
python3 tools/scan_secrets.py
python3 -B -m unittest discover -s tests -v
docker build -t kiagent:review .
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --tmpfs /tmp:rw,mode=1777 \
  -v "$PWD:/workspace:ro" -w /workspace --entrypoint python \
  kiagent:review -B -m unittest discover -s tests -v
```

Python-Image und Abhängigkeiten sind per Digest beziehungsweise Hash festgelegt. Der Lockfile ist für Linux amd64 mit CPython 3.14. GitHub Actions prüft Quellcode, Secret-Scan, Freigabelogik und Docker-Build ohne echte Zugangsdaten.
