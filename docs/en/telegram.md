# Telegram: token and user ID

Settings and connections · 1.2.0.0

1. Open BotFather through the official link. Use /newbot to create a bot or /mybots to select an existing one and manage its API token. Enter the token only in your installer or Settings → Telegram.

2. Enter the numeric personal Telegram ID in the allowlist, not the @username. It is the user.id or from.id of your own private bot update. For a fresh installation an administrator can obtain it using the Bot API before polling starts; do not run getUpdates alongside the live bot.

3. Start the bot in a private chat, then test /status. Only allowlisted users in private chats are accepted. An empty token field keeps the saved value. Replace a leaked token in BotFather and then update it here.

- [BotFather](https://t.me/BotFather)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Telegram tutorial](https://core.telegram.org/bots/tutorial)
