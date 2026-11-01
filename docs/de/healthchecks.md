# Healthchecks: Lebenszeichen & Alarme

Einstellungen & Verbindungen · 1.3.0.1

1. Im eigenen Healthchecks-Konto zwei getrennte Checks für Server und Bot anlegen. Die jeweiligen UUID-Ping-URLs kopieren und unter Einstellungen → Healthchecks zuordnen. Benötigt werden Ping-URLs, kein Management-API-Schlüssel.

2. Empfänger beziehungsweise Integrationen im Healthchecks-Konto einrichten. Zeitraum und Toleranz auf die tatsächlichen Lebenszeichen abstimmen. Ein kontrollierter Alarmtest muss getrennt zeigen, dass der Check ausfällt und die Warnung beim Empfänger ankommt.

3. Beide Felder sind optional. Ping-URLs wie Passwörter behandeln und nicht ins Repository kopieren. Ausbleibende Lebenszeichen sind keine vollständige Festplatten- oder Anwendungsdiagnose.

- [Healthchecks verwalten](https://healthchecks.io/checks/)
- [Healthchecks-Dokumentation](https://healthchecks.io/docs/)
