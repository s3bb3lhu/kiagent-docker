# Services, Docker and designs

Features and control · 1.5.0.0

1. A fresh full installation includes server control on HTTPS port 9898 and the services portal on 9999. Occupied ports are preserved; actual addresses are recorded under .installation. Create a username and password in each browser interface. No setup token is required.

2. Services and running or stopped containers are discovered automatically. Start, stop and restart require confirmation of the target name. Stopping critical services can interrupt access. Uncertain results are never retried automatically.

3. Container websites provides buttons for published TCP ports; a port does not prove a web protocol. Under Design choose layout, palette, logo and button independently. Day/night has a separate switch. Choices persist in that browser.

