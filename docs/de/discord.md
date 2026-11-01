# Discord: Bot, Token & IDs

Einstellungen & Verbindungen · 1.0.0.1

1. Im Developer Portal eine eigene Anwendung erstellen. Unter Bot den Bot-Token erzeugen beziehungsweise zurücksetzen und direkt unter Einstellungen → Discord einfügen. Die Application ID findet sich unter General Information. Public Key und Client Secret sind kein Bot-Token.

2. In Discord unter Benutzereinstellungen → Erweitert den Entwicklermodus einschalten. Benutzer, Server und privaten Textkanal rechts anklicken und die jeweilige ID kopieren. Alle vier IDs und den Token in die zugehörigen Felder eintragen.

3. Bot mit den Scopes bot und applications.commands auf den eigenen Server einladen. Nur die benötigten Kanalrechte vergeben, keine Administratorrechte. Privilegierte Intents werden nicht benötigt. /status im erlaubten Kanal testen; DMs und andere Benutzer/Kanäle werden abgewiesen.

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord-IDs finden](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID)
- [Discord-Entwickleranleitung](https://docs.discord.com/developers/quick-start/getting-started)
