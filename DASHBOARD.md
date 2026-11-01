# Dashboard

Die angemeldete Oberfläche hat die Bereiche Status, Steuerung, SSH Console und Einstellungen. Das Menü lässt sich einklappen. API-Schlüssel werden je Dienst auf einer eigenen Einstellungsseite verwaltet; dort liegt auch die Passwortänderung. Über die Sprachauswahl unten links stehen Deutsch, Englisch, Spanisch und Französisch zur Verfügung. Ruby Control und Crimson Glass gibt es in Rot, Blau, Grün, Lila und Anthrazit, jeweils mit Tag-/Nachtmodus. Design, Farbe, Modus, Menü und Sprache werden für diesen Browser gespeichert. Zahlen, Datumsangaben, Meldungen und Bestätigungen folgen der gewählten Sprache. Technische Kennungen wie `/automatik_an`, Paketnamen, Schnittstellen und Dateisystempfade bleiben unverändert.

Unter Einstellungen → Dokumentation stehen Anleitungen nach Installation, Einstellungen, Funktionen und Betrieb. Dieselben Inhalte liegen in vier Sprachen unter `docs/`. Die Version wird unten im Menü angezeigt; die aktuelle Veröffentlichung ist `1.2.0.1`. Die gewählte Wort-/Bildmarke C verbindet ein S-Symbol mit einem übersetzten Schriftzug; Symbol und Akzent folgen der Farbwahl.

Der Kopfbereich zeigt lokale Zeit und separat die vom Host gelieferte Serverzeit mit Zeitzone. Bei ausbleibenden Antworten wird die Serveruhr nach 45 Sekunden als nicht verfügbar markiert. Der Status zeigt alle logischen CPU-Kerne; die Auslastung benötigt jeweils zwei Messungen.

## SSH Console

Die Konsole ist eine lesende Aktivitätsansicht, keine interaktive SSH-Shell. Sie zeigt feste KI-Bearbeitungsphasen aus den Bots seit deren letztem Neustart sowie die jüngsten Paket- und Webaufträge. Anfragen, KI-Antworten und Geheimnisse werden nicht protokolliert. APT-Fortschritt wird ausschließlich aus bekannten Zeilenpräfixen und Paketnamen des tatsächlichen Plans extrahiert; rohe Ausgaben von Installationsskripten werden niemals an den Browser weitergegeben. Auftragserstellungszeiten sind entsprechend beschriftet, APT-Schritte ohne Einzelzeit bleiben ohne erfundene Zeitangabe. Ohne passenden Host-Adapter bleibt die Seite vorhanden und weist auf die fehlende Anbindung hin.

## Status

Die Linux-Host-Anbindung liest alle drei Sekunden CPU-Auslastung, Kernzahl, Systemlast, RAM, Laufzeit, physische Laufwerke, eingehängte Dateisysteme, Netzwerkraten und zugewiesene IP-Adressen. CPU- und Netzwerkraten benötigen zwei Messungen. Bei einem Verbindungsfehler werden alte Werte als veraltet markiert. Verdeckte Browser-Tabs pausieren die Abfrage. Die angezeigten Daten kommen vom Host, nicht aus dem Webcontainer. Die IP-Ermittlung verwendet keinen externen Dienst. Unzugewiesene öffentliche NAT-Adressen können nur anhand der konfigurierten Zugangsadresse angezeigt werden.

Laufwerkskapazität und Belegung sind keine SMART- oder umfassende Festplattengesundheitsprüfung. Die portable Oberfläche ohne Host-Adapter zeigt ausdrücklich keine vorgetäuschten Host-Werte.

## Steuerung

Die Statusbefehle `/status`, `/ram`, `/disk` und `/uptime` öffnen die entsprechende Statusansicht. `/automatik_status` und `/ki_install_status` sind zusätzliche lesende Abfragen. KI-Fragen und KI-Diagnosen über `/ki` und `/diagnose` bleiben in den Bots verfügbar; sie werden nicht als frei ausführbare Shell-Befehle angeboten.

