# Sauvegardes et restauration

Exploitation et maintenance · 1.3.0.1

1. L’installation Linux gérée sauvegarde chaque jour à 03:15 Europe/Berlin dans /var/backups/kiagent-daily. Les archives contiennent des secrets et un instantané SQLite cohérent, lisibles uniquement par root. Aucune suppression automatique des anciennes archives ; surveillez l’espace.

2. Les tests isolés vérifient fichiers et cohérence de base, pas un nouveau serveur complet. Les sauvegardes sur le même RAID ne protègent pas d’une perte totale. Prévoyez des copies externes séparément. Ne publiez jamais archives, volumes ou fichiers d’authentification.

3. Pour restaurer, arrêtez les services de façon contrôlée, vérifiez propriétaires/droits et ne restaurez pas un ancien historique sur un système ayant continué à fonctionner. Des autorisations consommées pourraient redevenir utilisables. L’authentification web est séparée et exclue de la sauvegarde quotidienne ; réinitialisez-la administrativement.

