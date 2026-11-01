# Docker sous Linux et Windows

Installation et premiers pas · 1.4.0.0

1. La variante portable nécessite des conteneurs Linux. Windows Server exige une VM Linux avec Docker Engine ; les conteneurs Windows natifs et les actions sur l’hôte Windows ne sont pas implémentés. Un PC Windows nécessite un environnement Linux pris en charge par le fournisseur.

2. Exécutez la commande Compose ci-dessous dans le projet. Sur cette même machine, ouvrez http://127.0.0.1:8787/setup et définissez un mot de passe. Le volume portal-state contient des données privées et ne doit pas être distribué.

3. Sans adaptateur hôte, cette variante conserve uniquement les paramètres : aucun bot actif, mesure serveur, installation ou réparation. Les commandes désactivées sont intentionnelles.

```text
docker compose -f compose.portable.yaml up -d --build --wait
```

- [Docker Desktop](https://docs.docker.com/desktop/)
