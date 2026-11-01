# Copias de seguridad y recuperación

Operación y mantenimiento · 1.3.0.0

1. La instalación Linux administrada respalda cada día a las 03:15 Europe/Berlin en /var/backups/kiagent-daily. Contiene credenciales y una copia SQLite coherente, solo legible por root. No borra archivos antiguos automáticamente; vigila el espacio.

2. Las pruebas aisladas verifican archivos y coherencia de base de datos, no un servidor nuevo completo. Las copias en el mismo RAID no protegen ante pérdida total. Planifica copias externas aparte. No publiques archivos, volúmenes ni autenticación.

3. Al recuperar detén servicios de forma controlada, verifica permisos y no restaures historial antiguo sobre un sistema que siguió operando. Podría reutilizar autorizaciones consumidas. La contraseña web queda aparte y no está en el respaldo diario; restablécela administrativamente.

