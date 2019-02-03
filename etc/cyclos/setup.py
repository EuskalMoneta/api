# coding: utf-8
from __future__ import unicode_literals

import argparse
import logging

import requests
from slugify import slugify

try:
    stringType = basestring
except NameError:  # Python 3, basestring causes NameError
    stringType = str

logging.basicConfig()
logger = logging.getLogger(__name__)


def check_request_status(r):
    if r.status_code == requests.codes.ok:
        logger.info('OK')
    else:
        logger.error(r.text)
        r.raise_for_status()


def get_internal_name(name):
    name = name.replace('€', 'euro')
    return slugify(name, separator='_')

# Ensemble des constantes nécessaires à l'API.
constants_by_category = {}


def add_constant(category, name, value):
    if category not in constants_by_category.keys():
        constants_by_category[category] = {}
    internal_name = get_internal_name(name)
    constants_by_category[category][internal_name] = value

# Arguments à fournir dans la ligne de commande
parser = argparse.ArgumentParser()
parser.add_argument('url', help='URL of Cyclos')
parser.add_argument('authorization',
                    help='string to use for Basic Authentication')
parser.add_argument('--debug',
                    help='enable debug messages',
                    action='store_true')
args = parser.parse_args()
for k, v in vars(args).items():
    logger.debug('args.%s = %s', k, v)

url = args.url.rstrip('/')
if args.debug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

# URLs des web services
global_web_services = url + '/global/web-rpc/'
eusko_web_services = url + '/eusko/web-rpc/'

# En-têtes pour toutes les requêtes (il n'y a qu'un en-tête, pour
# l'authentification).
headers = {'Authorization': 'Basic ' + args.authorization}

# On fait une 1ère requête en lecture seule uniquement pour vérifier
# si les paramètres fournis sont corrects.
logger.info('Vérification des paramètres fournis...')
r = requests.post(global_web_services + 'network/search',
                  headers=headers, json={})
check_request_status(r)

networks = r.json()['result']['pageItems']
for network in networks:
    if network['internalName'] == 'eusko':
        logger.info(networks)
        raise Exception('Cyclos est déjà configuré, utilisez le fichier cyclos_constants.yml.sample '
                        'ou supprimez la base...')

# On force une mise à jour de la license pour pouvoir créer des
# utilisateurs tout de suite après la fin du paramétrage.
# Sans ça Cyclos dit que la création d'utilisateurs est désactivée car
# le serveur de license ne peut pas être contacté, et il faut attendre
# quelques minutes (il doit donc y avoir une mise à jour automatique de
# la license dans cet intervalle).
logger.info('Mise à jour de la licence...')
r = requests.post(global_web_services + 'license/onlineUpdate',
                  headers=headers, json=[])
check_request_status(r)
logger.info('Récupération de la licence...')
r = requests.get(global_web_services + 'license/getLicense', headers=headers)
check_request_status(r)
logger.debug('Clé de licence : %s', r.json()['result']['licenseKey'])

# Récupération de la liste des canaux pour avoir leurs identifiants
# sans les coder en dur (du coup je code en dur leur nom interne mais je
# préfère ça).
logger.info('Récupération de la liste des canaux...')
r = requests.get(global_web_services + 'channels/list', headers=headers)
check_request_status(r)
channels = r.json()['result']
for channel in channels:
    if channel['internalName'] == 'main':
        ID_CANAL_MAIN_WEB = channel['id']
    elif channel['internalName'] == 'webServices':
        ID_CANAL_WEB_SERVICES = channel['id']
    elif channel['internalName'] == 'pos':
        ID_CANAL_PAY_AT_POS = channel['id']
    elif channel['internalName'] == 'mobile':
        ID_CANAL_MOBILE_APP = channel['id']
logger.debug('ID_CANAL_MAIN_WEB = %s', ID_CANAL_MAIN_WEB)
logger.debug('ID_CANAL_WEB_SERVICES = %s', ID_CANAL_WEB_SERVICES)
logger.debug('ID_CANAL_PAY_AT_POS = %s', ID_CANAL_PAY_AT_POS)
logger.debug('ID_CANAL_MOBILE_APP = %s', ID_CANAL_MOBILE_APP)

# Récupération de la liste des types de mots de passe.
logger.info('Récupération de la liste des types de mots de passe...')
r = requests.get(global_web_services + 'passwordType/list', headers=headers)
check_request_status(r)
password_types = r.json()['result']
for password_type in password_types:
    if password_type['internalName'] == 'login':
        ID_PASSWORD_LOGIN = password_type['id']
    elif password_type['internalName'] == 'pin':
        ID_PASSWORD_PIN = password_type['id']
logger.debug('ID_PASSWORD_LOGIN = %s', ID_PASSWORD_LOGIN)
logger.debug('ID_PASSWORD_PIN = %s', ID_PASSWORD_PIN)

# Récupération de la liste des méthodes d'identification.
logger.info("Récupération de la liste des méthodes d'identification...")
r = requests.get(global_web_services + 'principalType/list', headers=headers)
check_request_status(r)
principal_types = r.json()['result']
for principal_type in principal_types:
    if principal_type['internalName'] == 'username':
        ID_PRINCIPAL_TYPE_LOGIN_NAME = principal_type['id']
logger.debug('ID_PRINCIPAL_TYPE_LOGIN_NAME = %s', ID_PRINCIPAL_TYPE_LOGIN_NAME)


########################################################################
# Modification de la configuration par défaut globale :
# - définition de l'URL racine, pour que l'application web fonctionne
# - choix de la virgule comme séparateur pour les décimales
# - dates au format jour/mois/année
# - heures au format 24 heures
# - activation de l'utilisation des numéros de compte
# - activation du canal "Web services" par défaut pour tous les
#   utilisateurs
#
# Remarque : on configure l'accès aux web services comme étant activé
# par défaut et pas comme étant imposé mais comme aucun groupe n'a la
# permission "Manage my channels access", cela revient au même.
#
# D'abord on récupère l'id de la config par défaut.
r = requests.get(global_web_services + 'configuration/getDefault',
                 headers=headers)
check_request_status(r)
global_default_config_id = r.json()['result']['id']
# On charge la configuration par défaut pour pouvoir la modifier.
r = requests.get(
    global_web_services + 'configuration/load/' + global_default_config_id,
    headers=headers
)
check_request_status(r)
global_default_config = r.json()['result']
global_default_config['rootUrl'] = url
global_default_config['numberFormat'] = 'COMMA_AS_DECIMAL'
global_default_config['dateFormat'] = 'DMY_SLASH'
global_default_config['timeFormat'] = 'H24'
global_default_config['accountNumberConfiguration'] = {
    'enabled': True
}
r = requests.post(
    global_web_services + 'configuration/save',
    headers=headers,
    json=global_default_config
)
check_request_status(r)
# Puis on liste les config de canaux pour retrouver l'id de la config
# du canal "Web services".
r = requests.get(
    global_web_services + 'channelConfiguration/list/' + global_default_config_id,
    headers=headers
)
check_request_status(r)
for channel_config in r.json()['result']:
    if channel_config['channel']['internalName'] == 'webServices':
        ws_config_id = channel_config['id']
# Enfin on charge la config du canal "Web services", pour pouvoir la
# modifier.
r = requests.get(
    global_web_services + 'channelConfiguration/load/' + ws_config_id,
    headers=headers
)
check_request_status(r)
ws_config = r.json()['result']
ws_config['userAccess'] = 'DEFAULT_ENABLED'
r = requests.post(
    global_web_services + 'channelConfiguration/save',
    headers=headers,
    json=ws_config
)
check_request_status(r)


########################################################################
# Création du réseau "Eusko".
#
# C'est le seul réseau, tout le reste du paramétrage va être fait
# dans ce réseau. On ne crée pas d'administrateur spécifique pour ce
# réseau, on fait tout avec l'admnistrateur global.
# Note : On utilise la méthode save() de l'interface CRUDService. Le
# résultat de la requête est l'id de l'objet créé.
#
def create_network(name, internal_name):
    logger.info('Création du réseau "%s"...', name)
    r = requests.post(global_web_services + 'network/save',
                      headers=headers,
                      json={
                          'name': 'Eusko',
                          'internalName': get_internal_name(name),
                          'enabled': True
                      })
    check_request_status(r)
    network_id = r.json()['result']
    logger.debug('network_id = %s', network_id)
    return network_id

ID_RESEAU_EUSKO = create_network(
    name='Eusko',
    internal_name='eusko',
)


########################################################################
# Création des devises "Eusko" et "Euro".
#
def create_currency(name, symbol):
    logger.info('Création de la devise "%s"...', name)
    r = requests.post(eusko_web_services + 'currency/save',
                      headers=headers,
                      json={
                          'name': name,
                          'internalName': get_internal_name(name),
                          'symbol': symbol,
                          'suffix': ' ' + symbol,
                          'precision': 2
                      })
    check_request_status(r)
    currency_id = r.json()['result']
    logger.debug('currency_id = %s', currency_id)
    add_constant('currencies', name, currency_id)
    return currency_id

ID_DEVISE_EUSKO = create_currency(
    name='Eusko',
    symbol='EUS',
)
ID_DEVISE_EURO = create_currency(
    name='Euro',
    symbol='€',
)


########################################################################
# Création du token "Carte NFC".
#
def create_token(name, plural_name, token_type, token_mask, maximum_per_user):
    logger.info('Création du token "%s"...', name)
    r = requests.post(eusko_web_services + 'principalType/save',
                      headers=headers,
                      json={
                          'class': 'org.cyclos.model.access.principaltypes.TokenPrincipalTypeDTO',
                          'name': name,
                          'pluralName': plural_name,
                          'internalName': get_internal_name(name),
                          'tokenType': token_type,
                          'tokenMask': token_mask,
                          'maximumPerUser': maximum_per_user,
                      })
    check_request_status(r)
    token_id = r.json()['result']
    logger.debug('token_id = %s', token_id)
    add_constant('tokens', name, token_id)
    return token_id

ID_TOKEN_CARTE_NFC = create_token(
    name='Carte NFC',
    plural_name='Cartes NFC',
    token_type='NFC_TAG',
    token_mask='#### #### #### ####',
    maximum_per_user=100,
)

all_token_types = [
    ID_TOKEN_CARTE_NFC,
]


########################################################################
# Création du client "Point de vente NFC".
#
def create_access_client(name, plural_name, maximum_per_user, permission):
    logger.info('Création du client "%s"...', name)
    r = requests.post(eusko_web_services + 'principalType/save',
                      headers=headers,
                      json={
                          'class': 'org.cyclos.model.access.principaltypes.AccessClientPrincipalTypeDTO',
                          'name': name,
                          'pluralName': plural_name,
                          'internalName': get_internal_name(name),
                          'maximumPerUser': maximum_per_user,
                          'permission': permission,
                      })
    check_request_status(r)
    access_client_id = r.json()['result']
    logger.debug('access_client_id = %s', access_client_id)
    add_constant('access_clients', name, access_client_id)
    return access_client_id

ID_CLIENT_POINT_DE_VENTE_NFC = create_access_client(
    name='Point de vente NFC',
    plural_name='Points de vente NFC',
    maximum_per_user=10,
    permission='RECEIVE_PAYMENT',
)

all_access_clients = [
    ID_CLIENT_POINT_DE_VENTE_NFC,
]


