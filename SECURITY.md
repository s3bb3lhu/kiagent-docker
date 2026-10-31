# Sicherheitsgrenzen

- Niemals API-Schlüssel, Bot-Tokens, Healthchecks-Ping-URLs, SSH-Schlüssel, Datenbankdateien, Backups oder Laufzeitprotokolle einchecken. `.gitignore`, `.dockerignore` und `tools/scan_secrets.py` ergänzen sich; kein Scanner erkennt garantiert jedes Geheimnis.
- Das Repository enthält keine Anmeldung des interaktiven Codex-CLI.
- Der Bot kann KI-Antworten und Pläne erstellen. Modelltext wird nicht als Shell-Befehl ausgeführt.
- Host-Paketaktionen sind auf htop/tree beschränkt. Der Root-Agent vergleicht den Paketplan nach Bestätigung erneut und lehnt Entfernungen und Aktualisierungen ab. Ein unklarer Versuch wird nicht automatisch wiederholt.
- RAID-Aktionen bearbeiten nur die beiden Monitor-Dienste. Sie reparieren keine Dateisysteme, Partitionen, Laufwerke oder RAID-Mitglieder.
- Discord ist auf Benutzer, Server und Kanal begrenzt. Bestätigungen sind zusätzlich an Nachricht und Ablauf gebunden. Bei Neustarts werden offene Umschaltbestätigungen ungültig.
- UNIX-Peer-Authentifizierung setzt unveränderte Host-UIDs voraus. Kein Rootless-/UID-Remapping-Workaround wird automatisch angewendet.
- Lokale Sicherungen enthalten Geheimnisse und bleiben rootgeschützt. Nur der bereinigte Programmquellstand gehört nach GitHub.
- Bestehende Schlüssel werden durch diesen Export weder widerrufen noch aus der laufenden Serverinstallation gelöscht. Falls ein Schlüssel außerhalb dieser Installation veröffentlicht wurde, muss er beim jeweiligen Anbieter separat rotiert werden.

- Die Docker-Konfigurationsseite lauscht nur auf Server-Loopback. Zugriff erfolgt über SSH-Tunnel oder den gesonderten, geprüften nginx-HTTPS-Installer mit eigenem Web-Passwort. Beim HTTPS-Betrieb wird ausschließlich die konfigurierte öffentliche Adresse akzeptiert; ungeprüfte Forwarded-Header werden nicht vertraut. Port 8787 bleibt lokal.
- Passwort-Hash, Sitzungsschlüssel und Anbieter-Tokens liegen nur auf dem Zielserver. Der Browser erhält für gespeicherte Tokens ausschließlich den Status „eingerichtet“, niemals den bisherigen Wert.
- Die Web-App läuft als eigener unprivilegierter Benutzer ohne Docker-Socket. Der Root-Konfigurationsdienst hat feste Eingabefelder, feste Dateiziele und feste Dienstaktionen; Modelltext und Formulare können keine beliebigen Befehle ausführen.
- Schreibzugriffe erfordern Anmeldung, CSRF-Prüfung, passenden Host/Origin und aktuellen Konfigurationsstand. Die Seite lädt keine externen Skripte oder Schriftarten. Sitzungen laufen nach 30 Minuten ab.
- Sicherungen enthalten auch alte Schlüssel. Ein Rollback macht eine beim Anbieter widerrufene Zugangsdaten-Version nicht wieder gültig. Bei unterbrochener Übernahme oder fehlgeschlagener Wiederherstellung bleiben weitere Änderungen bis zur Prüfung per SSH gesperrt.
