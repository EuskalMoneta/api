# Euskalmoneta

## Applications à développer

- Front BDC: Bureau de change
- Front GI: Gestion interne
- Front EA: Espace adhérents

- API globale: Django REST Framework

- Cyclos: App monétaire/bancaire (image: cyclos/cyclos:4.6.1, dépendant de pgSQL 9.* -> version a définir + PostGIS 2.2)
- Dolibarr custom Euskalmoneta: CRM pour gestion des adhérents, etc... (version 3.9 custom Euskalmoneta + docker compose custom META-IT + MariaDB 10.1)
  - Branche utilisée: develop


## Comment ça marche ?

La méthode que j'utilise pour travailler dans cet environnement:

1) Je lance tous les services

```
docker compose up -d
```

2) Je stoppe ceux que je vais avoir besoin de redémarrer manuellement

```
docker compose stop api
docker compose stop bureaudechange
```

3) Je les relance individuellement

```
docker compose up api
docker compose up bureaudechange
```

4) Si vous modifiez du React (JavaScript ou JSX), il est **obligatoire** de lancer cette commande:

Elle lance le watcher webpack, et c'est lui qui compile notre JSX et gère nos dépendances Web, l'output de cette commande
est un (ou +) bundle(s) se trouvant dans `/assets/static/bundles` du container `bureaudechange`.

```
docker compose exec bureaudechange npm run watch
```

Il existe également 2 autres commandes:

Cette commande est lancée automagiquement lors d'un build du docker bureaudechange (cf. Dockerfile), il va lui aussi compiler et produire les output bundles (avec les dépendances de Dev), mais sans le watch évidemment.

```
docker compose exec bureaudechange npm run build
```

Comme précédemment, mais celle-ci est utilisée pour une mise en production (avec les dépendances de Prod, donc),
webpack va compresser les scripts/css et va retirer les commentaires, entre autres choses...

```
docker compose run bureaudechange npm run build-production
```

Pour corriger les problèmes de droit sur dolibarr :
```
docker compose exec dolibarr-app chown -hR www-data:www-data /var/www/documents
```

### En cas de problème

Dans le cas où l'on veut remettre à zéro les bases de données Cyclos et/ou Dolibarr, il faudra effectuer depuis le dossier de l'api:
```
# pour Cyclos
(sudo) rm -rf data/cyclos/
(sudo) rm etc/cyclos/cyclos_constants.yml

# pour Dolibarr
(sudo) rm -rf data/mariadb/
```
Afin de supprimer les données liées au Cyclos et/ou Dolibarr actuels.


Puis, stopper toute la pile API (Cyclos + Dolibarr, et leurs bases de données…):
```
docker compose stop
```

La relancer:
```
docker compose up -d
```

Il est possible de jeter un oeil aux logs des restauration pour s'assurer de leur bon fonctionnement:
```
# pour Cyclos
docker compose logs -f cyclos-db

# pour Dolibarr
docker compose logs -f dolibarr-db
```

Pour Cyclos, une fois le restore terminé, il faudra redémarrer `cyclos-app`:
```
docker compose restart cyclos-app
```

L'entrypoint de l'API devrait maintenant pouvoir se connecter à `cyclos-app`, et ainsi lancer les scripts d'init de Cyclos.
```
docker compose logs -f api
```
Une fois ces scripts passés: l'API démarre enfin Django, et le développement peut commencer.

#### Docker compose 2025
Il est possible que les données de test dans Cyclos ne s'initialisent pas correctement lors du lancement du docker compose.
On peut le faire manuellement avec les étapes suivantes : 
``` shell
docker compose exec api bash
cd /cyclos
PASS=$(echo -n admin:admin | base64)
python setup.py http://cyclos-app:8080/ $PASS
python init_test_data.py http://cyclos-app:8080/ $PASS
```
Les données de test cyclos devraient maintenant être disponible sur http://localhost:8081/eusko

Restaurer la base cyclos
``` shell
docker exec -i api-cyclos-db-1 psql -U postgres -c "DROP DATABASE IF EXISTS cyclos;"
docker exec -i api-cyclos-db-1 psql -U postgres -c "CREATE DATABASE cyclos;"
cat exportCyclos4Anonymisee.sql | docker exec -i api-cyclos-db-1 psql -U cyclos -d cyclos
```

Restaurer la base dolibarr
``` shell
sudo docker exec -i api-dolibarr-db-1 \
  mysql -u pass -ppass -e "DROP DATABASE IF EXISTS pass;"    

sudo docker exec -i api-dolibarr-db-1  \
  mysql -u pass -ppass -e "CREATE DATABASE pass CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"


cat exportDolibarrAnonymisee.sql | sudo docker exec -i api-dolibarr-db-1 \
  mysql -u pass -ppass pass
```

### commandes utiles


`docker compose exec api ./manage.py migrate`

`docker compose exec api pip install -r requirements.txt`

Faire une sauvegarde de la BDD
`docker exec -it api_dolibarr-db_1 usr/bin/mysqldump -u pass --password=pass pass > backup.sql`

Faire une restauration de la BDD
`cat mysqldump_dolibarr.sql | docker exec -i api_dolibarr-db_1 /usr/bin/mysql -u pass --password=pass pass`

## Comment initier le circuit Euskal Moneta ?

Afin d'effectuer les différentes opérations de nos applications, nous avons besoin avant toute chose d'initier les flux d'Eusko.

### I) Impression des billets Eusko 

Cette étape est maintenant automatisée dans le script `init_test_data.py`, ce qui suit reste pour documentation, nous pouvons d’ores et déjà aller au point II).

Pour cela, rendez-vous dans [l'interface d'administration de Cyclos](http://localhost:8081/global/#login).

Connectez-vous avec les identifiants Gestion interne (demo/demo), puis dans `Banking > System payment > Between system accounts`.

Rentrer dans le formulaire:
```
From account: Compte de débit eusko billet
Montant: 126,500 EUS.
```

### II) Sortie Coffre

Rendez-vous dans l'application Gestion interne pour sortir ces nouveaux billets du Coffre:

1. Se connecter avec les identifiants notés ci-dessus
2. Dans `Coffre > Sortie`, mettre un certain montant, 500 par exemple vers un bureau de change donné, comme Euskal Moneta (B001).

Vous pouvez maintenant déclarer une entrée stock dans l'application Bureau de change en se connectant avec le compte B001:
`Gestion > Stock de billets > Entrée`, sélectionner la liste correspondante à votre Sortie coffre.... Et voilà !

### III) Suite et fin

Une fois ceci fait, vous avez accès à toutes les actions possibles dans l'application BDC (sauf cotisation en Eusko, il faudra faire un change en premier lieu):

* Change
* Cotisation Eusko
* Reconversions
* Sortie stock, etc...