########################################################################
# Modification de la configuration des canaux "Pay at POS" et "Mobile
# app".
# La configuration par défaut pour chaque canal est héritée de la
# configuration globale. Pour personnaliser cette configuration au
# niveau du réseau Eusko, il faut créer une nouvelle configuration
# pour chaque canal.
# Ensuite on personnalise les configurations de la manière suivante :
# - activation de chaque canal par défaut pour tous les utilisateurs
# - canal "Pay at POS" : le mot de passe de confirmation est le code PIN
# - canal "Mobile app" : on définit deux méthodes d'identification pour
#   se connecter à l'application mobile :
#       - le login, pour les connexions "normales"
#       - le client "Point de vente NFC", pour pouvoir se connecter à
#         l'application mobile en mode point de vente (POS)
#   et on définit le token "Carte NFC" comme méthode d'identification
#   pour recevoir des paiements en mode POS.
#
# Remarque : Il faut faire ces modifications après avoir créé le token
# "Carte NFC" et l'access client "Point de vente NFC" car nous en avons
# besoin pour configurer le canal "Mobile app".
#
def get_data_for_new_channel_configuration(channel, configuration):
    logger.debug("get_data_for_new_channel_configuration(%s, %s)", channel, configuration)
    r = requests.post(eusko_web_services + 'channelConfiguration/getDataForNew/',
                      headers=headers,
                      json={
                          'channel': channel,
                          'configuration': configuration,
                      })
    check_request_status(r)
    return r.json()['result']['dto']

# D'abord on récupère l'id de la config par défaut.
logger.info('Récupération de l\'id de la configuration par défaut...')
r = requests.get(eusko_web_services + 'configuration/getDefault',
                 headers=headers)
check_request_status(r)
eusko_default_config_id = r.json()['result']['id']
# Puis on crée une nouvelle configuration pour le canal "Pay at POS".
logger.info('Création d\'une nouvelle configuration pour le canal "Pay at POS"...')
new_pos_config = get_data_for_new_channel_configuration(
    channel=ID_CANAL_PAY_AT_POS,
    configuration=eusko_default_config_id)
new_pos_config['defined'] = True
new_pos_config['enabled'] = True
new_pos_config['userAccess'] = 'DEFAULT_ENABLED'
new_pos_config['confirmationPassword'] = ID_PASSWORD_PIN
logger.info('Sauvegarde de la nouvelle configuration de canal...')
r = requests.post(
    eusko_web_services + 'channelConfiguration/save',
    headers=headers,
    json=new_pos_config
)
check_request_status(r)
# De le même manière, on crée une nouvelle configuration pour le canal
# "Mobile app".
logger.info('Création d\'une nouvelle configuration pour le canal "Mobile app"...')
new_mobile_app_config = get_data_for_new_channel_configuration(
    channel=ID_CANAL_MOBILE_APP,
    configuration=eusko_default_config_id)
new_mobile_app_config['defined'] = True
new_mobile_app_config['enabled'] = True
new_mobile_app_config['userAccess'] = 'DEFAULT_ENABLED'
new_mobile_app_config['principalTypes'] = [
    ID_PRINCIPAL_TYPE_LOGIN_NAME,
    ID_CLIENT_POINT_DE_VENTE_NFC,
]
new_mobile_app_config['receivePaymentPrincipalTypes'] = [
    ID_TOKEN_CARTE_NFC,
]
logger.info('Sauvegarde de la nouvelle configuration de canal...')
r = requests.post(
    eusko_web_services + 'channelConfiguration/save',
    headers=headers,
    json=new_mobile_app_config
)
check_request_status(r)


########################################################################
# Création d'une configuration spécifique pour les groupes "Opérateurs
# BDC" et "Gestion interne".
#
# Par défaut le délai de validité des sessions via les services web est
# de 5 minutes. Ce délai est trop court et rend l'utilisation des
# applications BDC et Gestion Interne pénible.
# On crée donc une nouvelle configuration identique à celle par défaut
# mais dans laquelle les sessions créées vis les services web sont
# valables 2h.
#
def get_data_for_new_configuration(parent_configuration):
    logger.debug("get_data_for_new_configuration(%s)", parent_configuration)
    r = requests.post(eusko_web_services + 'configuration/getDataForNew/',
                      headers=headers,
                      json=[parent_configuration])
    check_request_status(r)
    return r.json()['result']['dto']

# D'abord on crée une nouvelle configuration qui hérite de la config par
# défaut.
logger.info("Création d'une nouvelle configuration pour les opérateurs BDC...")
operateur_bdc_config = get_data_for_new_configuration(eusko_default_config_id)
operateur_bdc_config['name'] = 'Opérateurs BDC'
logger.info('Sauvegarde de la nouvelle configuration...')
r = requests.post(
    eusko_web_services + 'configuration/save',
    headers=headers,
    json=operateur_bdc_config
)
check_request_status(r)
ID_CONFIG_OPERATEURS_BDC = r.json()['result']
# Puis on crée une nouvelle configuration pour le canal "Web services".
logger.info('Création d\'une nouvelle configuration pour le canal "Web services"...')
operateur_bdc_ws_config = get_data_for_new_channel_configuration(
    channel=ID_CANAL_WEB_SERVICES,
    configuration=ID_CONFIG_OPERATEURS_BDC)
operateur_bdc_ws_config['defined'] = True
operateur_bdc_ws_config['sessionTimeout']['amount'] = 2
operateur_bdc_ws_config['sessionTimeout']['field'] = 'HOURS'
logger.info('Sauvegarde de la nouvelle configuration de canal...')
r = requests.post(
    eusko_web_services + 'channelConfiguration/save',
    headers=headers,
    json=operateur_bdc_ws_config
)
check_request_status(r)

# On fait la même chose pour Gestion interne.
logger.info("Création d'une nouvelle configuration pour Gestion interne...")
gestion_interne = get_data_for_new_configuration(eusko_default_config_id)
gestion_interne['name'] = 'Gestion interne'
logger.info('Sauvegarde de la nouvelle configuration...')
r = requests.post(
    eusko_web_services + 'configuration/save',
    headers=headers,
    json=gestion_interne
)
check_request_status(r)
ID_CONFIG_GESTION_INTERNE = r.json()['result']
logger.info('Création d\'une nouvelle configuration pour le canal "Web services"...')
gestion_interne_ws_config = get_data_for_new_channel_configuration(
    channel=ID_CANAL_WEB_SERVICES,
    configuration=ID_CONFIG_GESTION_INTERNE)
gestion_interne_ws_config['defined'] = True
gestion_interne_ws_config['sessionTimeout']['amount'] = 2
gestion_interne_ws_config['sessionTimeout']['field'] = 'HOURS'
logger.info('Sauvegarde de la nouvelle configuration de canal...')
r = requests.post(
    eusko_web_services + 'channelConfiguration/save',
    headers=headers,
    json=gestion_interne_ws_config
)
check_request_status(r)


