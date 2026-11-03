# Installation Linux complète

Installation et premiers pas · 1.5.0.0

1. L’installation complète est testée sur Ubuntu 26.04 amd64 avec systemd, mdadm, Docker Engine et Compose. L’adaptateur ne prend pas en charge Docker rootless ni le remappage des UID. Vérifiez d’abord le RAID et les alertes existantes.

2. Première installation avec l’assistant sur main : docker compose up -d. L’application provient toujours de la dernière version stable publiée sur GitHub, sans préversion ni retour à une ancienne copie locale. Version et commit sont dans .installation/version.json. Le conteneur privilégié détecte adresses et certificats, réutilise un certificat IP valide ou en demande un sur hôte libre. L’URL HTTPS est écrite dans .installation/WEBADRESSE.txt et les journaux ; -d masque la sortie ultérieure. Mot de passe et accès fournisseurs se règlent dans le navigateur. Redémarrer la même installation ne constitue pas une mise à jour ; les autres installations restent inchangées. Ubuntu 24.04/26.04 amd64 avec systemd et Docker. Utilisez la même connexion pour navigateur et SSH. Consultez le guide initial.

3. Clonez le dépôt et lancez docker compose up -d. Les adresses sont enregistrées dans .installation. Définissez identifiant et mot de passe dans le navigateur, sans jeton. Ajoutez ensuite identifiants de bots et clés sur la page, jamais dans le chat.

4. L’installateur ne reprend pas de projets étrangers et ne met pas à jour automatiquement les installations existantes. Les conteneurs web restent non privilégiés, avec agents fixes sur l’hôte. SSH et RAID sont préservés. Testez les bots après configuration.

```text
docker compose up -d
```

```text
docker compose up -d
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Installation complète avec Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/main/FIRST_INSTALL.md)
