# Euskalmoneta

## Applications à développer

- Front BDC: Bureau de change
- Front GI: Gestion interne
- Front EA: Espace adhérents

- API globale: Django REST Framework

- Cyclos: App monétaire/bancaire (image: cyclos/cyclos:4.6.1, dépendant de pgSQL 9.* -> version a définir + PostGIS 2.2)
- Dolibarr custom Euskalmoneta: CRM pour gestion des adhérents, etc... (version 3.9 custom Euskalmoneta + docker-compose custom META-IT + MariaDB 10.1)
  - Branche utilisée: develop


### Front BDC

La méthode que j'utilise pour travailler dans cet environnement:

1) Je lance tous les services

```
docker-compose up -d
```

2) Je stoppe ceux que je vais avoir besoin de redémarrer manuellement

```
docker-compose stop api
docker-compose stop bureaudechange
```

3) Je les relance individuellement pour pouvoir les relancer facilement

```
docker-compose up api
docker-compose up bureaudechange
```

4) Si vous modifiez du React (JavaScript ou JSX), il est **obligatoire** de lancer cette commande:

Elle lance le watcher webpack, et c'est lui qui compile notre JSX et gère nos dépendances Web, l'output de cette commande
est un (ou +) bundle(s) se trouvant dans `src/bureaudechange/static/bundles`.

```
docker-compose run bureaudechange npm run watch
```

Il existe également 2 autres commandes:

Cette commande est lancée automagiquement lors d'un build du docker bureaudechange (cf. Dockerfile), il va lui aussi compiler et produire les output bundles (avec les dépendances de Dev), mais sans le watch évidemment.

```
docker-compose run bureaudechange npm run build
```

Comme précédemment, mais celle-ci est utilisée pour une mise en production (avec les dépendances de Prod, donc),
webpack va compresser les scripts/css et va retirer les commentaires, entre autres choses...

```
docker-compose run bureaudechange npm run build-production
```