########################################################################
# Création des champs personnalisés pour les paiements.
#
# Note: On a besoin de la liste des champs personnalisés pour créer les
# types de compte puis les types de paiement, c'est pour cette raison
# qu'ils sont créés en premier.
def create_transaction_custom_field_linked_user(name, required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(eusko_web_services + 'transactionCustomField/save',
                      headers=headers,
                      json={
                          'name': name,
                          'internalName': get_internal_name(name),
                          'type': 'LINKED_ENTITY',
                          'linkedEntityType': 'USER',
                          'control': 'ENTITY_SELECTION',
                          'required': required
                      })
    check_request_status(r)
    custom_field_id = r.json()['result']
    logger.debug('custom_field_id = %s', custom_field_id)
    add_constant('transaction_custom_fields', name, custom_field_id)
    return custom_field_id


def create_transaction_custom_field_single_selection(name,
                                                     possible_values_name,
                                                     possible_values,
                                                     required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(eusko_web_services + 'transactionCustomField/save',
                      headers=headers,
                      json={
                          'name': name,
                          'internalName': get_internal_name(name),
                          'type': 'SINGLE_SELECTION',
                          'control': 'SINGLE_SELECTION',
                          'required': required
                      })
    check_request_status(r)
    custom_field_id = r.json()['result']
    logger.debug('custom_field_id = %s', custom_field_id)
    add_constant('transaction_custom_fields', name, custom_field_id)
    for value in possible_values:
        logger.info('Ajout de la valeur possible "%s"...', value)
        r = requests.post(eusko_web_services + 'transactionCustomFieldPossibleValue/save',
                          headers=headers,
                          json={
                              'field': custom_field_id,
                              'value': value
                          })
        check_request_status(r)
        possible_value_id = r.json()['result']
        add_constant(possible_values_name, value, possible_value_id)
    return custom_field_id


def create_transaction_custom_field_text(name, unique=False,
                                         required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(eusko_web_services + 'transactionCustomField/save',
                      headers=headers,
                      json={
                          'name': name,
                          'internalName': get_internal_name(name),
                          'type': 'STRING',
                          'size': 'LARGE',
                          'control': 'TEXT',
                          'unique': unique,
                          'required': required
                      })
    check_request_status(r)
    custom_field_id = r.json()['result']
    logger.debug('custom_field_id = %s', custom_field_id)
    add_constant('transaction_custom_fields', name, custom_field_id)
    return custom_field_id


def create_transaction_custom_field_decimal(name, required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(eusko_web_services + 'transactionCustomField/save',
                      headers=headers,
                      json={
                          'name': name,
                          'internalName': get_internal_name(name),
                          'type': 'DECIMAL',
                          'control': 'TEXT',
                          'required': required
                      })
    check_request_status(r)
    custom_field_id = r.json()['result']
    logger.debug('custom_field_id = %s', custom_field_id)
    add_constant('transaction_custom_fields', name, custom_field_id)
    return custom_field_id


def add_custom_field_to_transfer_type(transfer_type_id, custom_field_id):
    logger.info("Ajout d'un champ personnalisé...")
    r = requests.post(eusko_web_services + 'transactionCustomField/addRelation',
                      headers=headers,
                      json=[transfer_type_id, custom_field_id])
    check_request_status(r)

ID_CHAMP_PERSO_PAIEMENT_BDC = create_transaction_custom_field_linked_user(
    name='BDC',
)
ID_CHAMP_PERSO_PAIEMENT_PORTEUR = create_transaction_custom_field_linked_user(
    name='Porteur',
)
ID_CHAMP_PERSO_PAIEMENT_ADHERENT = create_transaction_custom_field_linked_user(
    name='Adhérent',
)
ID_CHAMP_PERSO_PAIEMENT_ADHERENT_FACULTATIF = create_transaction_custom_field_linked_user(
    name='Adhérent (facultatif)',
    required=False,
)
ID_CHAMP_PERSO_PAIEMENT_MODE_DE_PAIEMENT = create_transaction_custom_field_single_selection(
    name='Mode de paiement',
    possible_values_name='payment_modes',
    possible_values=[
        'Chèque',
        'Espèces',
        'Paiement en ligne',
        'Prélèvement',
        'Virement',
    ],
)
ID_CHAMP_PERSO_PAIEMENT_PRODUIT = create_transaction_custom_field_single_selection(
    name='Produit',
    possible_values_name='products',
    possible_values=[
        'Foulard',
    ],
)
ID_CHAMP_PERSO_PAIEMENT_NUMERO_BORDEREAU = create_transaction_custom_field_text(
    name='Numéro de bordereau',
    required=False,
)
ID_CHAMP_PERSO_PAIEMENT_MONTANT_COTISATIONS = create_transaction_custom_field_decimal(
    name='Montant Cotisations',
)
ID_CHAMP_PERSO_PAIEMENT_MONTANT_VENTES = create_transaction_custom_field_decimal(
    name='Montant Ventes',
)
ID_CHAMP_PERSO_PAIEMENT_MONTANT_CHANGES_BILLET = create_transaction_custom_field_decimal(
    name='Montant Changes billet',
)
ID_CHAMP_PERSO_PAIEMENT_MONTANT_CHANGES_NUMERIQUE = create_transaction_custom_field_decimal(
    name='Montant Changes numérique',
)
ID_CHAMP_PERSO_PAIEMENT_NUMERO_TRANSACTION_BANQUE = create_transaction_custom_field_text(
    name='Numéro de transaction banque',
)
ID_CHAMP_PERSO_PAIEMENT_NUMERO_FACTURE = create_transaction_custom_field_text(
    name='Numéro de facture',
    unique=True,
)

all_transaction_fields = [
    ID_CHAMP_PERSO_PAIEMENT_BDC,
    ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
    ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
    ID_CHAMP_PERSO_PAIEMENT_ADHERENT_FACULTATIF,
    ID_CHAMP_PERSO_PAIEMENT_MODE_DE_PAIEMENT,
    ID_CHAMP_PERSO_PAIEMENT_PRODUIT,
    ID_CHAMP_PERSO_PAIEMENT_NUMERO_BORDEREAU,
    ID_CHAMP_PERSO_PAIEMENT_MONTANT_COTISATIONS,
    ID_CHAMP_PERSO_PAIEMENT_MONTANT_VENTES,
    ID_CHAMP_PERSO_PAIEMENT_MONTANT_CHANGES_BILLET,
    ID_CHAMP_PERSO_PAIEMENT_MONTANT_CHANGES_NUMERIQUE,
    ID_CHAMP_PERSO_PAIEMENT_NUMERO_TRANSACTION_BANQUE,
    ID_CHAMP_PERSO_PAIEMENT_NUMERO_FACTURE,
]


########################################################################
# Création des types de comptes.
#
# Note : La méthode save() de l'interface AccountTypeService prend en
# paramètre un objet de type AccountTypeDTO. AccountTypeDTO a deux
# sous-classes, SystemAccountTypeDTO et UserAccountTypeDTO. Lorsque l'on
# appelle la méthode save(), il faut passer en paramètre un objet du
# type adéquat (selon que l'on crée un compte système ou un compte
# utilisateur) et il faut indiquer explicitement quelle est la classe de
# l'objet passé en paramètre, sinon on se prend l'erreur suivante :
# java.lang.IllegalStateException: Could not instantiate bean of class
# org.cyclos.entities.banking.AccountType.
#
# Note: 'customFieldsForList' définit la liste des champs personnalisés
# visibles dans l'historique du compte. On ne fait pas dans le détail et
# et on donne la liste de tous les champs à chaque fois. Le résultat
# n'est pas terrible dans l'application web mais ce n'est pas grave.
def create_system_account_type(name, currency_id, limit_type):
    logger.info('Création du type de compte système "%s"...', name)
    params = {
        'class': 'org.cyclos.model.banking.accounttypes.SystemAccountTypeDTO',
        'name': name,
        'internalName': get_internal_name(name),
        'currency': currency_id,
        'limitType': limit_type,
        'customFieldsForList': all_transaction_fields,
    }
    if limit_type == 'LIMITED':
        params['creditLimit'] = 0
    r = requests.post(eusko_web_services + 'accountType/save',
                      headers=headers, json=params)
    check_request_status(r)
    account_type_id = r.json()['result']
    logger.debug('account_type_id = %s', account_type_id)
    add_constant('account_types', name, account_type_id)
    return account_type_id


def create_user_account_type(name, currency_id):
    logger.info('Création du type de compte utilisateur "%s"...', name)
    params = {
        'class': 'org.cyclos.model.banking.accounttypes.UserAccountTypeDTO',
        'name': name,
        'internalName': get_internal_name(name),
        'currency': currency_id,
        'customFieldsForList': all_transaction_fields,
    }
    r = requests.post(eusko_web_services + 'accountType/save',
                      headers=headers, json=params)
    check_request_status(r)
    account_type_id = r.json()['result']
    logger.debug('account_type_id = %s', account_type_id)
    add_constant('account_types', name, account_type_id)
    return account_type_id

# Comptes système pour l'eusko billet
ID_COMPTE_DE_DEBIT_EUSKO_BILLET = create_system_account_type(
    name='Compte de débit eusko billet',
    currency_id=ID_DEVISE_EUSKO,
    limit_type='UNLIMITED',
)
ID_STOCK_DE_BILLETS = create_system_account_type(
    name='Stock de billets',
    currency_id=ID_DEVISE_EUSKO,
    limit_type='LIMITED',
)
ID_COMPTE_DE_TRANSIT = create_system_account_type(
    name='Compte de transit',
    currency_id=ID_DEVISE_EUSKO,
    limit_type='LIMITED',
)
ID_COMPTE_DES_BILLETS_EN_CIRCULATION = create_system_account_type(
    name='Compte des billets en circulation',
    currency_id=ID_DEVISE_EUSKO,
    limit_type='LIMITED',
)
ID_COMPTE_DE_DEBIT_EURO = create_system_account_type(
    name='Compte de débit €',
    currency_id=ID_DEVISE_EURO,
    limit_type='UNLIMITED',
)

# Comptes des bureaux de change :
# - Stock de billets : stock d'eusko disponible pour le change (eusko
#   billet) et les retraits (eusko numérique)
# - Caisse € : € encaissés pour les changes, cotisations et ventes
# - Caisse eusko : eusko encaissés pour les cotisations et ventes
# - Retours d'eusko : eusko retournés par les prestataires pour les
#   reconvertir en € ou les déposer sur leur compte
ID_STOCK_DE_BILLETS_BDC = create_user_account_type(
    name='Stock de billets BDC',
    currency_id=ID_DEVISE_EUSKO,
)
ID_CAISSE_EURO_BDC = create_user_account_type(
    name='Caisse € BDC',
    currency_id=ID_DEVISE_EURO,
)
ID_CAISSE_EUSKO_BDC = create_user_account_type(
    name='Caisse eusko BDC',
    currency_id=ID_DEVISE_EUSKO,
)
ID_RETOURS_EUSKO_BDC = create_user_account_type(
    name="Retours d'eusko BDC",
    currency_id=ID_DEVISE_EUSKO,
)

# Comptes utilisateur pour la gestion interne des €
# - pour le Crédit Agricole et La Banque Postale
# - pour les 2 comptes dédiés (eusko billet et eusko numérique)
ID_BANQUE_DE_DEPOT = create_user_account_type(
    name='Banque de dépôt',
    currency_id=ID_DEVISE_EURO,
)
ID_COMPTE_DEDIE = create_user_account_type(
    name='Compte dédié',
    currency_id=ID_DEVISE_EURO,
)

# Comptes pour l'eusko numérique
ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE = create_system_account_type(
    name='Compte de débit eusko numérique',
    currency_id=ID_DEVISE_EUSKO,
    limit_type='UNLIMITED',
)
ID_COMPTE_ADHERENT = create_user_account_type(
    name="Compte d'adhérent",
    currency_id=ID_DEVISE_EUSKO,
)

all_system_accounts = [
    ID_COMPTE_DE_DEBIT_EUSKO_BILLET,
    ID_STOCK_DE_BILLETS,
    ID_COMPTE_DE_TRANSIT,
    ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
    ID_COMPTE_DE_DEBIT_EURO,
    ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
]
all_user_accounts = [
    ID_STOCK_DE_BILLETS_BDC,
    ID_CAISSE_EURO_BDC,
    ID_CAISSE_EUSKO_BDC,
    ID_RETOURS_EUSKO_BDC,
    ID_BANQUE_DE_DEPOT,
    ID_COMPTE_DEDIE,
    ID_COMPTE_ADHERENT,
]


########################################################################
# Création des "status flow" pour les paiements.
#
def create_transfer_status_flow(name):
    logger.info('Création du "status flow" "%s"...', name)
    r = requests.post(eusko_web_services + 'transferStatusFlow/save',
                      headers=headers,
                      json={
                          'name': name,
                          'internalName': get_internal_name(name),
                      })
    check_request_status(r)
    status_flow_id = r.json()['result']
    logger.debug('status_flow_id = %s', status_flow_id)
    add_constant('transfer_status_flows', name, status_flow_id)
    return status_flow_id


def create_transfer_status(name, status_flow, possible_next=None):
    logger.info('Création du statut "%s"...', name)
    status = {
        'name': name,
        'internalName': get_internal_name(name),
        'flow': status_flow,
    }
    if possible_next:
        status['possibleNext'] = possible_next
    r = requests.post(eusko_web_services + 'transferStatus/save',
                      headers=headers,
                      json=status)
    check_request_status(r)
    status_id = r.json()['result']
    logger.debug('status_id = %s', status_id)
    add_constant('transfer_statuses', name, status_id)
    return status_id

# Rapprochement : pour toutes les opérations pour lesquelles on
# souhaite faire des rapprochements.
ID_STATUS_FLOW_RAPPROCHEMENT = create_transfer_status_flow(
    name='Rapprochement',
)
ID_STATUS_RAPPROCHE = create_transfer_status(
    name='Rapproché',
    status_flow=ID_STATUS_FLOW_RAPPROCHEMENT,
)
ID_STATUS_A_RAPPROCHER = create_transfer_status(
    name='A rapprocher',
    status_flow=ID_STATUS_FLOW_RAPPROCHEMENT,
    possible_next=ID_STATUS_RAPPROCHE,
)

# Remise à Euskal Moneta : pour tous les paiements qui créditent les
# caisses €, eusko et retours d'eusko des bureaux de change.
ID_STATUS_FLOW_REMISE_A_EM = create_transfer_status_flow(
    name='Remise à Euskal Moneta',
)
ID_STATUS_REMIS = create_transfer_status(
    name='Remis à Euskal Moneta',
    status_flow=ID_STATUS_FLOW_REMISE_A_EM,
)
ID_STATUS_A_REMETTRE = create_transfer_status(
    name='A remettre à Euskal Moneta',
    status_flow=ID_STATUS_FLOW_REMISE_A_EM,
    possible_next=ID_STATUS_REMIS,
)

# Virements : pour les reconversions d'eusko en € (virement à faire au
# prestataire qui a reconverti) et pour les dépôts en banque (virements
# à faire vers les comptes dédiés).
ID_STATUS_FLOW_VIREMENTS = create_transfer_status_flow(
    name='Virements',
)
ID_STATUS_VIREMENTS_FAITS = create_transfer_status(
    name='Virements faits',
    status_flow=ID_STATUS_FLOW_VIREMENTS,
)
ID_STATUS_VIREMENTS_A_FAIRE = create_transfer_status(
    name='Virements à faire',
    status_flow=ID_STATUS_FLOW_VIREMENTS,
    possible_next=ID_STATUS_VIREMENTS_FAITS,
)

all_status_flows = [
    ID_STATUS_FLOW_RAPPROCHEMENT,
    ID_STATUS_FLOW_REMISE_A_EM,
    ID_STATUS_FLOW_VIREMENTS,
]


########################################################################
# Création des types de paiement.
#
# Le paramètre "direction" n'est pas nécessaire pour les types de
# paiement SYSTEM_TO_SYSTEM, SYSTEM_TO_USER et USER_TO_SYSTEM, car dans
# ces cas-là, les types de compte d'origine et de destination permettent
# de déduire la direction. Par contre, ce paramètre est requis pour les
# types de paiement de compte utilisateur à compte utilisateur car il
# peut alors prendre la valeur USER_TO_SELF ou USER_TO_USER et cela doit
# être défini explicitement.
# Du coup, je l'ai rendu toujours obligatoire. C'est discutable mais
# définir systématiquement la direction de manière explicite est
# intéressant car cela sert de documentation.
#
# On définit un "maxChargebackTime" de 2 mois, ce qui veut dire que le
# délai maximum pour rejeter un paiment est de 2 mois.
# Note : les paiements pourront être rejetés par les administrateurs du
# groupe "Gestion interne" (voir le paramétrage des permissions).
#
# Par souci de simplicité, tous les types de paiement sont accessibles
# par les 2 canaux "Main web" et "Web services". Ainsi tous les types
# de paiement seront accessibles par l'interface web de Cyclos pour les
# administrateurs du groupe "Gestion interne" (voir le paramétrage des
# permissions), ce qui garantit une capacité à intervenir si nécessaire.
# D'autre part, ils peuvent tous être utilisés par l'API Eusko (ce n'est
# pas forcément nécessaire mais c'est possible, il n'y aura pas de
# question à se poser.
#
def create_payment_transfer_type(name, direction, from_account_type_id,
                                 to_account_type_id, custom_fields=[],
                                 status_flows=[], initial_statuses=[],
                                 channels=[ID_CANAL_MAIN_WEB, ID_CANAL_WEB_SERVICES],
                                 principal_types=[]):
    logger.info('Création du type de paiement "%s"...', name)
    r = requests.post(eusko_web_services + 'transferType/save',
                      headers=headers,
                      json={
                          'class': 'org.cyclos.model.banking.transfertypes.PaymentTransferTypeDTO',
                          'name': name,
                          'internalName': get_internal_name(name),
                          'direction': direction,
                          'from': from_account_type_id,
                          'to': to_account_type_id,
                          'enabled': True,
                          'statusFlows': status_flows,
                          'initialStatuses': initial_statuses,
                          'maxChargebackTime': {'amount': '2', 'field': 'MONTHS'},
                          'channels': channels,
                          'principalTypes': principal_types,
                      })
    check_request_status(r)
    payment_transfer_type_id = r.json()['result']
    logger.debug('payment_transfer_type_id = %s', payment_transfer_type_id)
    add_constant('payment_types', name, payment_transfer_type_id)
    for custom_field_id in custom_fields:
        add_custom_field_to_transfer_type(
            transfer_type_id=payment_transfer_type_id,
            custom_field_id=custom_field_id,
        )
    return payment_transfer_type_id


def create_generated_transfer_type(name, direction, from_account_type_id,
                                   to_account_type_id):
    logger.info('Création du type de paiement "%s"...', name)
    r = requests.post(eusko_web_services + 'transferType/save',
                      headers=headers,
                      json={
                          'class': 'org.cyclos.model.banking.transfertypes.GeneratedTransferTypeDTO',
                          'name': name,
                          'internalName': get_internal_name(name),
                          'direction': direction,
                          'from': from_account_type_id,
                          'to': to_account_type_id,
                      })
    check_request_status(r)
    generated_transfer_type_id = r.json()['result']
    logger.debug('generated_transfer_type_id = %s', generated_transfer_type_id)
    return generated_transfer_type_id


def create_transfer_fee(name, original_transfer_type, generated_transfer_type,
                        other_currency, payer, receiver, charge_mode, amount):
    logger.info('Création des frais de transfert "%s"...', name)
    r = requests.post(eusko_web_services + 'transferFee/save',
                      headers=headers,
                      json={
                          'name': name,
                          'internalName': get_internal_name(name),
                          'enabled': True,
                          'originalTransferType': original_transfer_type,
                          'generatedTransferType': generated_transfer_type,
                          'otherCurrency': other_currency,
                          'payer': payer,
                          'receiver': receiver,
                          'chargeMode': charge_mode,
                          'amount': amount,
                      })
    check_request_status(r)
    transfer_fee_id = r.json()['result']
    logger.debug('transfer_fee_id = %s', transfer_fee_id)

# Types de paiement pour l'eusko billet
#
ID_TYPE_PAIEMENT_IMPRESSION_BILLETS = create_payment_transfer_type(
    name="Impression de billets d'eusko",
    direction='SYSTEM_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EUSKO_BILLET,
    to_account_type_id=ID_STOCK_DE_BILLETS,
)
ID_TYPE_PAIEMENT_DESTRUCTION_BILLETS = create_payment_transfer_type(
    name="Destruction de billets d'eusko",
    direction='SYSTEM_TO_SYSTEM',
    from_account_type_id=ID_STOCK_DE_BILLETS,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EUSKO_BILLET,
)
ID_TYPE_PAIEMENT_SORTIE_COFFRE = create_payment_transfer_type(
    name='Sortie coffre',
    direction='SYSTEM_TO_SYSTEM',
    from_account_type_id=ID_STOCK_DE_BILLETS,
    to_account_type_id=ID_COMPTE_DE_TRANSIT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
        ID_CHAMP_PERSO_PAIEMENT_BDC,
    ],
    status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
    ],
    initial_statuses=[
        ID_STATUS_A_RAPPROCHER,
    ],
)
ID_TYPE_PAIEMENT_ENTREE_COFFRE = create_payment_transfer_type(
    name='Entrée coffre',
    direction='SYSTEM_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_DE_TRANSIT,
    to_account_type_id=ID_STOCK_DE_BILLETS,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
        ID_CHAMP_PERSO_PAIEMENT_BDC,
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT_FACULTATIF,
    ],
)
ID_TYPE_PAIEMENT_ENTREE_STOCK_BDC = create_payment_transfer_type(
    name='Entrée stock BDC',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_TRANSIT,
    to_account_type_id=ID_STOCK_DE_BILLETS_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
    ],
)
ID_TYPE_PAIEMENT_SORTIE_STOCK_BDC = create_payment_transfer_type(
    name='Sortie stock BDC',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_STOCK_DE_BILLETS_BDC,
    to_account_type_id=ID_COMPTE_DE_TRANSIT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
    ],
    status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
    ],
    initial_statuses=[
        ID_STATUS_A_RAPPROCHER,
    ],
)
# Les eusko sortis de la Caisse eusko du BDC vont dans le compte des
# billets en circulation (dans la pratique, ces eusko rentrent dans la
# caisse eusko d'Euskal Moneta mais ce sont bien des eusko en
# circulation). Les sorties caisse sont initialement dans l'état
# "A rapprocher" et seront passées dans l'état "Rapproché" lorsque leur
# entrée dans la Caisse eusko d'E.M. sera validée.
ID_TYPE_PAIEMENT_SORTIE_CAISSE_EUSKO_BDC = create_payment_transfer_type(
    name='Sortie caisse eusko BDC',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_CAISSE_EUSKO_BDC,
    to_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
    ],
    status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
    ],
    initial_statuses=[
        ID_STATUS_A_RAPPROCHER,
    ],
)
ID_TYPE_PAIEMENT_SORTIE_RETOURS_EUSKO_BDC = create_payment_transfer_type(
    name='Sortie retours eusko BDC',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_RETOURS_EUSKO_BDC,
    to_account_type_id=ID_COMPTE_DE_TRANSIT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
    ],
    status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
    ],
    initial_statuses=[
        ID_STATUS_A_RAPPROCHER,
    ],
)
ID_TYPE_PAIEMENT_PERTE_DE_BILLETS = create_payment_transfer_type(
    name='Perte de billets',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_STOCK_DE_BILLETS_BDC,
    to_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
)
ID_TYPE_PAIEMENT_GAIN_DE_BILLETS = create_payment_transfer_type(
    name='Gain de billets',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
    to_account_type_id=ID_STOCK_DE_BILLETS_BDC,
)

