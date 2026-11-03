# Dienste und Docker-Container auf dem bestehenden IONOS-Host

Die in der vollständigen Compose-Installation enthaltene, getrennte Oberfläche verwendet HTTPS-Port **9999**. Die bisherige
Serversteuerung kann über HTTPS-Port **9898** erreicht werden. Die vorhandene
nginx-Konfiguration auf Port 443 wird nicht ersetzt.

## Funktionen

- Systemdienste einschließlich installierter, derzeit nicht geladener Dienste.
- Status, installierte Beschreibung und verständliche Erläuterungen für bekannte
  Dienstfamilien. Unbekannten Diensten wird keine erfundene Aufgabe zugeschrieben.
- Automatische Docker-Erkennung und Übersicht laufender sowie gestoppter Container.
- Start, Stop und Neustart nach Bestätigung durch Eingabe des konkreten Namens.
- Getrennte Linkseite für veröffentlichte TCP-Ports. Lokale Bindungen werden
  gekennzeichnet und nicht als öffentliche Webadresse ausgegeben. Ein TCP-Port
  beweist keine Weboberfläche; die Protokollvorschläge sind nicht automatisch geprüft.
- Aktualisierung alle 15 Sekunden, Suche und Tag-/Nachtmodus.

## Anmeldung und Grenzen

Neue Installationen richten auf der Webseite einmalig einen Benutzernamen und ein
Passwort ein. Ein Einrichtungstoken oder ein Abruf über das Terminal ist nicht
erforderlich. Das Passwort benötigt mindestens acht Zeichen, einen Großbuchstaben,
eine Zahl und ein Sonderzeichen. Die Registrierung wird nach der ersten
erfolgreichen Einrichtung geschlossen; bis dahin bleiben Daten und Aktionen gesperrt.

Bereits eingerichtete Installationen behalten das vorhandene Passwort der
Serversteuerung. systemd stellt dort ausschließlich die zugehörige Anmeldedatei
als Credential bereit. Ein Dateiwächter lädt diese bei Passwortänderungen neu und
verwirft dadurch bestehende Manager-Sitzungen. Der Webprozess besitzt weder
root-Rechte noch den Docker-Socket.
Ein getrennter root-Dienst prüft die Prozessidentität am Unix-Socket, Anmeldung,
Zielidentität, Ablaufzeit, Bestätigung und den vorherigen Zustand.

Der root-Dienst akzeptiert nur die drei festgelegten Aktionen auf tatsächlich
ermittelten Diensten und Containern; keine Shell, beliebigen Befehle oder
Docker-Optionen. Seine beiden eigenen Zugangsdienste sind vor Selbstabschaltung
geschützt. Andere kritische Dienste können den Zugang oder abhängige Anwendungen
unterbrechen. Eine bestätigte Aktion wird nie automatisch wiederholt. Unklare
Ergebnisse müssen am aktuellen Zustand und gegebenenfalls im Journal geprüft werden.

Das private Aktionsprotokoll liegt unter
`/var/lib/kiagent-services/audit.jsonl`. Es enthält keine Passwörter, Sitzungstokens,
Container-Umgebungsvariablen, Befehlszeilen oder Mount-Inhalte.

## Installation

Ab Version 1.5.0.0 genügt auf dem unterstützten frischen Linux-Host mit Docker:

```bash
git clone https://github.com/s3bb3lhu/kiagent-docker.git
cd kiagent-docker
docker compose up -d
```

Der Erstinstaller lädt den neuesten veröffentlichten stabilen Release. Die Laufzeit-
vorlage `compose.runtime.yaml` enthält `services-web` mit Profil `services`; der
Host-Installer legt automatisch Benutzer, private Sitzungsdatei, Unix-Socket und
TLS-Kopien an und startet diesen Dienst ausdrücklich. Ein erneuter Start der
bestehenden Installation führt kein Update aus. Die eigenen Konten bleiben erhalten.

Das Web-Image enthält die Seiten, SVG-Logos, Styles und Browser-Auswahl. Der Container
läuft ohne root, mit schreibgeschütztem Dateisystem, entfernten Capabilities und ohne
Docker-Socket. Nur der Host-Agent führt die festgelegten Aktionen aus. Standardports
sind 9898 und 9999; belegte Ports bleiben anderen Anwendungen erhalten. Die tatsächlichen
Adressen stehen in den beiden Dateien unter `.installation/` und im Setup-Protokoll.
Zertifikate werden in eigene, nur lesend eingebundene Dateien kopiert und per Timer
aktuell gehalten. Die Originalkonfiguration anderer Webseiten bleibt unangetastet.

Die zusätzlichen `install_services_portal.py`, `resume_services_portal.py` und
Korrekturwerkzeuge sind gezielte Hilfen für den früher getrennt eingerichteten
Bestand. Sie gehören nicht zum normalen Ablauf einer Neuinstallation.

Die Funktion ist für Linux/systemd ausgelegt. Sie ist keine Windows-Dienstverwaltung.

## Prüfung

Auf Linux mit den Web-Abhängigkeiten:

```bash
python3 -B services/test_services.py
```

Die Tests prüfen unter anderem Authentifizierung, Origin und CSRF, feste Argumente,
unbekannte Ziele, Abbrechen, veralteten Zustand, Audit-Ausfall, unklare Ergebnisse
und den Ausschluss einer erneuten Ausführung derselben Bestätigung. Sie stoppen
keine echten Dienste oder Container.
