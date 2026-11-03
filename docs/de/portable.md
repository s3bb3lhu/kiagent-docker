# Docker unter Linux & Windows

Installation & Einstieg · 1.5.0.0

1. Die portable Variante benötigt Linux-Container. Unter Windows Server ist eine Linux-VM mit Docker Engine erforderlich; native Windows-Container und Windows-Hostaktionen sind nicht implementiert. Ein Windows-PC benötigt eine vom Hersteller unterstützte Linux-Container-Umgebung.

2. Im Projektverzeichnis den untenstehenden Compose-Befehl ausführen. Auf demselben Rechner http://127.0.0.1:8787/setup öffnen und Passwort anlegen. Das Volume portal-state enthält private Konfiguration und darf nicht weitergegeben werden.

3. Ohne Host-Adapter speichert diese Variante nur Einstellungen: keine laufenden Bots, keine Servermesswerte und keine Installations- oder Reparaturaktionen. Deaktivierte Schaltflächen sind hier beabsichtigt.

```text
docker compose -f compose.portable.yaml up -d --build --wait
```

- [Docker Desktop](https://docs.docker.com/desktop/)