# Change billets :
# Cette opération se fait en 2 temps :
# 1) l'adhérent(e) donne des € au BDC
# 2) le BDC donne des € à l'adhérent(e) : les eusko sortent du stock de
# billets du BDC et vont dans le compte système "Compte des billets en
# circulation". En effet, une fois donnés à l'adhérent(e), les eusko
# sont "dans la nature", on ne sait pas exactement ce qu'ils deviennent.
#
# Le paiement enregistré est le versement des € et cela génère
# automatiquement le paiement correspondant au fait de donner les eusko
# à l'adhérent(e). On utilise pour cela le mécanisme des frais de
# transaction. Les frais sont payés par le destinataire, çad le BDC, au
# système (le compte des billets en circulation). Ils correspondent à
# 100% du montant du paiement original.
ID_TYPE_PAIEMENT_CHANGE_BILLETS_VERSEMENT_DES_EUROS = create_payment_transfer_type(
    name='Change billets - Versement des €',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    to_account_type_id=ID_CAISSE_EURO_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
        ID_CHAMP_PERSO_PAIEMENT_MODE_DE_PAIEMENT,
    ],
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
    ],
)
ID_TYPE_PAIEMENT_CHANGE_BILLETS_VERSEMENT_DES_EUSKO = create_generated_transfer_type(
    name='Change billets - Versement des eusko',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_STOCK_DE_BILLETS_BDC,
    to_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
)
create_transfer_fee(
    name='Change billets - Versement des eusko',
    original_transfer_type=ID_TYPE_PAIEMENT_CHANGE_BILLETS_VERSEMENT_DES_EUROS,
    generated_transfer_type=ID_TYPE_PAIEMENT_CHANGE_BILLETS_VERSEMENT_DES_EUSKO,
    other_currency=True,
    payer='DESTINATION',
    receiver='SYSTEM',
    charge_mode='PERCENTAGE',
    amount=1.00,
)

ID_TYPE_PAIEMENT_RECONVERSION_BILLETS = create_payment_transfer_type(
    name='Reconversion billets - Versement des eusko',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
    to_account_type_id=ID_RETOURS_EUSKO_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
        ID_CHAMP_PERSO_PAIEMENT_NUMERO_FACTURE,
    ],
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
        ID_STATUS_FLOW_VIREMENTS,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
        ID_STATUS_VIREMENTS_A_FAIRE,
    ],
)
ID_TYPE_PAIEMENT_COTISATION_EN_EURO = create_payment_transfer_type(
    name='Cotisation en €',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    to_account_type_id=ID_CAISSE_EURO_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
        ID_CHAMP_PERSO_PAIEMENT_MODE_DE_PAIEMENT,
    ],
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
    ],
)
ID_TYPE_PAIEMENT_COTISATION_EN_EUSKO = create_payment_transfer_type(
    name='Cotisation en eusko',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
    to_account_type_id=ID_CAISSE_EUSKO_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
    ],
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
    ],
)
ID_TYPE_PAIEMENT_VENTE_EN_EURO = create_payment_transfer_type(
    name='Vente en €',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    to_account_type_id=ID_CAISSE_EURO_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PRODUIT,
        ID_CHAMP_PERSO_PAIEMENT_MODE_DE_PAIEMENT,
    ],
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
    ],
)
ID_TYPE_PAIEMENT_VENTE_EN_EUSKO = create_payment_transfer_type(
    name='Vente en eusko',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
    to_account_type_id=ID_CAISSE_EUSKO_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PRODUIT,
    ],
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
    ],
)

