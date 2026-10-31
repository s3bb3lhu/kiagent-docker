# Full Linux installation

Installation and first steps · 1.0.0.0

1. The full installation is tested on Ubuntu 26.04 amd64 with systemd, mdadm, Docker Engine and Compose. The host adapter does not support rootless Docker or UID remapping. Check existing RAID and alert configuration first.

2. Download the source package or clone the repository. Run sudo python3 tools/install.py in its directory. Enter your own Telegram/Discord identities and tokens in the terminal; OpenAI and Healthchecks are optional. Never put credentials into clone URLs or chats.

3. The installer backs up and migrates a compatible setup. An existing Docker project is not blindly overwritten. Host agents stay outside containers. SSH access and RAID members are unchanged. Afterwards check /status and /automatik_status in both bots.

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
