# Changelog

## 1.2.0.0 — 2026-11-01

- Bootstrap only the protected web UI without requesting provider keys, bot tokens, allowlist IDs or passwords in the terminal.
- Add a combined authenticated browser setup wizard for Telegram, Discord, OpenAI, Healthchecks and monitoring.
- Keep bot containers, host agents and web actions gated across restarts until validated browser activation.
- Validate required tokens even when kept empty; roll back failed first activation without restoring action history.
- Add an actual fresh web-only CI installation, checking password setup, empty provider files and blocked agents/actions.

## 1.1.0.0 — 2026-11-01

- Add an explicitly privileged, one-shot Compose installer for fixed Linux host agents and the full Telegram/Discord/web stack. No privileged runtime web or bot containers.
- Refuse existing deployments, unsupported hosts, UID remapping and occupied ports before fresh installation.
- Add trusted HTTPS access by public IPv4 and configurable port, default 8443; preserve port in Host/Origin checks and password reset.
- Provide guarded network-only resume after a completed base installation.
- Support local backups on non-RAID hosts while keeping required RAID files mandatory when RAID devices are configured.
- Test bootstrap boundaries, custom HTTPS configuration and read-only host-namespace preflight; document the separate real-credential installation acceptance test.

## 1.0.0.1 — 2026-11-01

- Quote tmpfs mount options in both portable Compose files so YAML preserves them as a single absolute mount specification.
- Fix startup failure: `invalid mount path: mode=1777`.
- Smoke-test actual Compose startup, first setup and restart for both portable files with isolated temporary networks/volumes.
- Keep application version, image labels, quickstart instructions and all four localized manuals consistent.
- Preserve the original v1.0.0.0 tag; new installations should use v1.0.0.1.

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