# Dépôt en banque :
# 1 type de paiement pour le dépôt proprement dit + 4 types de paiements
# pour régulariser les dépôts dont le montant ne correspond pas au
# montant calculé.
#
# Le dépôt proprement dit :
ID_TYPE_PAIEMENT_DEPOT_EN_BANQUE = create_payment_transfer_type(
    name='Dépôt en banque',
    direction='USER_TO_USER',
    from_account_type_id=ID_CAISSE_EURO_BDC,
    to_account_type_id=ID_BANQUE_DE_DEPOT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_MODE_DE_PAIEMENT,
        ID_CHAMP_PERSO_PAIEMENT_NUMERO_BORDEREAU,
        ID_CHAMP_PERSO_PAIEMENT_MONTANT_COTISATIONS,
        ID_CHAMP_PERSO_PAIEMENT_MONTANT_VENTES,
        ID_CHAMP_PERSO_PAIEMENT_MONTANT_CHANGES_BILLET,
        ID_CHAMP_PERSO_PAIEMENT_MONTANT_CHANGES_NUMERIQUE,
    ],
    status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
        ID_STATUS_FLOW_VIREMENTS,
    ],
    initial_statuses=[
        ID_STATUS_A_RAPPROCHER,
        ID_STATUS_VIREMENTS_A_FAIRE,
    ],
)
ID_TYPE_PAIEMENT_REGUL_DEPOT_INSUFFISANT = create_payment_transfer_type(
    direction='SYSTEM_TO_USER',
    name='Régularisation dépôt insuffisant',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    to_account_type_id=ID_BANQUE_DE_DEPOT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_BDC,
    ],
    status_flows=[
        ID_STATUS_FLOW_VIREMENTS,
    ],
    initial_statuses=[
        ID_STATUS_VIREMENTS_A_FAIRE,
    ],
)
ID_TYPE_PAIEMENT_BANQUE_VERS_CAISSE_EURO_BDC = create_payment_transfer_type(
    name='Paiement de Banque de dépôt vers Caisse € BDC',
    direction='USER_TO_USER',
    from_account_type_id=ID_BANQUE_DE_DEPOT,
    to_account_type_id=ID_CAISSE_EURO_BDC,
    status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    initial_statuses=[
        ID_STATUS_A_RAPPROCHER,
        ID_STATUS_A_REMETTRE,
    ],
)
ID_TYPE_PAIEMENT_CAISSE_EURO_BDC_VERS_BANQUE = create_payment_transfer_type(
    name='Paiement de Caisse € BDC vers Banque de dépôt',
    direction='USER_TO_USER',
    from_account_type_id=ID_CAISSE_EURO_BDC,
    to_account_type_id=ID_BANQUE_DE_DEPOT,
    status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
    ],
    initial_statuses=[
        ID_STATUS_A_RAPPROCHER,
    ],
)
ID_TYPE_PAIEMENT_REGUL_DEPOT_EXCESSIF = create_payment_transfer_type(
    name='Régularisation dépôt excessif',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_BANQUE_DE_DEPOT,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_BDC,
    ],
    status_flows=[
        ID_STATUS_FLOW_VIREMENTS,
    ],
    initial_statuses=[
        ID_STATUS_VIREMENTS_A_FAIRE,
    ],
)

# Type de paiement utilisé lorsqu'un BDC remet des espèces à Euskal
# Moneta suite à un refus de la banque de prendre ces espèces.
#
# Les € remis à E.M. vont dans le compte de débit et les opérations sont
# initialemnt dans l'état "A rapprocher", ce qui permettra de les
# valider (c'est le même fonctionnement que pour les sorties de la
# Caisse eusko des BDC).
ID_TYPE_PAIEMENT_REMISE_EUROS_EN_CAISSE = create_payment_transfer_type(
    name="Remise d'€ en caisse",
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_CAISSE_EURO_BDC,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
    ],
    initial_statuses=[
        ID_STATUS_A_RAPPROCHER,
    ],
)
# Paiement utilisé pour les virements depuis les banques de dépôt pour
# l'argent des cotisations, ventes, .... Dans la pratique, cet argent va
# sur le Compte de gestion d'Euskal Moneta mais ce compte n'existe pas
# dans Cyclos et on considère tout simplement que cet argent sort du
# système.
#
# Note : Le Compte de gestion d'Euskal Moneta n'existe pas dans Cyclos
# car il n'aurait donné qu'une vision partielle du Compte de gestion
# réel (celui qui se trouve au Crédit Coopératif). Plutôt que d'avoir un
# compte incomplet (toutes les opérations n'auraient pas été tracées
# dans Cyclos) et dans un état artificiel (le solde aurait été faux,
# complètement déconnecté de la réalité), il a été décidé de ne pas
# avoir ce compte dans Cyclos. Il est donc à l'extérieur du système et
# c'est le Compte de débit en € qui est utilisé pour les paiements qui
# dans la réalité font intervenir le Compte de gestion.
#
# Note 2 : Dans les noms des types de paiements ci-dessous on utilise
# "Compte débit €" et pas "le Compte de débit €" de façon à avoir un
# internalName ne dépassant pas 50 caractères (le internalName étant
# automatiquement généré à partir du nom).
ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DE_DEBIT = create_payment_transfer_type(
    name='Virement de Banque de dépôt vers Compte débit €',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_BANQUE_DE_DEPOT,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
)
# Type de paiement utilisé pour les virements depuis les banques de
# dépôt pour l'argent des changes.
ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DEDIE = create_payment_transfer_type(
    name='Virement de Banque de dépôt vers Compte dédié',
    direction='USER_TO_USER',
    from_account_type_id=ID_BANQUE_DE_DEPOT,
    to_account_type_id=ID_COMPTE_DEDIE,
)
# Type de paiement utilisé pour les virements de remboursement des
# reconversions.
ID_TYPE_PAIEMENT_COMPTE_DEDIE_VERS_COMPTE_DE_DEBIT = create_payment_transfer_type(
    name='Virement de Compte dédié vers Compte débit €',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_DEDIE,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
)

# Le type de paiement ci-dessous, "Virement entre comptes dédiés",
# permettra de régulariser la situation des 2 comptes dédiés lorsque
# des adhérents feront des dépôts de billets sur leur compte numérique
# ou des retraits de billets à partir de ce même compte.
ID_TYPE_PAIEMENT_VIREMENT_ENTRE_COMPTES_DEDIES = create_payment_transfer_type(
    name='Virement entre comptes dédiés',
    direction='USER_TO_USER',
    from_account_type_id=ID_COMPTE_DEDIE,
    to_account_type_id=ID_COMPTE_DEDIE,
)

# Les 2 types de paiement suivants sont utilisés lorsqu'un adhérent fait
# un paiement "en ligne" pour créditer son compte numérique.
# On parle ici de change "en ligne" par opposition à "dans un bureau
# de change". Il peut s'agir d'un paiement par prélèvement automatique,
# par virement ou par carte bleue (dans le cas de la VAD c'est-à-dire la
# vente à distance sur Internet).
# L'API Eusko doit générer ces 2 paiements de façon cohérente. Cela ne
# peut pas être géré dans le paramétrage avec des frais car il s'agit de
# 2 paiements de compte système à compte utilisateur, mais pour des
# utilisateurs différents (le compte dédié eusko numérique, et
# l'adhérent dont il faut créditer le compte).
# Le champ "Numéro de transaction banque" contient la référence du
# paiement bancaire réel en €.
ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_LIGNE_VERSEMENT_DES_EUROS = create_payment_transfer_type(
    name='Change numérique en ligne - Versement des €',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    to_account_type_id=ID_COMPTE_DEDIE,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_NUMERO_TRANSACTION_BANQUE,
    ],
)
ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_LIGNE_VERSEMENT_DES_EUSKO = create_payment_transfer_type(
    name='Change numérique en ligne - Versement des eusko',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
    to_account_type_id=ID_COMPTE_ADHERENT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_NUMERO_TRANSACTION_BANQUE,
    ],
)

# Ce type de paiement sera utilisé lorsqu'un adhérent fera un paiement
# en € dans un bureau de change pour créditer son compte numérique.
# Pour cette opération, l'API Eusko doit générer 2 paiements :
#  - un paiement "Change numérique en BDC - Versement des €"
#  - un paiement "Crédit du compte"
# C'est l'API qui doit générer ces 2 paiements de façon cohérente. Cela
# ne peut pas être géré dans le paramétrage avec des frais car il s'agit
# de 2 paiements de compte système à compte utilisateur, mais pour des
# utilisateurs différents (le BDC qui reçoit les €, et l'adhérent dont
# il faut créditer le compte).
ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_BDC = create_payment_transfer_type(
    name='Change numérique en BDC - Versement des €',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    to_account_type_id=ID_CAISSE_EURO_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
        ID_CHAMP_PERSO_PAIEMENT_MODE_DE_PAIEMENT,
    ],
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
    ],
)

ID_TYPE_PAIEMENT_RECONVERSION_NUMERIQUE = create_payment_transfer_type(
    name='Reconversion numérique',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_ADHERENT,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
    status_flows=[
        ID_STATUS_FLOW_VIREMENTS,
    ],
    initial_statuses=[
        ID_STATUS_VIREMENTS_A_FAIRE,
    ],
)

# Les 2 types de paiement ci-dessous seront utilisés lorsqu'un adhérent
# déposera des eusko billet dans un bureau de change pour créditer son
# compte numérique.
# Pour cette opération, l'API Eusko doit générer 2 paiements :
#  - un paiement "Dépôt de billets"
#  - un paiement "Crédit du compte"
# Note : voir le commentaire du type de paiement "Change numérique en
# BDC - Versement des €" pour l'explication sur pourquoi cela est fait
# de cette manière.
ID_TYPE_PAIEMENT_DEPOT_DE_BILLETS = create_payment_transfer_type(
    name='Dépôt de billets',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
    to_account_type_id=ID_RETOURS_EUSKO_BDC,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
    ],
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
        ID_STATUS_FLOW_VIREMENTS,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
        ID_STATUS_VIREMENTS_A_FAIRE,
    ],
)
ID_TYPE_PAIEMENT_CREDIT_DU_COMPTE = create_payment_transfer_type(
    name='Crédit du compte',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
    to_account_type_id=ID_COMPTE_ADHERENT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_BDC,
    ],
)

# Les 2 types de paiement ci-dessous seront utilisés lorsqu'un adhérent
# fera un retrait d'eusko billet (à partir de son compte numérique) dans
# un bureau de change.
# Pour cette opération, l'API Eusko doit générer 2 paiements :
#  - un paiement "Retrait de billets"
#  - un paiement "Retrait du compte"
# Note : c'est le même fonctionnement que pour le dépôt de billets.
#
# Attention, pour le retrait de billets, le compte d'origine est bien
# le stock de billets du bureau de change, et pas sa caisse eusko, car
# on n'a aucun contrôle sur l'approvisionnement de cette caisse eusko.
# Pour être certain que le BDC a des eusko lorsqu'un adhérent veut faire
# un retrait, il faut prendre ces eusko dans le stock de billets du BDC.
# Au départ, nous voulions que ce stock ne soit utilisé que pour le
# change, mais je ne vois pas comment faire autrement.
ID_TYPE_PAIEMENT_RETRAIT_DE_BILLETS = create_payment_transfer_type(
    name='Retrait de billets',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_STOCK_DE_BILLETS_BDC,
    to_account_type_id=ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_ADHERENT,
    ],
    status_flows=[
        ID_STATUS_FLOW_VIREMENTS,
    ],
    initial_statuses=[
        ID_STATUS_VIREMENTS_A_FAIRE,
    ],
)
ID_TYPE_PAIEMENT_RETRAIT_DU_COMPTE = create_payment_transfer_type(
    name='Retrait du compte',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_ADHERENT,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_BDC,
    ],
)

