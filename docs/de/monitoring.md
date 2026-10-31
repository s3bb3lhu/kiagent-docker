# RAID-Überwachung & Automatik

Einstellungen & Verbindungen · 1.0.0.0

1. Unter Einstellungen → Überwachung nur vorhandene md-Gerätenamen wie md4 eintragen. RAID-Mitglieder, Partitionen und Synchronisation werden nicht verändert. Ein Resync bei degraded=0 ist kein Nachweis eines Plattenausfalls.

2. Die Automatik prüft alle 60 Sekunden. Nur eine mindestens 120 Sekunden anhaltende Störung der getesteten RAID-Monitor-Dienste darf repariert werden. Grenzen: eine Stunde Abstand, höchstens drei Versuche in 24 Stunden und gemeinsamer 120-Sekunden-Cooldown.

3. /automatik_status zeigt Zustand, letzte Versuche und Sperrzeiten. /automatik_an und /automatik_aus schalten dauerhaft um. Telegram-Vorankündigung ist vor jeder automatischen Reparatur erforderlich; Ergebnisse bleiben bis zur Zustellung gespeichert. Fehler oder unklare Ergebnisse sperren bis erfolgreichem manuellem /raid_monitor_start.

4. Die freigegebene Reparatur betrifft ausschließlich mdmonitor.service und mdmonitor-oneshot.service. Ein erfolgreich inaktiver oneshot-Dienst ist normal. Dies ist keine SMART-Prüfung oder automatische Reparatur von Laufwerken.

