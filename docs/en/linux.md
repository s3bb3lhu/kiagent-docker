# Full Linux installation

Installation and first steps · 1.2.0.1

1. The full installation is tested on Ubuntu 26.04 amd64 with systemd, mdadm, Docker Engine and Compose. The host adapter does not support rootless Docker or UID remapping. Check existing RAID and alert configuration first.

2. New: use docker compose -f compose.install.yaml run --rm --build installer for interactive full installation and startup. This explicitly privileged one-shot installer sets up fixed host agents and is then removed. Fresh Ubuntu 24.04/26.04 amd64 hosts are checked; existing installations are not overwritten. After the web starts, set your password and enter service IDs/tokens at /settings/setup. The web address is printed after automatic IP discovery; there are no terminal questions. Use the same internet connection for SSH and your browser; bots and actions remain locked until validation succeeds. Default access is https://SERVER-IP:8443; TCP 80 and the chosen web port must be reachable. See the linked full-installation guide.

3. Download the source package or clone the repository. Run sudo python3 tools/install.py in its directory. Enter your own Telegram/Discord identities and tokens in the terminal; OpenAI and Healthchecks are optional. Never put credentials into clone URLs or chats.

4. The installer backs up and migrates a compatible setup. An existing Docker project is not blindly overwritten. Host agents stay outside containers. SSH access and RAID members are unchanged. Afterwards check /status and /automatik_status in both bots.

```text
docker compose -f compose.install.yaml run --rm --build installer
```

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Full installation with Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/v1.2.0.1/FULL_COMPOSE.md)
