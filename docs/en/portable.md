# Docker on Linux and Windows

Installation and first steps · 1.1.0.0

1. The portable variant needs Linux containers. Windows Server requires a Linux VM with Docker Engine; native Windows containers and Windows host actions are not implemented. A Windows PC needs a vendor-supported Linux-container environment.

2. Run the Compose command below in the project directory. On that same machine open http://127.0.0.1:8787/setup and set a password. The portal-state volume contains private configuration and must not be distributed.

3. Without a host adapter this variant only stores settings: no running bots, server metrics, installations or repairs. Disabled controls are intentional.

```text
docker compose -f compose.portable.yaml up -d --build --wait
```

- [Docker Desktop](https://docs.docker.com/desktop/)
