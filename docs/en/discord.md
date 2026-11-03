# Discord: bot, token and IDs

Settings and connections · 1.5.0.0

1. Create your own application in the Developer Portal. Generate or reset the bot token under Bot and enter it directly in Settings → Discord. Find Application ID under General Information. Public Key and Client Secret are not the bot token.

2. Enable Developer Mode in Discord User Settings → Advanced. Right-click the user, server and private text channel to copy their IDs. Enter all four IDs and the token into the corresponding fields.

3. Invite the bot to your server with bot and applications.commands scopes. Grant only required channel permissions, not Administrator. Privileged intents are not needed. Test /status in the allowed channel; DMs and other users/channels are rejected.

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Find Discord IDs](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID)
- [Discord developer guide](https://docs.discord.com/developers/quick-start/getting-started)
