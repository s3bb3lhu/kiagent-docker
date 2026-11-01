# Actualizaciones, versión y solución de problemas

Operación y mantenimiento · 1.0.0.0

1. La versión aparece abajo en el menú. Esta primera publicación tiene la versión 1.0.0.0. Las actualizaciones se instalan explícitamente desde código revisado; no hay autoactualización desatendida. Revisa tareas abiertas/inciertas y respaldos antes.

2. En una instalación administrada existente ejecuta tools/install_ui.py desde el código preparado con sudo. Prueba aisladamente, respalda código/imágenes y comprueba reinicio. Conserva credenciales, contraseña, historial y bloqueos. Recarga con Ctrl+F5.

3. Ante 502 o un bot silencioso consulta estados, salud de contenedores e informe guardado por SSH. Para errores de IA revisa OpenAI y acceso al proyecto; /status y /ki_install no dependen de IA. Ante errores de cookies reabre acceso y permítelas.

4. No pegues tokens ni registros sin limpiar en incidencias públicas. Las acciones inciertas no se repiten automáticamente. Si personalizaste la instalación compara archivos con el proyecto antes de actualizar.

```text
systemctl is-active kiagent-config kiagent-docker kiagent-executor kiagent-packages
```

```text
sudo python3 tools/install_ui.py
```

