# Updates, Version & Fehlerhilfe

Betrieb & Wartung · 1.0.0.1

1. Die Produktversion steht unten im Menü. Die aktuelle Veröffentlichung trägt die Version 1.0.0.1. Updates werden ausdrücklich aus einem geprüften Quellstand installiert; es gibt kein unbeaufsichtigtes Selbst-Update. Vorher offene oder unklare Aufträge prüfen und Sicherungen kontrollieren.

2. Auf bestehender verwalteter Installation tools/install_ui.py aus dem vorbereiteten Stand mit sudo starten. Das Skript testet isoliert, sichert Code und Images und prüft den Neustart. Zugangsdaten, Passwort, Historie und Sperrzeiten bleiben erhalten. Danach Browser mit Strg+F5 neu laden.

3. Bei 502 oder fehlender Bot-Antwort zunächst Dienstzustände, Container-Gesundheit und gespeichertes Installationsergebnis per SSH lesen. Bei KI-Fehlern OpenAI-Konfiguration und Projektzugang prüfen; /status und /ki_install bleiben unabhängig von KI. Bei Cookie-Fehlern Anmeldung neu öffnen und Cookies zulassen.

4. Keine Tokens oder unbereinigten Journale in öffentliche Issues kopieren. Ein unklarer Aktionsausgang wird nicht automatisch wiederholt. Bei eigener Anpassung die installierten Dateien vor einem Update mit dem Projektstand vergleichen.

```text
systemctl is-active kiagent-config kiagent-docker kiagent-executor kiagent-packages
```

```text
sudo python3 tools/install_ui.py
```

