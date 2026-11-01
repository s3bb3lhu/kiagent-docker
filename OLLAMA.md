# Ollama als lokaler KI-Anbieter

Ollama ergänzt OpenAI für Telegram, Discord, Installationsberatung und Diagnose. KI-Ausgaben werden weiterhin niemals direkt als Shellbefehle ausgeführt. Paketpläne und Reparaturen behalten ihre bestehenden Prüfungen, Bestätigungen, Sperrzeiten und Protokolle.

## Automatische Prüfung bei Docker-Installationen

Der Standardweg `docker compose up -d` prüft Ollama bei der Erstinstallation und bei jedem erneuten Start derselben Installation. Auch der explizite vollständige Installer prüft es. Ein vorhandenes Ollama wird anhand der Standard-API, des Dienstes/Binaries oder eines Docker-Containers erkannt. Container ohne öffentlichen Port können über ihre interne Docker-Adresse genutzt werden. Ungewöhnliche Installationen, verschlüsselte oder authentifizierte Sonder-APIs müssen administrativ geprüft werden.

**Vorhandenes Ollama wird nicht verändert:** kein Start oder Neustart, kein Update, keine Modellinstallation, kein Löschen und keine Änderung seiner Konfiguration, CPU-/RAM-Limits oder Ports. Eine gestoppte Instanz bleibt gestoppt. Es werden nur vorhandene lokale Textmodelle angeboten; Cloud- und Embedding-Modelle werden nicht automatisch ausgewählt. Fehlt ein nutzbares Modell, zeigt die Oberfläche das an. Das Modell muss dann vom Betreiber in der vorhandenen Instanz eingerichtet werden.

Eine eigene kleine Vermittlung verbindet die Bots über einen authentifizierten Unix-Socket mit Ollama. Sie läuft ohne Rootrechte, hält höchstens eine Generierung gleichzeitig offen und beschränkt die eigenen Anfragen auf 2048 Kontext- und maximal 512 Ausgabetokens. Bestehende Server behalten ihre eigenen globalen Limits; diese können ohne eine Konfigurationsänderung nicht nachträglich von uns erzwungen werden. Bei vorhandenen Instanzen werden auch keine `keep_alive`- oder Thread-Einstellungen gesetzt.

## Nur bei einer neuen Instanz

Der Installer richtet einen separaten Container `server-control-ollama` mit dem offiziellen Ollama-Image ein. Der bei der Installation aufgelöste Image-Digest wird protokolliert. Es gibt keine GPU-Freigabe und keine öffentliche API: nur `127.0.0.1:11434` wird gebunden.

- CPU: höchstens 25 % der verfügbaren CPU-Kapazität, maximal zwei Kerne, niedrige relative CPU-Priorität.
- RAM: maximal ein Viertel des Gesamtspeichers und maximal 4096 MiB; zusätzlich höchstens die Hälfte des aktuell verfügbaren RAM und mindestens 2048 MiB Reserve. Erkannte cgroup-Grenzen werden berücksichtigt. Kein zusätzlicher Swap für den Container.
- Modell: `qwen3:0.6b` bei kleinerem Budget, `qwen3:1.7b` ab 3072 MiB Containerbudget. Es wird kein großes Modell automatisch gewählt.
- Ein geladenes Modell, eine parallele Anfrage, höchstens zwei serverinterne Warteschlangenplätze, Kontext 2048. Die Ausgabelänge wird auf schwächeren CPUs zusätzlich reduziert.
- Nach 30 Sekunden ohne Nutzung darf das Modell entladen werden. Anfragen haben ein festes Zeitlimit; es gibt keine Hintergrund-Generierung.
- Bei zu wenig RAM, weniger als einem verfügbaren CPU-Kern oder weniger als 20 GiB freiem Platz wird die automatische Modellinstallation ausgelassen und der Grund angezeigt. Nach dem Image-Download wird der verbleibende Platz erneut geprüft. Die Anwendung bleibt mit OpenAI nutzbar.

Diese Limits gelten ausschließlich für die neu angelegte Instanz. Bei späteren Prüfungen werden sie nicht neu skaliert oder auf vorhandene Instanzen übertragen. Modellgewichte bleiben unter `/var/lib/kiagent-ollama`; vorhandene Verzeichnisse werden nicht ungeprüft übernommen. Fehlgeschlagene Erst-Downloads werden nicht durch einen späteren ungefragten Modell-Download auf einer inzwischen vorhandenen Instanz wiederholt.

## Im Browser

Unter **Einstellungen → KI-Anbieter** stehen Ollama und OpenAI zur Auswahl. Die Seite zeigt Modellverfügbarkeit, Betriebsart und gegebenenfalls die selbst gesetzten Ressourcenlimits. Ollama benötigt keinen API-Key. OpenAI verwendet weiterhin den unter Einstellungen → OpenAI hinterlegten Schlüssel.

Anfragen an Ollama werden auf dem Server verarbeitet. Bei OpenAI werden Anfrage und feste Statusmesswerte an OpenAI übertragen. Es gibt **keinen automatischen Anbieterwechsel** bei Fehlern und keinen stillen externen Ersatz für eine ausgefallene lokale KI. Status-, Reparatur- und Paketbefehle bleiben unabhängig von KI verfügbar.

## Bestehende Server ausdrücklich aktivieren

Für geprüfte Docker-Installationen 1.3.0.0/1.3.0.1 gibt es einen einmaligen Aktivierungsschritt. Er prüft vorhandene Dateien und offene Aufträge, erstellt ein privates Backup und baut zuerst das neue Image. Erst anschließend werden die zuvor laufenden Web-/Bot-Container umgestellt. Die Host-Reparatur- und Paket-Agenten, SQLite-Historie, Sperrzeiten, Tokens, Authentifizierung und HTTPS-Ports werden nicht ersetzt. Nur die eigene KI-Anbindung wird ergänzt. Bei einer nicht bestätigten Rücksetzung bleibt eine Wartungssperre zur manuellen Prüfung stehen.

```bash
git clone --branch v1.4.0.0 --depth 1 https://github.com/s3bb3lhu/kiagent-docker.git kiagent-ollama-1.4.0.0
cd kiagent-ollama-1.4.0.0
sudo python3 tools/activate_ollama.py
```

Nicht statt einer vorhandenen Installation nochmals den Erstinstaller ausführen. Nach Erfolg die Seite neu laden und die Modellverfügbarkeit prüfen. Bei eigener Anpassung oder abweichendem Host-Dienstcode wird ohne automatische Übernahme abgebrochen. Neue Ollama-Komponenten können nach einer fehlgeschlagenen Frontend-Aktivierung begrenzt installiert bleiben; vorhandene Ollama-Instanzen werden auch bei einer Rücksetzung nicht gestoppt oder verändert.

## Quellen

- [Offizielles Docker-Image und CPU-Betrieb](https://docs.ollama.com/docker)
- [Parallelität, Kontext und Speicherhaltezeit](https://docs.ollama.com/faq)
- [Chat-API und strukturierte Antworten](https://docs.ollama.com/api/chat)
- [Qwen3-Modellgrößen](https://ollama.com/library/qwen3)
