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
