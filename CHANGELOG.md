# Changelog

## 1.0.0.0 — 2026-11-01

First release of the self-hosted Server Control dashboard and the existing Kiagent host adapters.

- Release quickstart Compose file and separate full Linux deployment guide.
- Authenticated dashboard with Status, Control, a read-only SSH Console and Settings.
- Ruby Control and Crimson Glass, five accent colors, light/dark mode and collapsible navigation.
- German, English, Spanish and French user interface and categorized documentation.
- Host CPU including every logical core, RAM, disks, network, assigned addresses and server clock.
- Separate Telegram, Discord, OpenAI, Healthchecks and monitoring settings; browser password management.
- Explicitly confirmed APT installations with pinned plans, SQLite audit and uncertain-result lockout.
- Limited RAID-monitor repair and persistent rate-limited automation with Telegram notifications.
- Local backups, isolated restore checks and optional external heartbeats.

Scope: the full host adapter targets the tested Ubuntu 26.04 amd64 setup. The portable Linux-container portal also runs in suitable Linux environments on Windows, but has no native Windows host actions and does not run the bots by itself. The console is not an interactive shell. Backups stored on the same RAID are not off-server protection.

Brand C (connected server links) is selected and implemented with a localized wordmark and automatic theme accents.