# Et enfin, les types de paiement les plus importants pour l'eusko
# numérique !
# On crée un type de paiement dédié pour le paiement par carte via le
# terminal de paiement, ce qui permettra de distinguer très facilement
# les paiements par virement via le site web des paiements par carte.
# Cela permettra aussi, éventuellement, de définir des règles
# particulières pour l'un ou l'autre de ces moyens de paiement.
ID_TYPE_PAIEMENT_VIREMENT_INTER_ADHERENT = create_payment_transfer_type(
    name='Virement inter-adhérent',
    direction='USER_TO_USER',
    from_account_type_id=ID_COMPTE_ADHERENT,
    to_account_type_id=ID_COMPTE_ADHERENT,
)
ID_TYPE_PAIEMENT_PAIEMENT_PAR_CARTE = create_payment_transfer_type(
    name='Paiement par carte',
    direction='USER_TO_USER',
    from_account_type_id=ID_COMPTE_ADHERENT,
    to_account_type_id=ID_COMPTE_ADHERENT,
    channels=[
        ID_CANAL_PAY_AT_POS,
    ],
    principal_types=[
        ID_TOKEN_CARTE_NFC,
    ],
)

# Types de paiement pour des régularisations entre caisses des BDC.
ID_TYPE_PAIEMENT_DE_STOCK_DE_BILLETS_BDC_VERS_RETOURS_EUSKO_BDC = create_payment_transfer_type(
    name="De Stock de billets BDC vers Retours d'eusko BDC",
    direction='USER_TO_SELF',
    from_account_type_id=ID_STOCK_DE_BILLETS_BDC,
    to_account_type_id=ID_RETOURS_EUSKO_BDC,
)
ID_TYPE_PAIEMENT_DE_RETOURS_EUSKO_BDC_VERS_STOCK_DE_BILLETS_BDC = create_payment_transfer_type(
    name="De Retours d'eusko BDC vers Stock de billets BDC",
    direction='USER_TO_SELF',
    from_account_type_id=ID_RETOURS_EUSKO_BDC,
    to_account_type_id=ID_STOCK_DE_BILLETS_BDC,
)


all_system_to_system_payments = [
    ID_TYPE_PAIEMENT_IMPRESSION_BILLETS,
    ID_TYPE_PAIEMENT_DESTRUCTION_BILLETS,
    ID_TYPE_PAIEMENT_SORTIE_COFFRE,
    ID_TYPE_PAIEMENT_ENTREE_COFFRE,
]
all_system_to_user_payments = [
    ID_TYPE_PAIEMENT_ENTREE_STOCK_BDC,
    ID_TYPE_PAIEMENT_GAIN_DE_BILLETS,
    ID_TYPE_PAIEMENT_CHANGE_BILLETS_VERSEMENT_DES_EUROS,
    ID_TYPE_PAIEMENT_RECONVERSION_BILLETS,
    ID_TYPE_PAIEMENT_COTISATION_EN_EURO,
    ID_TYPE_PAIEMENT_COTISATION_EN_EUSKO,
    ID_TYPE_PAIEMENT_VENTE_EN_EURO,
    ID_TYPE_PAIEMENT_VENTE_EN_EUSKO,
    ID_TYPE_PAIEMENT_REGUL_DEPOT_INSUFFISANT,
    ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_LIGNE_VERSEMENT_DES_EUROS,
    ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_LIGNE_VERSEMENT_DES_EUSKO,
    ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_BDC,
    ID_TYPE_PAIEMENT_DEPOT_DE_BILLETS,
    ID_TYPE_PAIEMENT_CREDIT_DU_COMPTE,
]
all_user_to_system_payments = [
    ID_TYPE_PAIEMENT_SORTIE_STOCK_BDC,
    ID_TYPE_PAIEMENT_SORTIE_CAISSE_EUSKO_BDC,
    ID_TYPE_PAIEMENT_SORTIE_RETOURS_EUSKO_BDC,
    ID_TYPE_PAIEMENT_PERTE_DE_BILLETS,
    ID_TYPE_PAIEMENT_REGUL_DEPOT_EXCESSIF,
    ID_TYPE_PAIEMENT_REMISE_EUROS_EN_CAISSE,
    ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DE_DEBIT,
    ID_TYPE_PAIEMENT_COMPTE_DEDIE_VERS_COMPTE_DE_DEBIT,
    ID_TYPE_PAIEMENT_RECONVERSION_NUMERIQUE,
    ID_TYPE_PAIEMENT_RETRAIT_DE_BILLETS,
    ID_TYPE_PAIEMENT_RETRAIT_DU_COMPTE,
]
all_user_to_user_payments = [
    ID_TYPE_PAIEMENT_DEPOT_EN_BANQUE,
    ID_TYPE_PAIEMENT_BANQUE_VERS_CAISSE_EURO_BDC,
    ID_TYPE_PAIEMENT_CAISSE_EURO_BDC_VERS_BANQUE,
    ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DEDIE,
    ID_TYPE_PAIEMENT_VIREMENT_ENTRE_COMPTES_DEDIES,
    ID_TYPE_PAIEMENT_VIREMENT_INTER_ADHERENT,
    ID_TYPE_PAIEMENT_PAIEMENT_PAR_CARTE,
]
all_user_to_self_payments = [
    ID_TYPE_PAIEMENT_DE_STOCK_DE_BILLETS_BDC_VERS_RETOURS_EUSKO_BDC,
    ID_TYPE_PAIEMENT_DE_RETOURS_EUSKO_BDC_VERS_STOCK_DE_BILLETS_BDC,
]
all_payments_to_system = \
    all_system_to_system_payments \
    + all_user_to_system_payments
all_payments_to_user = \
    all_system_to_user_payments \
    + all_user_to_user_payments \
    + all_user_to_self_payments


