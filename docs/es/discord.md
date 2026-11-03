# Discord: bot, token e IDs

Ajustes y conexiones · 1.5.0.0

1. Crea tu aplicación en Developer Portal. Genera o restablece el token en Bot e introdúcelo en Ajustes → Discord. Application ID está en General Information. Public Key y Client Secret no son el token del bot.

2. Activa Developer Mode en Ajustes de usuario → Avanzado. Haz clic derecho sobre usuario, servidor y canal privado para copiar sus IDs. Introduce los cuatro IDs y el token en sus campos.

3. Invita el bot con scopes bot y applications.commands. Concede solo permisos necesarios del canal, sin Administrador. No necesita intents privilegiados. Prueba /status en el canal permitido; se rechazan mensajes privados y otros usuarios/canales.

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Encontrar IDs de Discord](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID)
- [Guía para desarrolladores de Discord](https://docs.discord.com/developers/quick-start/getting-started)
