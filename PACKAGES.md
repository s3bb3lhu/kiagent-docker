# Allgemeine Paketinstallation

Die feste Liste htop/tree ist entfernt. Alle syntaktisch gültigen APT-Paketnamen aus den auf dem Host eingerichteten Paketquellen dürfen einen Installationsplan anfordern. Der Host-Agent installiert weiterhin auf dem Server, nicht nur im Chat-Container. Die bisherigen Benutzer-, Discord-Server-/Kanal- und Web-Anmeldeprüfungen bleiben erhalten.

## Verwendung

- Telegram: `/ki_install nginx` oder `/ki Installiere nginx`.
- Discord: `/ki_install` mit freiem Paketnamen oder `/ki` mit einem Installationswunsch.
- Webseite → Steuerung → APT-Paket installieren → Paketname eingeben.
- Ergebnisse später über `/ki_install_status` beziehungsweise die Steuerungsseite abfragen.

Jeder Auftrag betrifft ein Zielpaket mit dessen Abhängigkeiten. Bei einem KI-Wunsch nach mehreren Zielpaketen wird gefragt, welches zuerst installiert werden soll. Für explizite Paketnamen ist kein OpenAI-Schlüssel erforderlich. Die KI verwendet ein festes JSON-Schema mit Installationstyp, Paketname und Antwort. Nur ein geprüfter Paketname wird an die Planungsfunktion weitergereicht. KI-Text wird niemals als Shellskript ausgeführt und gilt nicht als Bestätigung.

## Ausführung

1. Der Agent prüft den Paketnamen und simuliert APT aus den bestehenden Paketquellen.
2. Bereits installierte Zielpakete werden gemeldet, ohne sie erneut zu installieren. Der Vorgang ist kein allgemeines Systemupgrade.
3. Der vollständige Plan wird angezeigt. Lange Pläne werden in Telegram/Discord als Textdatei beigefügt. In der Webseite werden alle geplanten Paketversionen im Bestätigungsdialog aufgelistet.
4. Die Freigabe ist an Benutzer/Plattform/Nachricht beziehungsweise Web-Sitzung und Plan gebunden. Sie gilt zwei Minuten. Abbrechen führt keine Installation aus.
5. Nach Bestätigung wird die Freigabe dauerhaft verbraucht und der Plan erneut simuliert. Änderungen brechen den Vorgang ab. Alle geplanten Versionen werden für die echte Installation fest vorgegeben.
6. APT läuft im Hintergrund. Der Status bleibt abfragbar. Erst nach erfolgreichem Ende und Prüfung des Zielpakets sowie aller geplanten Abhängigkeitsversionen wird Erfolg gespeichert und gemeldet.

Die Grenze von zehn neuen Paketen entfällt. Abhängigkeiten dürfen entsprechend dem bestätigten Plan aktualisiert werden; Dienste können durch Paket-Maintainerskripte neu gestartet werden. Vorhandene geänderte Konfigurationsdateien werden mit `--force-confold` beibehalten. Entfernen und Herabstufen sind nicht freigegeben. Paketnamen sind keine URLs, lokalen `.deb`-Pfade, APT-Optionen oder Shellbefehle. Neue Paketquellen und Signaturschlüssel werden nicht automatisch hinzugefügt. Die konkrete Installierbarkeit hängt weiterhin von Architektur, Paketquellen, Abhängigkeiten, Platz und Betriebssystem ab.

Ein aktiver oder unklarer Paketvorgang sperrt weitere Installationen. Ein Prozessabbruch während einer gestarteten Installation wird als unklar markiert und nicht wiederholt. Eine unterbrochene reine Planprüfung wird als verbraucht/fehlgeschlagen gespeichert; dafür ist ein neuer Plan erforderlich. Die SQLite-Historie und bisherigen Sperren werden bei Aktualisierung nicht zurückgesetzt. Nach besonders langen Bot-Aufträgen kann eine neue Statusabfrage zur Ergebniszustellung nötig sein; sie wiederholt die Installation nicht.

## Aktivierung auf der bestehenden Installation

```bash
sudo python3 tools/install_packages.py
```

Der Installer prüft die installierten Quelldateien, offene Aufträge und Sicherungen, führt isolierte Tests aus und aktualisiert Host-Paketdienst, Konfigurationsdienst sowie Telegram-, Discord- und Web-Image. Eine lesende APT-Probe prüft einen bisher nicht freigegebenen Paketnamen. Es wird kein Testpaket installiert, keine Zugangsdaten verändert und kein Paketauftrag automatisch bestätigt.

Der Wechsel startet die Chat-Container kurz neu; offene neue Aktionen deshalb vorher abschließen. Ein Fehler stellt vorherige Code-Dateien und Images wieder her, niemals ältere Ausführungshistorie. Native Windows-Installationsaktionen sind weiterhin nicht enthalten; die allgemeine Paketinstallation ist eine Funktion des Linux/APT-Host-Adapters.
