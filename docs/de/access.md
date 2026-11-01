# Anmeldung, Passwort & HTTPS

Einstellungen & Verbindungen · 1.3.0.1

1. Bei der ersten Einrichtung /setup öffnen. Es gibt kein Standardpasswort und keinen Einrichtungscode. Mindestens 8 Zeichen, ein Großbuchstabe, eine Zahl und ein Sonderzeichen; keine Leerzeichen. Bei öffentlichem HTTPS ist die Ersteinrichtung auf die Administrator-IP beschränkt.

2. Einstellungen → Passwort ändern verlangt das bisherige Passwort. Eine Änderung macht bestehende Sitzungen ungültig. Bei vergessenem Passwort ist ein administrativer Reset per bestehendem Serverzugang nötig; siehe DISTRIBUTION.md. Cookies für die Seite zulassen.

3. Standardmäßig ist Port 8787 nur lokal erreichbar. Für Fernzugriff einen regulären SSH-Tunnel oder den HTTPS-Installer mit eigener öffentlicher IP nutzen. Bei öffentlichem Betrieb benötigt nginx TCP 443 und die Zertifikatserneuerung TCP 80. Port 8787 nicht öffentlich freigeben.

```text
sudo python3 tools/install_https.py --address YOUR_PUBLIC_IP
```