########################################################################
# Création des champs personnalisés pour les profils utilisateur.
#
def create_user_custom_field_linked_user(name, required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(eusko_web_services + 'userCustomField/save',
                      headers=headers,
                      json={
                          'name': name,
                          'internalName': get_internal_name(name),
                          'type': 'LINKED_ENTITY',
                          'linkedEntityType': 'USER',
                          'control': 'ENTITY_SELECTION',
                          'required': required
                      })
    check_request_status(r)
    custom_field_id = r.json()['result']
    logger.debug('custom_field_id = %s', custom_field_id)
    add_constant('user_custom_fields', name, custom_field_id)
    return custom_field_id


ID_CHAMP_PERSO_UTILISATEUR_BDC = create_user_custom_field_linked_user(
    name='BDC',
)


########################################################################
# Création des produits et des groupes.
#
# Les produits servent à gérer les permissions et les règles d'accès, et
# à attribuer des types de compte aux utilisateurs.
#
# Un groupe de nature Administrateur est associé à un unique produit, de
# nature Administrateur, et qui est créé automatiquement lors de la
# création du groupe. C'est dans ce produit que sont définies les
# permissions et les règles d'accès du groupe.
#
# Au contraire, un groupe de nature Membre peut être associé à plusieurs
# produits (de nature Membre) mais aucun n'est créé automatiquement. Là
# encore, c'est via les produits que les permissions et les règles
# d'accès sont définies. Si plusieurs produits sont associés à un
# groupe, les permissions se cumulent.
# Un produit de nature Membre ne peut être lié qu'à un seul type de
# compte utilisateur. Chaque utilisateur appartenant à un groupe associé
# à ce produit aura un compte de ce type.
# Si on veut attribuer plusieurs comptes à des utilisateurs (c'est notre
# cas pour les bureaux de change), il faut créer un produit pour chaque
# type de compte utilisateur et associer tous ces produits au groupe des
# utilisateurs.
#
# Note: Tous les utilisateurs ont un nom et un login, même ceux qui ne
# peuvent pas se connecter à Cyclos (par exemple les utilisateurs des
# groupes "Bureaux de change", "Banques de dépôt" ou "Porteurs"). Comme
# Cyclos vérifie l'unicité du login, cela rend impossible la création de
# doublons (c'est donc une mesure de protection).
def create_member_product(name,
                          my_profile_fields=[],
                          accessible_user_groups=[],
                          other_users_profile_fields={},
                          user_account_type_id=None,
                          dashboard_actions=[],
                          password_actions=[],
                          my_access_clients=[],
                          my_token_types=[],
                          system_payments=[],
                          user_payments=[],
                          receive_payments=[]):
    logger.info('Création du produit "%s"...', name)
    # On commence par créer le produit avec les propriétés de base.
    product = {
        'class': 'org.cyclos.model.users.products.MemberProductDTO',
        'name': name,
        'internalName': get_internal_name(name),
        # Workaround of a bug in Cyclos 4.6.
        'myRecordTypeFields': [],
    }
    if user_account_type_id:
        product['userAccount'] = user_account_type_id
        product['accountAccessibility'] = 'ALWAYS'
    r = requests.post(eusko_web_services + 'product/save',
                      headers=headers,
                      json=product)
    check_request_status(r)
    product_id = r.json()['result']
    logger.debug('product_id = %s', product_id)
    # Ensuite on charge le produit pour pouvoir le modifier.
    r = requests.get(
        eusko_web_services + 'product/load/' + product_id,
        headers=headers
    )
    check_request_status(r)
    product = r.json()['result']
    # On modifie les paramètres du produit puis on l'enregistre.
    for field in product['myProfileFields']:
        if field['profileField'] in my_profile_fields:
            field['enabled'] = True
            field['editableAtRegistration'] = True
            field['visible'] = True
            field['editable'] = True
    # Par défaut un utilisateur peut accéder à son propre groupe. C'est
    # nécessaire pour qu'un utilisateur soit capable de voir dans quel
    # groupe lui-même se trouve (voir aussi 'groupVisibility' plus bas).
    if not accessible_user_groups:
        product['userGroupAccessibility'] = 'OWN_GROUP'
    else:
        product['userGroupAccessibility'] = 'SPECIFIC'
        product['accessibleUserGroups'] = accessible_user_groups
        product['searchUsersOnGroups'] = 'ALL'
    # Permettre de voir le group dans lequel un utilisateur se trouve
    # (s'applique aussi à soi-même).
    product['groupVisibility'] = 'GROUP'
    for field in product['userProfileFields']:
        key = field['profileField']
        try:
            if key in other_users_profile_fields:
                field['visible'] = True
                field['userKeywords'] = other_users_profile_fields[key]
        except TypeError:
            # Pour les champs de profil personnalisés (comme 'BDC'),
            # 'profileField' n'est une string mais un dictionnaire et
            # un TypeError est balancé. On ignore l'erreur car on ne
            # traite ici que les champs de profil standards.
            pass
    for dashboard_action in product['dashboardActions']:
        if dashboard_action['dashboardAction'] in dashboard_actions:
            dashboard_action['enabled'] = True
            dashboard_action['enabledByDefault'] = True
    for password_action in product['passwordActions']:
        if password_action['passwordType']['internalName'] in password_actions:
            password_action['change'] = True
    for access_client in product['myAccessClients']:
        if access_client['accessClientType']['id'] in my_access_clients:
            access_client['enable'] = True
            access_client['view'] = True
    for token_type in product['myTokenTypes']:
        if token_type['tokenType']['id'] in my_token_types:
            token_type['enable'] = True
            token_type['block'] = True
            token_type['unblock'] = True
    product['systemPayments'] = system_payments
    product['userPayments'] = user_payments
    product['receivePayments'] = receive_payments
    r = requests.post(eusko_web_services + 'product/save',
                      headers=headers,
                      json=product)
    check_request_status(r)
    return product_id


def assign_product_to_group(product_id, group_id):
    logger.info("Affectation du produit à un groupe...")
    r = requests.post(eusko_web_services + 'productsGroup/assign',
                      headers=headers,
                      json=[product_id, group_id])
    check_request_status(r)


def get_admin_product(group_id):
    r = requests.get(eusko_web_services + 'group/load/' + group_id,
                     headers=headers,
                     json={})
    check_request_status(r)
    product_id = r.json()['result']['adminProduct']['id']
    return product_id


def set_admin_group_permissions(
        group_id,
        my_profile_fields=[],
        password_actions=[],
        visible_transaction_fields=[],
        transfer_status_flows=[],
        system_accounts=[],
        system_to_system_payments=[],
        system_to_user_payments=[],
        chargeback_of_payments_to_system=[],
        accessible_user_groups=[],
        accessible_administrator_groups=[],
        user_profile_fields=[],
        change_group='NONE',
        user_registration=False,
        blocked_users_manage=False,
        disabled_users='NONE',
        removed_users='NONE',
        user_password_actions=[],
        user_token_types=[],
        user_access_clients=[],
        access_user_accounts=[],
        payments_as_user_to_user=[],
        payments_as_user_to_system=[],
        payments_as_user_to_self=[],
        chargeback_of_payments_to_user=[]):
    # Récupération de l'id du produit de ce groupe.
    product_id = get_admin_product(group_id)
    # Chargement du produit
    r = requests.get(eusko_web_services + 'product/load/' + product_id,
                     headers=headers,
                     json={})
    check_request_status(r)
    product = r.json()['result']
    # Plusieurs champs de profil sont activés par défaut et on doit les
    # désactiver si on n'en veut pas.
    for profile_field in product['myProfileFields']:
        field = profile_field['profileField']
        if isinstance(field, stringType):
            enable = field in my_profile_fields
        elif isinstance(field, dict):
            enable = field['id'] in my_profile_fields
        profile_field['enabled'] = enable
        profile_field['editableAtRegistration'] = enable
        profile_field['visible'] = enable
        profile_field['editable'] = enable
    # Par défaut tous les types de mot de passe sont présents et aucune
    # action n'est activée. Pour les types voulus, on active les actions
    # 'Change' (modifier le mot de passe) et 'At registration' (définir
    # le mot de passe lors de l'enregistrement de l'utilisateur).
    for password_action in product['passwordActions']:
        if password_action['passwordType']['internalName'] in password_actions:
            password_action['change'] = True
            password_action['atRegistration'] = True
    product['visibleTransactionFields'] = visible_transaction_fields
    # Status flows.
    for product_transfer_status_flow in product['transferStatusFlows']:
        if product_transfer_status_flow['flow']['id'] in transfer_status_flows:
            product_transfer_status_flow['visible'] = True
            product_transfer_status_flow['editable'] = True
    product['systemAccounts'] = system_accounts
    product['systemToSystemPayments'] = system_to_system_payments
    product['systemToUserPayments'] = system_to_user_payments
    product['chargebackPaymentsToSystem'] = chargeback_of_payments_to_system
    if accessible_user_groups:
        product['userGroupAccessibility'] = 'SPECIFIC'
        product['accessibleUserGroups'] = accessible_user_groups
    if accessible_administrator_groups:
        product['adminGroupAccessibility'] = 'SPECIFIC'
        product['accessibleAdminGroups'] = accessible_administrator_groups
    for profile_field in product['userProfileFields']:
        field = profile_field['profileField']
        if isinstance(field, stringType):
            enable = field in user_profile_fields
        elif isinstance(field, dict):
            enable = field['id'] in user_profile_fields
        profile_field['visible'] = enable
        profile_field['editable'] = enable
    product['userGroup'] = change_group
    product['userRegistration'] = user_registration
    product['blockedUsersManage'] = blocked_users_manage
    product['disabledUsers'] = disabled_users
    product['removedUsers'] = removed_users
    # Actions possibles sur les mots de passe des autres utilisateurs :
    # le principe est le même que pour les 'passwordActions' sauf que
    # l'on n'active que l'action 'Change'.
    for password_action in product['userPasswordActions']:
        if password_action['passwordType']['internalName'] in user_password_actions:
            password_action['change'] = True
            password_action['reset'] = True
            password_action['unblock'] = True
    for token_type in product['userTokenTypes']:
        if token_type['tokenType']['id'] in user_token_types:
            token_type['view'] = True
            token_type['block'] = True
            token_type['unblock'] = True
            token_type['cancel'] = True
            token_type['initialize'] = True
            token_type['personalize'] = True
            token_type['changeDates'] = True
    for access_client in product['userAccessClients']:
        if access_client['accessClientType']['id'] in user_access_clients:
            access_client['view'] = True
            access_client['manage'] = True
            access_client['block'] = True
            access_client['unblock'] = True
            access_client['activate'] = True
            access_client['unassign'] = True
    product['userAccountsAccess'] = access_user_accounts
    product['userPaymentsAsUser'] = payments_as_user_to_user
    product['systemPaymentsAsUser'] = payments_as_user_to_system
    product['selfPaymentsAsUser'] = payments_as_user_to_self
    product['chargebackPaymentsToUser'] = chargeback_of_payments_to_user
    # Enregistrement du produit modifié
    r = requests.post(eusko_web_services + 'product/save',
                      headers=headers,
                      json=product)
    check_request_status(r)


# TODO factoriser le code de ces 2 fonctions si elles restent telles quelles
# create_group(nature = 'ADMIN' ou 'MEMBER', name)
def create_admin_group(name):
    logger.info('Création du groupe Administrateur "%s"...', name)
    r = requests.post(eusko_web_services + 'group/save',
                      headers=headers,
                      json={
                          'class': 'org.cyclos.model.users.groups.AdminGroupDTO',
                          'name': name,
                          'internalName': get_internal_name(name),
                          'initialUserStatus': 'ACTIVE',
                          'enabled': True
                      })
    check_request_status(r)
    group_id = r.json()['result']
    logger.debug('group_id = %s', group_id)
    add_constant('groups', name, group_id)
    return group_id


def create_member_group(name,
                        initial_user_status='ACTIVE',
                        products=[]):
    logger.info('Création du groupe Membre "%s"...', name)
    r = requests.post(eusko_web_services + 'group/save',
                      headers=headers,
                      json={
                          'class': 'org.cyclos.model.users.groups.MemberGroupDTO',
                          'name': name,
                          'internalName': get_internal_name(name),
                          'initialUserStatus': initial_user_status,
                          'enabled': True
                      })
    check_request_status(r)
    group_id = r.json()['result']
    logger.debug('group_id = %s', group_id)
    add_constant('groups', name, group_id)
    for product_id in products:
        assign_product_to_group(product_id, group_id)
    return group_id


def change_group_configuration(group_id, configuration_id):
    logger.info("Affectation d'une nouvelle configuration à un groupe...")
    r = requests.post(eusko_web_services + 'group/changeConfiguration',
                      headers=headers,
                      json=[group_id, configuration_id])
    check_request_status(r)


# Gestion interne :
# Les membres de ce groupe ont accès à l'application de gestion interne.
# Ils ont aussi accès à Cyclos, où ils ont toutes les permissions, ce
# qui leur permet d'intervenir au-delà de ce que permet l'application de
# gestion interne (par exemple pour annuler un paiement).
ID_GROUPE_GESTION_INTERNE = create_admin_group(
    name='Gestion interne',
)
change_group_configuration(ID_GROUPE_GESTION_INTERNE,
                           ID_CONFIG_GESTION_INTERNE)

# Opérateurs BDC :
# Les membres de ce groupe ont accès à l'application des bureaux de
# change. Ils ont aussi accès à Cyclos, où ils n'ont que les permissions
# correspondant aux opérations qu'ils peuvent faire dans l'application
# BDC (ils ne peuvent rien faire de plus).
# Un utilisateur est créé dans ce groupe pour chaque bureau de change,
# et lié à l'utilisateur "Bureau de change" correspondant.
ID_GROUPE_OPERATEURS_BDC = create_admin_group(
    name='Opérateurs BDC',
)
change_group_configuration(ID_GROUPE_OPERATEURS_BDC,
                           ID_CONFIG_OPERATEURS_BDC)

# Anonyme :
# Ce groupe ne va contenir qu'un utilisateur : l'utilisateur "anonyme"
# que l'API va utiliser à chaque fois qu'elle devra faire des requêtes
# sans qu'un "vrai" utilisateur ne soit authentifié (par exemple, lors
# de la 1ère connexion d'un adhérent à l'application Compte en ligne).
ID_GROUPE_ANONYME = create_admin_group(
    name='Anonyme',
)

# Bureaux de change :
# Un utilisateur est créé dans ce groupe pour chaque bureau de change
# (c'est cet utilisateur qui possèdes les comptes du BDC, par contre
# toutes les opérations sont faites par l'opérateur BDC associé).
ID_PRODUIT_STOCK_DE_BILLETS_BDC = create_member_product(
    name='Stock de billets BDC',
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    user_account_type_id=ID_STOCK_DE_BILLETS_BDC,
)
ID_PRODUIT_CAISSE_EURO_BDC = create_member_product(
    name='Caisse € BDC',
    user_account_type_id=ID_CAISSE_EURO_BDC,
)
ID_PRODUIT_CAISSE_EUSKO_BDC = create_member_product(
    name='Caisse eusko BDC',
    user_account_type_id=ID_CAISSE_EUSKO_BDC,
)
ID_PRODUIT_RETOURS_EUSKO_BDC = create_member_product(
    name="Retours d'eusko BDC",
    user_account_type_id=ID_RETOURS_EUSKO_BDC,
)
ID_GROUPE_BUREAUX_DE_CHANGE = create_member_group(
    name='Bureaux de change',
    products=[
        ID_PRODUIT_STOCK_DE_BILLETS_BDC,
        ID_PRODUIT_CAISSE_EURO_BDC,
        ID_PRODUIT_CAISSE_EUSKO_BDC,
        ID_PRODUIT_RETOURS_EUSKO_BDC,
    ]
)

# Banques de dépôt.
ID_PRODUIT_BANQUE_DE_DEPOT = create_member_product(
    name='Banque de dépôt',
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    user_account_type_id=ID_BANQUE_DE_DEPOT,
)
ID_GROUPE_BANQUES_DE_DEPOT = create_member_group(
    name='Banques de dépôt',
    products=[
        ID_PRODUIT_BANQUE_DE_DEPOT,
    ]
)

# Comptes dédiés.
ID_PRODUIT_COMPTE_DEDIE = create_member_product(
    name='Compte dédié',
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    user_account_type_id=ID_COMPTE_DEDIE,
)
ID_GROUPE_COMPTES_DEDIES = create_member_group(
    name='Comptes dédiés',
    products=[
        ID_PRODUIT_COMPTE_DEDIE,
    ]
)

# Adhérents : On crée d'abord les 2 groupes car on en a besoin pour
# définir les permissions (autrement dit pour créer les produits).
prestataires = 'Adhérents prestataires'
utilisateurs = 'Adhérents utilisateurs'
ID_GROUPE_ADHERENTS_PRESTATAIRES = create_member_group(
    name=prestataires,
    initial_user_status='DISABLED',
)
ID_GROUPE_ADHERENTS_UTILISATEURS = create_member_group(
    name=utilisateurs,
    initial_user_status='DISABLED',
)

# Permissions pour les prestataires.
ID_PRODUIT_ADHERENTS_PRESTATAIRES = create_member_product(
    name=prestataires,
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
        'ACCOUNT_NUMBER',
    ],
    accessible_user_groups=[
        ID_GROUPE_ADHERENTS_PRESTATAIRES,
        ID_GROUPE_ADHERENTS_UTILISATEURS,
    ],
    other_users_profile_fields={
        'FULL_NAME': False,
        'LOGIN_NAME': True,
        'ACCOUNT_NUMBER': True,
    },
    user_account_type_id=ID_COMPTE_ADHERENT,
    dashboard_actions=[
        'ACCOUNT_INFO',
        'PAYMENT_USER_TO_USER',
        'PAYMENT_USER_TO_SYSTEM',
    ],
    password_actions=[
        'login',
        'pin',
    ],
    my_access_clients=[
        ID_CLIENT_POINT_DE_VENTE_NFC,
    ],
    my_token_types=[
        ID_TOKEN_CARTE_NFC,
    ],
    system_payments=[
        ID_TYPE_PAIEMENT_RECONVERSION_NUMERIQUE,
    ],
    user_payments=[
        ID_TYPE_PAIEMENT_VIREMENT_INTER_ADHERENT,
        ID_TYPE_PAIEMENT_PAIEMENT_PAR_CARTE,
    ],
    receive_payments=[
        ID_TYPE_PAIEMENT_PAIEMENT_PAR_CARTE,
    ],
)
assign_product_to_group(ID_PRODUIT_ADHERENTS_PRESTATAIRES,
                        ID_GROUPE_ADHERENTS_PRESTATAIRES)

