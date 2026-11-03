# Instalación completa en Linux

Instalación y primeros pasos · 1.5.0.0

1. La instalación completa está probada en Ubuntu 26.04 amd64 con systemd, mdadm, Docker Engine y Compose. El adaptador no admite Docker rootless ni reasignación de UID. Revisa primero RAID y las alertas existentes.

2. Primera instalación con el asistente de main: docker compose up -d. La aplicación se descarga de la última versión estable publicada en GitHub, sin versiones previas ni alternativa local antigua. Versión y commit figuran en .installation/version.json. El contenedor privilegiado detecta direcciones y certificados, reutiliza un certificado IP válido o solicita uno en un servidor libre. La URL HTTPS aparece en .installation/WEBADRESSE.txt y en los registros; -d oculta la salida posterior. Contraseña y accesos se configuran solo en el navegador. Reiniciar la misma instalación no es actualizar; no se sobrescriben otras instalaciones. Ubuntu 24.04/26.04 amd64 con systemd y Docker. Usa la misma conexión para navegador y SSH. Consulta la guía de primera instalación.

3. Clona el repositorio y ejecuta docker compose up -d. Las direcciones quedan en .installation. Crea usuario y contraseña en el navegador, sin token de instalación. Añade después IDs y claves en la página, nunca en el chat.

4. El instalador no adopta proyectos ajenos ni actualiza instalaciones existentes automáticamente. Los contenedores web no son privilegiados; los agentes fijos quedan fuera. Conserva SSH y RAID. Comprueba los bots tras configurarlos.

```text
docker compose up -d
```

```text
docker compose up -d
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Instalación completa con Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/main/FIRST_INSTALL.md)
