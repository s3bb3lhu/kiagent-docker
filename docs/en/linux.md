# Full Linux installation

Installation and first steps · 1.5.0.0

1. The full installation is tested on Ubuntu 26.04 amd64 with systemd, mdadm, Docker Engine and Compose. The host adapter does not support rootless Docker or UID remapping. Check existing RAID and alert configuration first.

2. First install using the helper on main: docker compose up -d. The application always comes from the latest published stable GitHub release, with no prereleases or fallback to an old local payload. Version and commit are recorded in .installation/version.json. The privileged setup container discovers addresses and certificates, reuses a valid IP certificate or issues one on a free host. The HTTPS URL is saved to .installation/WEBADRESSE.txt and setup logs when ready; Docker -d hides later output. Enter passwords and provider settings only in the browser. Repeated starts of the same installation are not updates; other installations are never overwritten. Supports Ubuntu 24.04/26.04 amd64 with systemd and Docker. Use the same internet connection for browser and SSH. See the first-install guide.

3. Clone the repository and run docker compose up -d in its directory. Web addresses are saved under .installation. Set username and password in the browser, without a setup token. Add bot IDs and API keys later on the page, never in chat.

4. The first installer neither takes over unrelated projects nor automatically updates existing installations. Web containers stay unprivileged; fixed host agents run outside them. SSH and RAID members are preserved. Test bots after configuring them.

```text
docker compose up -d
```

```text
docker compose up -d
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Full installation with Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/main/FIRST_INSTALL.md)
