# Instalación completa en Linux

Instalación y primeros pasos · 1.3.0.1

1. La instalación completa está probada en Ubuntu 26.04 amd64 con systemd, mdadm, Docker Engine y Compose. El adaptador no admite Docker rootless ni reasignación de UID. Revisa primero RAID y las alertas existentes.

2. Nuevo: usa docker compose -f compose.install.yaml run --rm --build installer para instalación completa e inicio interactivos. Este instalador privilegiado de un solo uso configura los agentes y se elimina al terminar. Comprueba Ubuntu 24.04/26.04 amd64 limpio; no sobrescribe instalaciones existentes. Tras iniciar la web crea tu contraseña e introduce IDs y tokens en /settings/setup. La dirección web se muestra tras detectar las IP automáticamente; no hay preguntas en la terminal. Usa la misma conexión a Internet para SSH y navegador; bots y acciones siguen bloqueados hasta validar. Con otros servicios web se elige un puerto HTTPS libre desde 9443 y un certificado IP existente válido, sin cambiar los otros servicios. Usa la URL indicada. En hosts libres: https://IP-SERVIDOR:8443. TCP 80 y el puerto web elegido deben ser accesibles. Consulta la guía completa enlazada.

3. Descarga el código o clona el repositorio. Ejecuta sudo python3 tools/install.py en su directorio. Introduce tus identidades y tokens de Telegram/Discord en la terminal; OpenAI y Healthchecks son opcionales. No pongas credenciales en URLs de clonación ni chats.

4. El instalador respalda y migra una configuración compatible. No sobrescribe a ciegas un proyecto Docker existente. Los agentes permanecen fuera de los contenedores. No modifica SSH ni miembros RAID. Después comprueba /status y /automatik_status en ambos bots.

```text
docker compose -f compose.install.yaml run --rm --build installer
```

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Instalación completa con Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/v1.3.0.1/FULL_COMPOSE.md)
