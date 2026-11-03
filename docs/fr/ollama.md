# Ollama : IA locale et limites

Paramètres et connexions · 1.5.0.0

1. Choisissez Ollama ou OpenAI dans Paramètres → Fournisseur IA. Ollama ne nécessite aucune clé API. Aucun changement automatique de fournisseur. Ollama traite sur le serveur ; OpenAI reçoit demandes et mesures.

2. Ollama existant reste inchangé : aucun téléchargement, mise à jour, redémarrage ou changement des limites. Seuls les modèles texte locaux installés sont proposés. Modèles absents ou services arrêtés exigent une configuration administrative.

3. Chaque installation Docker vérifie Ollama. Les nouvelles instances utilisent au maximum 25 pour cent CPU, deux cœurs et 4 Gio RAM avec réserves supplémentaires. Petit modèle Qwen3, une requête à la fois, contexte 2048 et maintien court limitent la charge. Ressources insuffisantes : installation omise avec indication.

- [Ollama Docker](https://docs.ollama.com/docker)
- [Ollama FAQ](https://docs.ollama.com/faq)
- [Qwen3](https://ollama.com/library/qwen3)
