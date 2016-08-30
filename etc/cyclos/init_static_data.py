# coding: utf-8
from __future__ import unicode_literals
import argparse
import logging
import requests

logging.basicConfig()
logger = logging.getLogger(__name__)


def check_request_status(r):
    if r.status_code == requests.codes.ok:
        logger.info('OK')
    else:
        logger.error(r.text)
        r.raise_for_status()

# Arguments à fournir dans la ligne de commande
parser = argparse.ArgumentParser()
parser.add_argument('url', help='URL of Cyclos')
parser.add_argument('authorization',
                    help='string to use for Basic Authentication')
parser.add_argument('--debug',
                    help='enable debug messages',
                    action='store_true')
args = parser.parse_args()

if not args.url.endswith('/'):
    args.url = args.url + '/'
if args.debug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

for k, v in vars(args).items():
    logger.debug('args.%s = %s', k, v)

# URLs des web services
global_web_services = args.url + 'global/web-rpc/'
eusko_web_services = args.url + 'eusko/web-rpc/'

# En-têtes pour toutes les requêtes (il n'y a qu'un en-tête, pour
# l'authentification).
headers = {'Authorization': 'Basic ' + args.authorization}

# On fait une 1ère requête en lecture seule uniquement pour vérifier
# si les paramètres fournis sont corrects.
logger.info('Vérification des paramètres fournis...')
r = requests.post(global_web_services + 'network/search',
                  headers=headers, json={})
check_request_status(r)


########################################################################
# Création des utilisateurs pour les banques de dépôt et les comptes
# dédiés.
#
def create_user(group, name, login=None, password=None, custom_values=None):
    logger.info('Création de l\'utilisateur "%s" (groupe "%s")...', name, group)
    # FIXME code à déplacer pour ne pas l'exécuter à chaque fois
    r = requests.post(eusko_web_services + 'group/search',
                      headers=headers, json={})
    check_request_status(r)
    logger.critical(r.text)
    groups = r.json()['result']['pageItems']
    for g in groups:
        if g['name'] == group:
            group_id = g['id']
    user_registration = {
        'group': group_id,
        'name': name,
        'skipActivationEmail': True,
    }
    if login and password:
        # FIXME code à déplacer pour ne pas l'exécuter à chaque fois
        r = requests.get(eusko_web_services + 'passwordType/list',
                         headers=headers)
        check_request_status(r)
        password_types = r.json()['result']
        for password_type in password_types:
            if password_type['internalName'] == 'login':
                login_password = password_type
        user_registration['username'] = login
        user_registration['passwords'] = [
            {
                'type': login_password,
                'value': password,
                'confirmationValue': password,
                'assign': True,
                'forceChange': False,
            },
        ]
    if custom_values:
        user_registration['customValues'] = []
        for field_id, value in custom_values.items():
            r = requests.get(eusko_web_services + 'userCustomField/load/' + field_id, headers=headers)
            check_request_status(r)
            custom_field_type = r.json()['result']['type']
            if custom_field_type == 'LINKED_ENTITY':
                value_key = 'linkedEntityValue'
            user_registration['customValues'].append({
                'field': field_id,
                value_key: value,
            })
    logger.debug('create_user : json = %s', user_registration)
    r = requests.post(eusko_web_services + 'user/register',
                      headers=headers,
                      json=user_registration)
    check_request_status(r)
    logger.debug('result = %s', r.json()['result'])
    user_id = r.json()['result']['user']['id']
    logger.debug('user_id = %s', user_id)
    return user_id

create_user(
    group='Banques de dépôt',
    name='Crédit Agricole',
)
create_user(
    group='Banques de dépôt',
    name='La Banque Postale',
)
create_user(
    group='Comptes dédiés',
    name='Compte dédié eusko billet',
)
create_user(
    group='Comptes dédiés',
    name='Compte dédié eusko numérique',
)


########################################################################
# Création des utilisateurs pour les tests.
# FIXME Séparer ce code du code qui crée les données statiques.

# On récupère l'id du champ perso 'BDC'.
r = requests.get(eusko_web_services + 'userCustomField/list', headers=headers)
check_request_status(r)
user_custom_fields = r.json()['result']
for field in user_custom_fields:
    if field['internalName'] == 'bdc':
        id_user_custom_field_bdc = field['id']

create_user(
    group='Administrateurs de comptes',
    name='Admin Comptes',
    login='admin_comptes',
    password='admin',
)

bureaux_de_change = {
    'B001': 'Euskal Moneta',
    'B002': 'Le Fandango',
    'B003': 'Café des Pyrénées',
}
for login, name in bureaux_de_change.items():
    id_bdc = create_user(
        group='Bureaux de change',
        name=name + ' (BDC)',
    )
    create_user(
        group='Opérateurs BDC',
        name=name + ' (opérateur BDC)',
        login=login,
        password=login,
        custom_values={
            id_user_custom_field_bdc: id_bdc,
        }
    )
