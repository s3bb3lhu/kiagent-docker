# Telegram: Token & Benutzer-ID

Einstellungen & Verbindungen · 1.2.0.0

1. BotFather über den offiziellen Link öffnen. Mit /newbot einen Bot erstellen oder mit /mybots einen bestehenden auswählen und dessen API-Token verwalten. Token ausschließlich im eigenen Installationsdialog oder unter Einstellungen → Telegram eingeben.

2. Die numerische persönliche Telegram-ID in die Zugriffsliste eintragen, nicht den @Benutzernamen. Die ID entspricht dem user.id beziehungsweise from.id eines eigenen privaten Bot-Updates. Bei einer frischen Installation kann der Administrator diese über die Bot API vor Start des Pollings feststellen; getUpdates nicht parallel zum laufenden Bot abfragen.

3. Bot im privaten Chat starten, dann /status prüfen. Nur freigegebene Benutzer in privaten Chats werden akzeptiert. Ein leeres Token-Feld behält den gespeicherten Wert. Ein offengelegtes Token bei BotFather ersetzen und anschließend hier aktualisieren.

- [BotFather](https://t.me/BotFather)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Telegram-Anleitung](https://core.telegram.org/bots/tutorial)
