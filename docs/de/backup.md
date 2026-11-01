# Sicherungen & Wiederherstellung

Betrieb & Wartung · 1.3.0.1

1. Die verwaltete Linux-Installation sichert täglich um 03:15 Europe/Berlin nach /var/backups/kiagent-daily. Archive enthalten private Zugangsdaten und einen konsistenten SQLite-Snapshot und sind nur für root lesbar. Es gibt keine automatische Löschung alter Archive; freien Platz überwachen.

2. Eine isolierte Wiederherstellungsprüfung bestätigt Dateien und Datenbankkonsistenz, keinen vollständigen neuen Server. Backups auf demselben RAID schützen nicht vor dessen vollständigem Verlust. Externe Sicherung separat planen. Niemals Archive, Volumes oder Auth-Dateien veröffentlichen.

3. Bei Wiederherstellung Dienste kontrolliert anhalten, Besitz/Rechte prüfen und keine alte Historie auf ein bereits weitergelaufenes System zurückspielen. Sonst könnten verbrauchte Freigaben wiederverwendbar werden. Web-Passwortzustand liegt separat und ist nicht Teil der täglichen Konfigurationssicherung; bei Wiederherstellung administrativ neu setzen.

