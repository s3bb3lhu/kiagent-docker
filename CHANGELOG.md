# Changelog

## Erstinstallationsweg auf main — ohne Versions-/Bestandsupdate

- Default `docker compose up -d` performs first installation and saves the HTTPS URL to a local result file and setup logs.
- Certificate discovery now also runs on unused hosts; valid existing certificates are reused, otherwise the clean-host ACME flow issues one.
- Durable local ownership prevents updates or replacement of existing installations; repeat starts use installed code.
- Keep application version and release tags unchanged. Add isolated plain-Compose integration coverage.


## 1.3.0.1 — 2026-11-01

- Normalize the host working directory after namespace entry and explicitly set the project directory for parallel HTTPS Compose commands.
- Add a real TLS integration regression test starting from a deleted inherited working directory.
- Document in-place continuation of a 1.3.0.0 setup without reinstalling or modifying existing services.


## 1.3.0.0 — 2026-11-01

- Add isolated HTTPS co-location on an automatically selected free port from 9443, leaving existing proxies, containers and port 8787 unchanged.
- Reuse validated existing IP certificates through root-only copies; synchronize renewals without reloading the original proxy.
- Discover certificate roots from bind-mount metadata without reading container environments.
- Fix application validation of custom HTTPS ports and add actual TLS co-location CI coverage.


## 1.2.0.1 — 2026-11-01

- Remove terminal IP and certificate confirmation prompts from the standard Compose installer.
- Discover the server and bootstrap administrator address from SSH metadata, with a unique host-login fallback for sudo.
- Fail closed for ambiguous logins or unsupported NAT/multiple-address hosts; never expose unrestricted first setup.
- Print the HTTPS setup URL after installation; retain browser-only password and provider configuration.


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
