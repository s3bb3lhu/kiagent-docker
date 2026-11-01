# Updates, version and troubleshooting

Operation and maintenance · 1.3.0.1

1. The product version appears at the bottom of the menu. The current release is version 1.3.0.1. Updates are explicitly installed from reviewed source; there is no unattended self-update. Check open/uncertain jobs and backups first.

2. On an existing managed installation run tools/install_ui.py from the prepared source with sudo. It tests in isolation, backs up code/images and checks restart. Credentials, password, history and lock times are preserved. Afterwards reload the browser with Ctrl+F5.

3. For 502 or a silent bot first read service states, container health and the saved installation report over SSH. For AI errors check OpenAI configuration/project access; /status and /ki_install remain independent of AI. For cookie errors reopen sign-in and allow cookies.

4. Do not paste tokens or unsanitized journals into public issues. Uncertain actions are never retried automatically. If you customized the installation, compare installed files with the project before upgrading.

```text
systemctl is-active kiagent-config kiagent-docker kiagent-executor kiagent-packages
```

```text
sudo python3 tools/install_ui.py
```

