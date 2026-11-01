# Telegram: token e ID de usuario

Ajustes y conexiones · 1.1.0.0

1. Abre BotFather desde el enlace oficial. Usa /newbot para crear un bot o /mybots para elegir uno existente y gestionar el token. Introdúcelo solo en el instalador o en Ajustes → Telegram.

2. Introduce el ID numérico personal de Telegram en la lista permitida, no el @usuario. Corresponde a user.id o from.id de tu actualización privada. En una instalación nueva el administrador puede obtenerlo con la Bot API antes del polling; no uses getUpdates en paralelo al bot activo.

3. Inicia el bot en un chat privado y prueba /status. Solo se aceptan usuarios autorizados en privado. Dejar vacío el campo conserva el token. Si se filtra, reemplázalo en BotFather y actualízalo aquí.

- [BotFather](https://t.me/BotFather)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Guía de Telegram](https://core.telegram.org/bots/tutorial)
