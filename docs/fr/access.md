# Connexion, mot de passe et HTTPS

Paramètres et connexions · 1.1.0.0

1. Ouvrez /setup lors de la première configuration. Aucun mot de passe par défaut ni code. Utilisez au moins 8 caractères dont une majuscule, un chiffre et un caractère spécial, sans espace. L’initialisation HTTPS publique est limitée à l’IP de l’administrateur.

2. Paramètres → Modifier le mot de passe exige le mot de passe actuel. La modification invalide les sessions. En cas d’oubli, une réinitialisation administrative via l’accès serveur existant est nécessaire ; voir DISTRIBUTION.md. Autorisez les cookies du site.

3. Le port 8787 reste local par défaut. Utilisez un tunnel SSH habituel ou l’installateur HTTPS avec votre IP publique. Le déploiement public nécessite TCP 443 pour nginx et TCP 80 pour renouveler les certificats. N’exposez pas publiquement le port 8787.

```text
sudo python3 tools/install_https.py --address YOUR_PUBLIC_IP
```