# Permissions pour les utilisateurs.
ID_PRODUIT_ADHERENTS_UTILISATEURS = create_member_product(
    name=utilisateurs,
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
        'ACCOUNT_NUMBER',
    ],
    accessible_user_groups=[
        ID_GROUPE_ADHERENTS_PRESTATAIRES,
        ID_GROUPE_ADHERENTS_UTILISATEURS,
    ],
    other_users_profile_fields={
        'FULL_NAME': False,
        'LOGIN_NAME': True,
        'ACCOUNT_NUMBER': True,
    },
    user_account_type_id=ID_COMPTE_ADHERENT,
    dashboard_actions=[
        'ACCOUNT_INFO',
        'PAYMENT_USER_TO_USER',
        'PAYMENT_USER_TO_SYSTEM',
    ],
    password_actions=[
        'login',
        'pin',
    ],
    my_token_types=[
        ID_TOKEN_CARTE_NFC,
    ],
    user_payments=[
        ID_TYPE_PAIEMENT_VIREMENT_INTER_ADHERENT,
        ID_TYPE_PAIEMENT_PAIEMENT_PAR_CARTE,
    ],
)
assign_product_to_group(ID_PRODUIT_ADHERENTS_UTILISATEURS,
                        ID_GROUPE_ADHERENTS_UTILISATEURS)

# Produit pour tous les groupes d'utilisateurs qui n'auront pas de
# compte.
ID_PRODUIT_UTILISATEURS_BASIQUES_SANS_COMPTE = create_member_product(
    name='Utilisateurs basiques sans compte',
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    password_actions=[
        'login',
    ],
)
# Porteurs.
ID_GROUPE_PORTEURS = create_member_group(
    name='Porteurs',
    products=[
        ID_PRODUIT_UTILISATEURS_BASIQUES_SANS_COMPTE,
    ]
)
# Adhérents sans compte.
ID_GROUPE_ADHERENTS_SANS_COMPTE = create_member_group(
    name='Adhérents sans compte',
    initial_user_status='DISABLED',
    products=[
        ID_PRODUIT_UTILISATEURS_BASIQUES_SANS_COMPTE,
    ]
)

all_user_groups = [
    ID_GROUPE_BUREAUX_DE_CHANGE,
    ID_GROUPE_BANQUES_DE_DEPOT,
    ID_GROUPE_COMPTES_DEDIES,
    ID_GROUPE_ADHERENTS_PRESTATAIRES,
    ID_GROUPE_ADHERENTS_UTILISATEURS,
    ID_GROUPE_PORTEURS,
    ID_GROUPE_ADHERENTS_SANS_COMPTE,
]

# Définition des permissions.
# Il faut faire ça en dernier car nous avons besoin de tous les objets
# créés auparavant.
#
# Permissions pour le groupe "Gestion interne":
set_admin_group_permissions(
    group_id=ID_GROUPE_GESTION_INTERNE,
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    password_actions=[
        'login',
    ],
    visible_transaction_fields=all_transaction_fields,
    transfer_status_flows=all_status_flows,
    system_accounts=all_system_accounts,
    system_to_system_payments=all_system_to_system_payments,
    system_to_user_payments=all_system_to_user_payments,
    chargeback_of_payments_to_system=all_payments_to_system,
    accessible_user_groups=all_user_groups,
    accessible_administrator_groups=[
        ID_GROUPE_OPERATEURS_BDC,
    ],
    user_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
        'ACCOUNT_NUMBER',
        ID_CHAMP_PERSO_UTILISATEUR_BDC,
    ],
    change_group='MANAGE',
    user_registration=True,
    blocked_users_manage=True,
    disabled_users='MANAGE',
    removed_users='MANAGE',
    user_password_actions=[
        'login',
        'pin',
    ],
    user_token_types=all_token_types,
    user_access_clients=all_access_clients,
    access_user_accounts=all_user_accounts,
    payments_as_user_to_user=all_user_to_user_payments,
    payments_as_user_to_system=all_user_to_system_payments,
    payments_as_user_to_self=all_user_to_self_payments,
    chargeback_of_payments_to_user=all_payments_to_user
)
# Permissions pour le groupe "Opérateurs BDC":
set_admin_group_permissions(
    group_id=ID_GROUPE_OPERATEURS_BDC,
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
        ID_CHAMP_PERSO_UTILISATEUR_BDC,
    ],
    password_actions=[
        'login',
    ],
    visible_transaction_fields=all_transaction_fields,
    transfer_status_flows=[
        ID_STATUS_FLOW_RAPPROCHEMENT,
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    system_accounts=[
        ID_COMPTE_DE_TRANSIT,
        ID_COMPTE_DES_BILLETS_EN_CIRCULATION,
        ID_COMPTE_DE_DEBIT_EURO,
        ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
    ],
    system_to_user_payments=[
        ID_TYPE_PAIEMENT_ENTREE_STOCK_BDC,
        ID_TYPE_PAIEMENT_CHANGE_BILLETS_VERSEMENT_DES_EUROS,
        ID_TYPE_PAIEMENT_RECONVERSION_BILLETS,
        ID_TYPE_PAIEMENT_COTISATION_EN_EURO,
        ID_TYPE_PAIEMENT_COTISATION_EN_EUSKO,
        ID_TYPE_PAIEMENT_VENTE_EN_EURO,
        ID_TYPE_PAIEMENT_VENTE_EN_EUSKO,
        ID_TYPE_PAIEMENT_REGUL_DEPOT_INSUFFISANT,
        ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_BDC,
        ID_TYPE_PAIEMENT_DEPOT_DE_BILLETS,
        ID_TYPE_PAIEMENT_CREDIT_DU_COMPTE,
    ],
    accessible_user_groups=all_user_groups,
    accessible_administrator_groups=[
        ID_GROUPE_OPERATEURS_BDC,
    ],
    user_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
        'ACCOUNT_NUMBER',
    ],
    user_registration=True,
    disabled_users='VIEW',
    access_user_accounts=[
        ID_STOCK_DE_BILLETS_BDC,
        ID_CAISSE_EURO_BDC,
        ID_CAISSE_EUSKO_BDC,
        ID_RETOURS_EUSKO_BDC,
        ID_BANQUE_DE_DEPOT,
        ID_COMPTE_ADHERENT,
    ],
    payments_as_user_to_user=[
        ID_TYPE_PAIEMENT_DEPOT_EN_BANQUE,
        ID_TYPE_PAIEMENT_BANQUE_VERS_CAISSE_EURO_BDC,
        ID_TYPE_PAIEMENT_CAISSE_EURO_BDC_VERS_BANQUE,
    ],
    payments_as_user_to_system=[
        ID_TYPE_PAIEMENT_SORTIE_STOCK_BDC,
        ID_TYPE_PAIEMENT_SORTIE_CAISSE_EUSKO_BDC,
        ID_TYPE_PAIEMENT_SORTIE_RETOURS_EUSKO_BDC,
        ID_TYPE_PAIEMENT_REGUL_DEPOT_EXCESSIF,
        ID_TYPE_PAIEMENT_REMISE_EUROS_EN_CAISSE,
        ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DE_DEBIT,
        ID_TYPE_PAIEMENT_RETRAIT_DE_BILLETS,
        ID_TYPE_PAIEMENT_RETRAIT_DU_COMPTE,
    ],
)
# Permissions pour le groupe "Anonyme":
set_admin_group_permissions(
    group_id=ID_GROUPE_ANONYME,
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    password_actions=[
        'login',
    ],
    visible_transaction_fields=[
        ID_CHAMP_PERSO_PAIEMENT_NUMERO_TRANSACTION_BANQUE,
    ],
    system_accounts=[
        ID_COMPTE_DE_DEBIT_EURO,
        ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
    ],
    system_to_user_payments=[
        ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_LIGNE_VERSEMENT_DES_EUROS,
        ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_LIGNE_VERSEMENT_DES_EUSKO,
    ],
    accessible_user_groups=[
        ID_GROUPE_ADHERENTS_PRESTATAIRES,
        ID_GROUPE_ADHERENTS_UTILISATEURS,
        ID_GROUPE_ADHERENTS_SANS_COMPTE,
    ],
    user_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    change_group='MANAGE',
    disabled_users='MANAGE',
    user_password_actions=[
        'login',
    ],
)


########################################################################
# Création des utilisateurs pour les comptes dédiés.
#
def create_user(group, name, login):
    logger.info('Création de l\'utilisateur "%s"...', name)
    r = requests.post(eusko_web_services + 'user/register',
                      headers=headers,
                      json={
                          'group': group,
                          'name': name,
                          'username': login,
                          'skipActivationEmail': True,
                      })
    check_request_status(r)
    user_id = r.json()['result']['user']['id']
    logger.debug('user_id = %s', user_id)
    add_constant('users', name, user_id)
    return user_id

create_user(
    group=ID_GROUPE_COMPTES_DEDIES,
    name='Compte dédié eusko billet',
    login='CD_BILLET',
)
create_user(
    group=ID_GROUPE_COMPTES_DEDIES,
    name='Compte dédié eusko numérique',
    login='CD_NUMERIQUE',
)


########################################################################
# Récupération de la liste des types de mot de passe.
r = requests.get(eusko_web_services + 'passwordType/list',
                 headers=headers)
for passwordType in r.json()['result']:
    add_constant('password_types', passwordType['name'], passwordType['id'])


########################################################################
# On écrit dans un fichier toutes les constantes nécessaires à l'API,
# après les avoir triées.
logger.debug('Constantes :\n%s', constants_by_category)
constants_file = open('cyclos_constants.yml', 'w')
for category in sorted(constants_by_category.keys()):
    constants_file.write(category + ':\n')
    constants = constants_by_category[category]
    for name in sorted(constants.keys()):
        constants_file.write('  ' + name + ': ' + constants[name] + '\n')
constants_file.close()
