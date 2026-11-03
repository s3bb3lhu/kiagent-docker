# Docker en Linux y Windows

Instalación y primeros pasos · 1.5.0.0

1. La variante portable necesita contenedores Linux. Windows Server requiere una VM Linux con Docker Engine; no hay contenedores Windows nativos ni acciones sobre Windows. Un PC Windows necesita un entorno de contenedores Linux compatible con el fabricante.

2. Ejecuta el comando Compose de abajo en el proyecto. En ese mismo equipo abre http://127.0.0.1:8787/setup y crea la contraseña. El volumen portal-state contiene configuración privada y no debe distribuirse.

3. Sin adaptador del servidor esta variante solo guarda ajustes: no ejecuta bots, métricas, instalaciones ni reparaciones. Los controles desactivados son intencionados.

```text
docker compose -f compose.portable.yaml up -d --build --wait
```

- [Docker Desktop](https://docs.docker.com/desktop/)
