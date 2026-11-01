# Installation Linux complète

Installation et premiers pas · 1.0.0.1

1. L’installation complète est testée sur Ubuntu 26.04 amd64 avec systemd, mdadm, Docker Engine et Compose. L’adaptateur ne prend pas en charge Docker rootless ni le remappage des UID. Vérifiez d’abord le RAID et les alertes existantes.

2. Téléchargez les sources ou clonez le dépôt. Exécutez sudo python3 tools/install.py dans son répertoire. Saisissez vos identifiants et tokens Telegram/Discord dans le terminal ; OpenAI et Healthchecks sont facultatifs. Ne placez jamais de secrets dans une URL de clonage ou un chat.

3. L’installateur sauvegarde et migre une installation compatible. Il n’écrase pas aveuglément un projet Docker existant. Les agents restent hors des conteneurs. SSH et les membres RAID sont préservés. Vérifiez ensuite /status et /automatik_status dans les deux bots.

```text
sudo python3 tools/install.py
```

- [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
