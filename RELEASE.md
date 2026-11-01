# Release — 1.3.0.1

The repository is the source distribution. Start with [COMPOSE.md](COMPOSE.md). Never distribute a live host export, `/etc/kiagent-docker`, Docker volumes, SSH keys, auth files, databases, logs or backup archives. Users supply their own service credentials.

## Source verification

```bash
python3 -B tools/release_check.py
python3 -B -m unittest discover -s tests -v
sudo python3 tools/test_docker.py
sudo python3 tools/test_portable.py
```

GitHub Actions runs the isolated builds and tests using fixture credentials. It also checks the version and localized manual. The source check is not a guarantee that every possible secret format has been detected; review the complete Git history before changing repository visibility.

## Product version

`src/app/release_version.py` is the application value. Future stable source releases must include `installer-manifest.json` with kind `server-control-first-install`, protocol `1`, and the exact application version. The default first installer resolves GitHub’s latest non-draft, non-prerelease release and pins its tag to a commit before download; an unreachable or incompatible latest release never falls back to baked source. `VERSION`, the OCI version labels and generated manual must agree. Versions use four numeric components as requested, starting at **1.0.0.0**. No automatic increments or update execution are provided.

## Manual

The authenticated portal includes **Settings → Documentation**. Repository copies are in [Deutsch](docs/de/README.md), [English](docs/en/README.md), [Español](docs/es/README.md) and [Français](docs/fr/README.md). Edit `src/app/user_docs.py`, then run `python3 tools/export_docs.py`; CI rejects stale exports.

## Before publishing

- Selected logo: C, connected server links. The SVG uses the active accent and the wordmark uses the selected language; verify final layout on the deployed UI.
- Complete the isolated full and portable Docker tests for the final commit.
- Review source and Git history for credentials and deployment-specific data.
- Choose distribution/license terms before granting third parties reuse rights. No open-source license is assumed or silently assigned by this preparation.
- Confirm the supported-platform limitations in README and DISTRIBUTION.
- Create the intended GitHub release/tag only from that final verified commit, using the changelog as release notes.

The public release is published from a verified commit as tag `v1.3.0.1`. Images are built locally from source; no container registry publishing is implied. The running managed server is independent of the publication step.
