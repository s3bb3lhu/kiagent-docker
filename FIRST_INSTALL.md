# Erstinstallation mit einem Compose-Befehl

Dieser Weg ist eine neue **Erstinstallation**, kein Update. Neuinstallationen verwenden immer den neuesten veröffentlichten stabilen GitHub-Release. Bestehende Installationen bleiben unverändert. Bereits veröffentlichte Release-Tags und laufende Installationen werden nicht geändert. Die folgende Standard-Compose liegt auf dem aktuellen `main`-Zweig.

## Start

Voraussetzungen: frisches Ubuntu 24.04/26.04 amd64 mit systemd, regulärem Docker Engine und Compose. Rootless-Docker, UID-Remapping und native Windows-Hosts werden nicht unterstützt. Unter Windows Server eine passende Linux-VM verwenden. Fehlendes Python/OpenSSL wird nur auf einem bisher nicht eingerichteten unterstützten Host nachinstalliert. Es erfolgt kein allgemeines System-Upgrade.

Über eine direkte SSH-Verbindung ausführen; Browser und SSH sollen denselben Internetzugang verwenden:

```bash
git clone https://github.com/s3bb3lhu/kiagent-docker.git
cd kiagent-docker
docker compose up -d
```

Bei fehlenden Docker-Berechtigungen den letzten Befehl mit `sudo` ausführen. Es werden keine IP-Adressen, Passwörter, API-Keys oder Tokens abgefragt. Server- und Administrator-Adresse werden automatisch erkannt. Bei uneindeutiger SSH-Zuordnung oder nicht unterstütztem NAT wird geschützt abgebrochen.

## Immer der aktuelle stabile Release

Der heruntergeladene `main`-Stand enthält den Installationshelfer. Die zu installierende Anwendung wird erst beim Start einer **neuen** Installation über GitHubs `releases/latest` ermittelt. Entwurfs- und Vorabversionen werden abgewiesen. Der Release-Tag wird zu einem konkreten Commit aufgelöst und genau dessen Quellarchiv heruntergeladen; Versionsnummer, Installationsprotokoll und Archivstruktur werden geprüft.

Damit bestimmt weder ein alter Checkout noch das lokal zwischengespeicherte Installer-Image die Anwendungsversion. Es gibt keinen stillen Rückfall auf den mitgelieferten alten Programmstand. Sind GitHub oder der aktuelle passende Stable-Release nicht abrufbar, wird vor der Hostinstallation abgebrochen. Nach erfolgreicher Installation stehen Version, Tag und Commit zusätzlich in **`.installation/version.json`** sowie im installierten `release-source.json`.

Der bereits veröffentlichte Release 1.3.0.1 liegt vor Einführung dieses Erstinstallationsprotokolls. Für genau dessen unveränderlichen Commit passt der Starter drei Installationshelfer an und ergänzt die Laufzeitvorlage. Die Anwendungsdateien und Abhängigkeiten bleiben aus dem stabilen Release; die angepassten Helfer werden mit Prüfsummen protokolliert. Andere alte oder unbekannte Releases werden nicht ungeprüft angepasst. Künftige Releases liefern `installer-manifest.json` mit Protokoll 1 und passender Version selbst mit.

Eine gestartete oder teilweise eingerichtete Installation bleibt an ihren ausgewählten Stand gebunden. Wiederanlauf oder Fortsetzung führt kein Versionsupdate aus; eine neuere Stable-Veröffentlichung ersetzt keine bereits installierten Dateien.

## Webadresse und Einrichtung

`-d` bedeutet Hintergrundbetrieb: Docker zeigt beim Start nur den Containerstatus, keine späteren Anwendungsausgaben. Der Installer schreibt die fertige HTTPS-Adresse automatisch nach **`.installation/WEBADRESSE.txt`** und in sein Container-Protokoll. Optional im Terminal ansehen:

```bash
docker compose logs -f setup
```

Der Zustand steht zusätzlich in `.installation/status.json` (`installing`, `ready` oder `failed`). Erst bei `ready` ist die URL freigegeben. Die Installation kann mehrere Minuten dauern. Der beendete Setup-Container mit Exitcode 0 ist normal.

