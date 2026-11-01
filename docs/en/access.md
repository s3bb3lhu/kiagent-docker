# Sign-in, password and HTTPS

Settings and connections · 1.3.0.1

1. Open /setup for first setup. There is no default password or setup code. Use at least 8 characters including an uppercase letter, a number and a special character, with no whitespace. Public HTTPS first setup is restricted to the administrator IP.

2. Settings → Change password requires the current password. A change invalidates existing sessions. A forgotten password needs an administrative reset through existing server access; see DISTRIBUTION.md. Allow cookies for this site.

3. Port 8787 is local-only by default. Use a regular SSH tunnel or the HTTPS installer with your public IP for remote access. Public deployment needs TCP 443 for nginx and TCP 80 for certificate renewal. Do not expose port 8787 publicly.

```text
sudo python3 tools/install_https.py --address YOUR_PUBLIC_IP
```