Direkt ausführbar sind die getesteten RAID-Monitor-Aktionen, Ein-/Ausschalten der Automatik, der isolierte Übungsdienst, ein Bestätigungstest sowie die Installation beliebiger Pakete aus eingerichteten APT-Quellen. Ein freies Paketfeld ergänzt die Schnellknöpfe für htop/tree. Jede Änderung verlangt eine eigene, kurzlebige Bestätigung. Paketversionen werden vor Ausführung angezeigt und vom vorhandenen Paket-Agenten erneut geprüft. Die bisherigen 120-Sekunden-Cooldowns, Automatikgrenzen und Sperren bleiben maßgeblich. Ein geänderter Paketplan wird nicht ausgeführt.

Die Root-Anbindung akzeptiert ausschließlich feste Operationen. Sie verwendet für bestehende Host-Agenten die primäre freigegebene Telegram-Identität als Transport und protokolliert die Web-Sitzung zusätzlich als Hash. Keine Kommunikation wird dabei als Telegram-Nachricht versendet. Die Web-App erhält weder Docker-Socket noch Geheimnisse aus dem Root-Agenten.

Bestätigungen sind an die Web-Sitzung gebunden, verfallen nach 120 Sekunden und werden vor jeder Ausführung dauerhaft verbraucht. Unklare Ergebnisse werden nicht automatisch wiederholt. Offene Ausführungen werden nach einem Broker-Neustart als unklar gesperrt und benötigen eine Prüfung per SSH. Die Audit-Dateien liegen rootgeschützt unter `/var/lib/kiagent-config/actions`; Code-Rollbacks setzen diese Aufträge nicht zurück.

## Server-Neustart

Der Kopfbereich enthält links neben Abmelden einen echten Server-Neustart. Nach Öffnen des Dialogs müssen die Wirkung bestätigt und das angezeigte Wort eingegeben werden. Erst danach wird genau ein fester systemd-Neustartauftrag mit etwa zehn Sekunden Verzögerung angelegt. Das Ergebnis „angefordert“ ist keine Bestätigung eines bereits abgeschlossenen Neustarts. Die Webseite und Bots sind währenddessen vorübergehend nicht erreichbar. Ein neuer Neustartauftrag ist fünf Minuten gesperrt; aktive oder unklare Reparatur-/Paketvorgänge verhindern die Freigabe. Der Installer führt keinen Server-Neustart und keine Reparatur aus.

## Aktualisierung

Aus dem vorbereiteten Quellstand auf der bestehenden verwalteten Linux-Installation:

```bash
sudo python3 tools/install_ui.py
```

Der Installer sichert den Stand, baut und testet die Images mit isolierten Beispieldaten, aktualisiert Web-Image und begrenzten Konfigurationsdienst und prüft Host-Messwerte sowie lesende Agentenaufrufe. Das vorhandene Passwort, Bot-Tokens, Host-Agenten und SQLite-Historie werden nicht zurückgesetzt. Bei einem Fehler werden vorherige Code-Dateien und das vorherige Web-Image wiederhergestellt. Anschließend den Browser mit Strg+F5 neu laden.

Windows benötigt weiterhin einen passenden Host-Adapter für native Aktionen. Die portable Oberfläche bleibt ohne solchen Adapter auf Konfiguration beschränkt; ihre Host-Schaltflächen sind deaktiviert.

## Speichern und Verfügbarkeit

Beim Speichern werden die Chat-/Heartbeat-Container kurz angehalten und die Host-Agenten laden ihre Zugangsdaten neu. Die Weboberfläche bleibt dabei gestartet. Die Agenten sind dafür weiche `Wants`-Abhängigkeiten des Docker-Dienstes; ein `Requires` würde beim Anhalten eines Agenten den gesamten Stack einschließlich der Webseite stoppen. Für bereits betroffene Installationen korrigiert `sudo python3 tools/fix_save_lifecycle.py` die Dienstdatei und stellt die Erreichbarkeit wieder her. Der Helfer zeigt nur den gespeicherten Ergebnisstatus, keine Schlüssel, und prüft per Hash, dass Zugangsdaten und Passwort unverändert bleiben. Unterbrochene oder unklare Speicheraufträge werden nicht erneut ausgeführt.
