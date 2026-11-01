# Full Linux installation

Installation and first steps · 1.3.0.1

1. The full installation is tested on Ubuntu 26.04 amd64 with systemd, mdadm, Docker Engine and Compose. The host adapter does not support rootless Docker or UID remapping. Check existing RAID and alert configuration first.

2. First install on current main: docker compose up -d. The privileged setup container discovers addresses and certificates, reuses a valid IP certificate or issues one on a free host. The HTTPS URL is saved to .installation/WEBADRESSE.txt and setup logs when ready; Docker -d hides later output. Enter passwords and provider settings only in the browser. Repeated starts of the same installation are not updates; other installations are never overwritten. Supports Ubuntu 24.04/26.04 amd64 with systemd and Docker. Use the same internet connection for browser and SSH. See the first-install guide.

3. Download the source package or clone the repository. Run sudo python3 tools/install.py in its directory. Enter your own Telegram/Discord identities and tokens in the terminal; OpenAI and Healthchecks are optional. Never put credentials into clone URLs or chats.

4. The installer backs up and migrates a compatible setup. An existing Docker project is not blindly overwritten. Host agents stay outside containers. SSH access and RAID members are unchanged. Afterwards check /status and /automatik_status in both bots.

```text
docker compose up -d
```

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Full installation with Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/main/FIRST_INSTALL.md)
