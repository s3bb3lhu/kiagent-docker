# Instalación completa en Linux

Instalación y primeros pasos · 1.0.0.0

1. La instalación completa está probada en Ubuntu 26.04 amd64 con systemd, mdadm, Docker Engine y Compose. El adaptador no admite Docker rootless ni reasignación de UID. Revisa primero RAID y las alertas existentes.

2. Descarga el código o clona el repositorio. Ejecuta sudo python3 tools/install.py en su directorio. Introduce tus identidades y tokens de Telegram/Discord en la terminal; OpenAI y Healthchecks son opcionales. No pongas credenciales en URLs de clonación ni chats.

3. El instalador respalda y migra una configuración compatible. No sobrescribe a ciegas un proyecto Docker existente. Los agentes permanecen fuera de los contenedores. No modifica SSH ni miembros RAID. Después comprueba /status y /automatik_status en ambos bots.

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
