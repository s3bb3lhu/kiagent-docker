# Healthchecks : signaux de vie et alertes

Paramètres et connexions · 1.3.0.1

1. Créez des checks distincts pour le serveur et le bot dans Healthchecks. Copiez leurs URL de ping UUID et affectez-les dans Paramètres → Healthchecks. Des URL de ping sont requises, pas une clé API de gestion.

2. Configurez les destinataires ou intégrations dans Healthchecks. Adaptez période et délai de grâce aux signaux réels. Un test contrôlé doit vérifier séparément la panne du check et la réception de l’alerte.

3. Les deux champs sont facultatifs. Traitez les URL comme des mots de passe et ne les placez pas dans le dépôt. L’absence de signaux n’est pas un diagnostic complet des disques ou applications.

- [Gérer Healthchecks](https://healthchecks.io/checks/)
- [Documentation Healthchecks](https://healthchecks.io/docs/)
