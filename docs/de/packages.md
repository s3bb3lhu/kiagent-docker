# KI & Paketinstallationen

Funktionen & Steuerung · 1.0.0.0

1. /ki Installiere nginx erkennt einen Installationswunsch und bereitet einen APT-Plan vor. /ki_install nginx fordert den Plan ohne KI an. Auf der Steuerungsseite einen konkreten Paketnamen eingeben. Alle gültigen Pakete aus den eingerichteten APT-Quellen sind zugelassen; keine URLs, lokalen .deb-Dateien oder Shelloptionen.

2. Zielpaket und alle Abhängigkeiten samt Versionen prüfen, dann separat bestätigen. Freigaben sind einmalig, identitäts- und nachrichtengebunden und zwei Minuten gültig. Ein geänderter Plan wird abgewiesen. Bereits installierte Zielpakete werden nicht erneut installiert.

3. Installiert wird auf dem Linux-Host im Hintergrund. Abhängigkeiten dürfen gemäß Plan aktualisiert werden; Paket-Skripte können Dienste neu starten. Entfernen und Herabstufen sind nicht freigegeben. /ki_install_status zeigt den letzten Auftrag. Unklare Ergebnisse niemals blind wiederholen, sondern per SSH prüfen.

