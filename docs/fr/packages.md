# IA et installation de paquets

Fonctions et commandes · 1.0.0.0

1. /ki Installe nginx reconnaît la demande et prépare un plan APT. /ki_install nginx demande le plan sans IA. Dans Commandes, saisissez un paquet précis. Les paquets valides des dépôts APT configurés sont autorisés ; pas d’URL, fichier .deb local ni option shell.

2. Vérifiez le paquet et toutes ses dépendances avec versions, puis confirmez séparément. L’autorisation est unique, liée à l’identité/message et valable deux minutes. Un plan modifié est refusé. Les paquets cibles déjà installés ne sont pas réinstallés.

3. L’installation s’exécute en arrière-plan sur l’hôte Linux. Les dépendances peuvent être mises à jour selon le plan et les scripts redémarrer des services. Suppressions et rétrogradations sont interdites. /ki_install_status affiche la dernière tâche. Ne répétez pas un résultat incertain ; vérifiez via SSH.

