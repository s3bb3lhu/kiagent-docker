# Mises à jour, version et dépannage

Exploitation et maintenance · 1.0.0.1

1. La version apparaît en bas du menu. La version actuelle est 1.0.0.1. Les mises à jour s’installent explicitement depuis des sources vérifiées ; aucune mise à jour autonome. Vérifiez d’abord tâches ouvertes/incertaines et sauvegardes.

2. Sur une installation gérée existante, lancez tools/install_ui.py depuis les sources préparées avec sudo. Il teste isolément, sauvegarde code/images et vérifie le redémarrage. Secrets, mot de passe, historique et délais sont conservés. Rechargez avec Ctrl+F5.

3. En cas de 502 ou bot silencieux, lisez d’abord états des services, santé des conteneurs et rapport d’installation via SSH. Pour les erreurs IA, vérifiez OpenAI et l’accès au projet ; /status et /ki_install sont indépendants. En cas d’erreur de cookie, rouvrez la connexion et autorisez les cookies.

4. Ne copiez pas de tokens ou journaux non nettoyés dans des tickets publics. Les actions incertaines ne sont jamais répétées automatiquement. Si vous avez personnalisé l’installation, comparez les fichiers au projet avant mise à jour.

```text
systemctl is-active kiagent-config kiagent-docker kiagent-executor kiagent-packages
```

```text
sudo python3 tools/install_ui.py
```

