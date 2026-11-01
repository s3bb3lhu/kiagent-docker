# Acceso, contraseña y HTTPS

Ajustes y conexiones · 1.1.0.0

1. Abre /setup al configurar por primera vez. No hay contraseña predeterminada ni código. Usa al menos 8 caracteres con mayúscula, número y símbolo, sin espacios. La configuración inicial por HTTPS público se limita a la IP del administrador.

2. Ajustes → Cambiar contraseña requiere la contraseña actual. El cambio invalida las sesiones. Si la olvidas, hace falta un restablecimiento administrativo mediante el acceso existente al servidor; consulta DISTRIBUTION.md. Permite cookies para este sitio.

3. El puerto 8787 solo es local por defecto. Para acceso remoto usa un túnel SSH normal o el instalador HTTPS con tu IP pública. El despliegue público necesita TCP 443 para nginx y TCP 80 para renovar certificados. No publiques el puerto 8787.

```text
sudo python3 tools/install_https.py --address YOUR_PUBLIC_IP
```

