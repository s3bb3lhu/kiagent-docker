# Discord : bot, token et identifiants

Paramètres et connexions · 1.2.0.1

1. Créez votre application dans le Developer Portal. Générez ou réinitialisez le token dans Bot et saisissez-le dans Paramètres → Discord. Application ID se trouve dans General Information. Public Key et Client Secret ne sont pas le token du bot.

2. Activez Developer Mode dans Paramètres utilisateur → Avancé. Faites un clic droit sur l’utilisateur, le serveur et le salon privé pour copier leurs identifiants. Saisissez les quatre identifiants et le token dans leurs champs.

3. Invitez le bot avec les scopes bot et applications.commands. Accordez seulement les permissions nécessaires du salon, sans Administrateur. Aucun intent privilégié requis. Testez /status dans le salon autorisé ; les messages privés et autres utilisateurs/salons sont refusés.

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Trouver les identifiants Discord](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID)
- [Guide de développement Discord](https://docs.discord.com/developers/quick-start/getting-started)
