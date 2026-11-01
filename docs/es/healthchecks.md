# Healthchecks: señales y alertas

Ajustes y conexiones · 1.0.0.1

1. Crea checks separados para servidor y bot en Healthchecks. Copia sus URLs de ping UUID y asígnalas en Ajustes → Healthchecks. Se necesitan URLs de ping, no una clave API de gestión.

2. Configura destinatarios o integraciones en Healthchecks. Ajusta período y tolerancia al intervalo real. Una prueba controlada debe verificar tanto la caída del check como la recepción del aviso.

3. Ambos campos son opcionales. Trata las URLs como contraseñas y no las copies al repositorio. La falta de señales no es un diagnóstico completo de discos ni aplicaciones.

- [Gestionar Healthchecks](https://healthchecks.io/checks/)
- [Documentación de Healthchecks](https://healthchecks.io/docs/)
