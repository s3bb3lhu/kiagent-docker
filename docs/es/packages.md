# IA e instalación de paquetes

Funciones y control · 1.2.0.0

1. /ki Instala nginx reconoce la solicitud y prepara un plan APT. /ki_install nginx lo pide sin IA. En Control introduce un paquete concreto. Se permiten paquetes válidos de repositorios configurados; no URLs, archivos .deb locales ni opciones shell.

2. Revisa el paquete y todas las dependencias con versiones, y confirma aparte. La autorización es de un uso, ligada a identidad/mensaje y válida dos minutos. Se rechazan planes cambiados. No reinstala objetivos ya instalados.

3. La instalación corre en segundo plano en el host Linux. Puede actualizar dependencias según el plan y reiniciar servicios mediante scripts. No permite eliminar ni bajar versiones. /ki_install_status muestra la última tarea. No repitas resultados inciertos; revisa por SSH.

