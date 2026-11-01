# Installation Linux complète

Installation et premiers pas · 1.3.0.1

1. L’installation complète est testée sur Ubuntu 26.04 amd64 avec systemd, mdadm, Docker Engine et Compose. L’adaptateur ne prend pas en charge Docker rootless ni le remappage des UID. Vérifiez d’abord le RAID et les alertes existantes.

2. Première installation avec l’assistant sur main : docker compose up -d. L’application provient toujours de la dernière version stable publiée sur GitHub, sans préversion ni retour à une ancienne copie locale. Version et commit sont dans .installation/version.json. Le conteneur privilégié détecte adresses et certificats, réutilise un certificat IP valide ou en demande un sur hôte libre. L’URL HTTPS est écrite dans .installation/WEBADRESSE.txt et les journaux ; -d masque la sortie ultérieure. Mot de passe et accès fournisseurs se règlent dans le navigateur. Redémarrer la même installation ne constitue pas une mise à jour ; les autres installations restent inchangées. Ubuntu 24.04/26.04 amd64 avec systemd et Docker. Utilisez la même connexion pour navigateur et SSH. Consultez le guide initial.

3. Téléchargez les sources ou clonez le dépôt. Exécutez sudo python3 tools/install.py dans son répertoire. Saisissez vos identifiants et tokens Telegram/Discord dans le terminal ; OpenAI et Healthchecks sont facultatifs. Ne placez jamais de secrets dans une URL de clonage ou un chat.

4. L’installateur sauvegarde et migre une installation compatible. Il n’écrase pas aveuglément un projet Docker existant. Les agents restent hors des conteneurs. SSH et les membres RAID sont préservés. Vérifiez ensuite /status et /automatik_status dans les deux bots.

```text
docker compose up -d
```

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- [Installation complète avec Compose](https://github.com/s3bb3lhu/kiagent-docker/blob/main/FIRST_INSTALL.md)