Auf der ausgegebenen Seite zuerst das Administrator-Passwort erstellen. Danach Telegram-/Discord-IDs und Tokens eintragen, bei Bedarf OpenAI und Healthchecks ergänzen und **Prüfen und aktivieren** wählen. Bis zur erfolgreichen Prüfung bleiben Bots und Host-Aktionen gesperrt. Es gibt kein Standardpasswort und keinen Einrichtungscode.

## SSL/TLS-Zertifikate

Vor der Einrichtung wird nach einem gültigen IP-Zertifikat gesucht: in `/etc/letsencrypt` sowie in Ordnern, die laufende Container dort eingebunden haben. IP-Zuordnung, Vertrauenskette, Gültigkeit, Schlüssel und Pfadschutz werden geprüft. Ein geeignetes Zertifikat wird über eigene rootgeschützte Kopien übernommen. Bestehende Zertifikatsdateien und Webserver bleiben unverändert; ein eigener Timer übernimmt Erneuerungen.

Fehlt ein geeignetes Zertifikat auf einem freien Host, richtet der Installer nginx und ein Let's-Encrypt-IP-Zertifikat automatisch ein und prüft die Erneuerung. Dabei gelten die [Let's-Encrypt-Nutzungsbedingungen](https://letsencrypt.org/repository/). **TCP 80** muss für Ausstellung und Erneuerung erreichbar bleiben. Es wird kein selbst signiertes Zertifikat als Ersatz veröffentlicht.

Bei vorhandenen Diensten wird ein eigener freier HTTPS-Port ab 9443 gewählt; andernfalls standardmäßig 8443. Der ausgegebene Port muss in der Cloud-Firewall erreichbar sein. Die Firewall wird nicht automatisch geändert. Ein fremder Webserver auf Port 80 ohne geeignetes vorhandenes IP-Zertifikat verhindert die automatische Ausstellung: Der Installer bricht vor der Hostinstallation ab, statt fremde Konfigurationen umzuschreiben.

## Wiederholter Start ist kein Update

Die versteckte `.installation`-Mappe gehört zu genau dieser Installation. Sie enthält eine interne Zuordnung, keine Provider-Tokens. Aufbewahren, nicht in Git aufnehmen oder als Distribution weitergeben.

Ein erneutes `docker compose up -d` aus demselben Ordner startet die zugeordnete Installation, kopiert aber keinen neuen Quellstand und ändert weder Zugangsdaten noch Reparaturhistorie. Ein nur fehlgeschlagener HTTPS-Schritt wird mit dem bereits installierten Quellstand fortgesetzt. Andere beziehungsweise ältere Installationen ohne passende Zuordnung werden nicht übernommen oder aktualisiert. Eine unvollständige Grundeinrichtung erfordert manuelle Prüfung.

Nach Serverneustarts starten die eingerichteten Host-Dienste den Web-/Bot-Stack. Die Standard-Compose verwaltet nur den einmaligen Setup-Container. `docker compose down` entfernt diesen Container, deinstalliert aber nicht die Host-Agenten und beendet nicht den separat verwalteten Laufzeit-Stack. Für dessen Bedienung siehe [FULL_COMPOSE.md](FULL_COMPOSE.md).

## Berechtigungen

Der einmalige Setup-Container benötigt wie bisher privilegierten Hostzugriff, den Host-PID-Namensraum und den Mount `/` nach `/host`. Er beendet sich nach der Einrichtung und hat keine Neustartregel. Im Gegensatz zu `run --rm` bleibt bei `up -d` der beendete Setup-Container samt Protokoll sichtbar. Die laufenden Web-/Bot-Container erhalten diese Rechte und keinen Docker-Socket.

Die Standarddatei im Download ist `compose.yaml`; die vorbereitete Laufzeitvorlage heißt `compose.runtime.yaml`. Der Installer legt die Laufzeitdatei auf dem Host weiter unter `/opt/kiagent-docker/project/compose.yaml` ab. Damit bleiben die bestehenden Host-Werkzeuge kompatibel. Bestehende Installationen werden durch diese neue Standarddatei nicht umgestellt.
