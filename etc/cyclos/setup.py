# coding: utf-8
import argparse
import logging
import requests

from slugify import slugify

logging.basicConfig()
logger = logging.getLogger(__name__)

try:
    stringType = basestring
except NameError:  # Python 3, basestring causes NameError
    stringType = str


def check_request_status(r):
    if r.status_code == requests.codes.ok:
        logger.info('OK')
    else:
        logger.error(r.text)
        r.raise_for_status()

# Ensemble des constantes nécessaires à l'API.
constants_by_category = {}

def add_constant(category, name, value):
    if category not in constants_by_category.keys():
        constants_by_category[category] = {}
    name = name.replace('€', 'euro')
    slug_name = slugify(name, separator='_')
    constants_by_category[category][slug_name] = value

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
logger.debug('ID_CANAL_MAIN_WEB = %s', ID_CANAL_MAIN_WEB)
logger.debug('ID_CANAL_WEB_SERVICES = %s', ID_CANAL_WEB_SERVICES)


########################################################################
# Modification de la configuration par défaut :
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
default_config_id = r.json()['result']['id']
# Puis on liste les config de canaux pour retrouver l'id de la config
# du canal "Web services".
r = requests.get(
    global_web_services + 'channelConfiguration/list/' + default_config_id,
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
    r = requests.post(
            global_web_services + 'network/save',
            headers=headers,
            json={
                'name': 'Eusko',
                'internalName': 'eusko',
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
    r = requests.post(
            eusko_web_services + 'currency/save',
            headers=headers,
            json={
                'name': name,
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
def create_system_account_type(name, currency_id, limit_type):
    logger.info('Création du type de compte système "%s"...', name)
    params = {
        'class': 'org.cyclos.model.banking.accounttypes.SystemAccountTypeDTO',
        'name': name,
        'currency': currency_id,
        'limitType': limit_type
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
        'currency': currency_id
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
ID_CAISSE_EUSKO_EM = create_system_account_type(
    name='Caisse eusko EM',
    currency_id=ID_DEVISE_EUSKO,
    limit_type='LIMITED',
)
ID_COMPTE_DE_DEBIT_EURO = create_system_account_type(
    name='Compte de débit €',
    currency_id=ID_DEVISE_EURO,
    limit_type='UNLIMITED',
)
ID_COMPTE_DE_GESTION = create_system_account_type(
    name='Compte de gestion',
    currency_id=ID_DEVISE_EURO,
    limit_type='LIMITED',
)
ID_CAISSE_EURO_EM = create_system_account_type(
    name='Caisse € EM',
    currency_id=ID_DEVISE_EURO,
    limit_type='LIMITED',
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
    ID_CAISSE_EUSKO_EM,
    ID_COMPTE_DE_DEBIT_EURO,
    ID_COMPTE_DE_GESTION,
    ID_CAISSE_EURO_EM,
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
# Création des champs personnalisés pour les paiements.
#
def create_transaction_custom_field_linked_user(name, internal_name,
                                                required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(
            eusko_web_services + 'transactionCustomField/save',
            headers=headers,
            json={
                'name': name,
                'internalName': internal_name,
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


def create_transaction_custom_field_single_selection(name, internal_name,
                                                     possible_values_name,
                                                     possible_values,
                                                     required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(
            eusko_web_services + 'transactionCustomField/save',
            headers=headers,
            json={
                'name': name,
                'internalName': internal_name,
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
        r = requests.post(
                eusko_web_services + 'transactionCustomFieldPossibleValue/save',
                headers=headers,
                json={
                    'field': custom_field_id,
                    'value': value
                })
        check_request_status(r)
        possible_value_id = r.json()['result']
        add_constant(possible_values_name, value, possible_value_id)
    return custom_field_id


def create_transaction_custom_field_text(name, internal_name, required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(
            eusko_web_services + 'transactionCustomField/save',
            headers=headers,
            json={
                'name': name,
                'internalName': internal_name,
                'type': 'STRING',
                'size': 'LARGE',
                'control': 'TEXT',
                'required': required
            })
    check_request_status(r)
    custom_field_id = r.json()['result']
    logger.debug('custom_field_id = %s', custom_field_id)
    add_constant('transaction_custom_fields', name, custom_field_id)
    return custom_field_id


def create_transaction_custom_field_decimal(name, internal_name,
                                            required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(
            eusko_web_services + 'transactionCustomField/save',
            headers=headers,
            json={
                'name': name,
                'internalName': internal_name,
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
    r = requests.post(
            eusko_web_services + 'transactionCustomField/addRelation',
            headers=headers,
            json=[transfer_type_id, custom_field_id])
    check_request_status(r)

ID_CHAMP_PERSO_PAIEMENT_BDC = create_transaction_custom_field_linked_user(
    name='BDC',
    internal_name='bdc',
)
ID_CHAMP_PERSO_PAIEMENT_PORTEUR = create_transaction_custom_field_linked_user(
    name='Porteur',
    internal_name='porteur',
)
ID_CHAMP_PERSO_PAIEMENT_ADHERENT = create_transaction_custom_field_linked_user(
    name='Adhérent',
    internal_name='adherent',
)
ID_CHAMP_PERSO_PAIEMENT_ADHERENT_FACULTATIF = create_transaction_custom_field_linked_user(
    name='Adhérent (facultatif)',
    internal_name='adherent_facultatif',
    required=False,
)
ID_CHAMP_PERSO_PAIEMENT_MODE_DE_PAIEMENT = create_transaction_custom_field_single_selection(
    name='Mode de paiement',
    internal_name='mode_de_paiement',
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
    internal_name='produit',
    possible_values_name='products',
    possible_values=[
        'Foulard',
    ],
)
ID_CHAMP_PERSO_PAIEMENT_NUMERO_BORDEREAU = create_transaction_custom_field_text(
    name='Numéro de bordereau',
    internal_name='numero_bordereau',
    required=False,
)
ID_CHAMP_PERSO_PAIEMENT_MONTANT_COTISATIONS = create_transaction_custom_field_decimal(
    name='Montant Cotisations',
    internal_name='montant_cotisations',
)
ID_CHAMP_PERSO_PAIEMENT_MONTANT_VENTES = create_transaction_custom_field_decimal(
    name='Montant Ventes',
    internal_name='montant_ventes',
)
ID_CHAMP_PERSO_PAIEMENT_MONTANT_CHANGES_BILLET = create_transaction_custom_field_decimal(
    name='Montant Changes billet',
    internal_name='montant_changes_billet',
)
ID_CHAMP_PERSO_PAIEMENT_MONTANT_CHANGES_NUMERIQUE = create_transaction_custom_field_decimal(
    name='Montant Changes numérique',
    internal_name='montant_changes_numerique',
)
ID_CHAMP_PERSO_PAIEMENT_NUMERO_TRANSACTION_BANQUE = create_transaction_custom_field_text(
    name='Numéro de transaction banque',
    internal_name='numero_transaction_banque',
)
ID_CHAMP_PERSO_PAIEMENT_NUMERO_FACTURE = create_transaction_custom_field_text(
    name='Numéro de facture',
    internal_name='numero_facture',
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
# Création des "status flow" pour les paiements.
#
def create_transfer_status_flow(name):
    logger.info('Création du "status flow" "%s"...', name)
    r = requests.post(
            eusko_web_services + 'transferStatusFlow/save',
            headers=headers,
            json={
                'name': name,
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
        'flow': status_flow,
    }
    if possible_next:
        status['possibleNext'] = possible_next
    r = requests.post(
            eusko_web_services + 'transferStatus/save',
            headers=headers,
            json=status)
    check_request_status(r)
    status_id = r.json()['result']
    logger.debug('status_id = %s', status_id)
    add_constant('transfer_statuses', name, status_id)
    return status_id

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

# Virement(s) : pour les reconversions d'eusko en € (virement à faire au
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
    ID_STATUS_FLOW_REMISE_A_EM,
    ID_STATUS_FLOW_VIREMENTS,
]


########################################################################
# Création du rôle "Administrateurs de comptes" pour les autorisations.
#
# Ce rôle sera attribué au groupe "Administrateurs de comptes" et sera
# utilisé dans tous les paiements soumis à autorisation. De cette
# manière, ce sont les membres du groupe "Administrateurs de comptes"
# qui pourront autoriser les paiements soumis à autorisation.
#
def create_authorization_role(name):
    logger.info('Création du rôle "%s" pour les autorisations...', name)
    r = requests.post(
            eusko_web_services + 'authorizationRole/save',
            headers=headers,
            json={'name': name})
    check_request_status(r)
    authorization_role_id = r.json()['result']
    logger.debug('authorization_role_id = %s', authorization_role_id)
    return authorization_role_id


def create_authorization_level(transfer_type_id, authorization_role_id):
    logger.info("Création d'un niveau d'autorisation...")
    r = requests.post(
            eusko_web_services + 'authorizationLevel/save',
            headers=headers,
            json={
                'transferType': transfer_type_id,
                'roles': [authorization_role_id]
            })
    check_request_status(r)
    authorization_level_id = r.json()['result']
    logger.debug('authorization_level_id = %s', authorization_level_id)
    return authorization_level_id

ID_ROLE_AUTORISATION_ADMIN_COMPTES = create_authorization_role(
    name='Administrateurs de comptes',
)


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
# Note : les paiements pourront être rejetés par les administrateurs de
# comptes (voir le paramétrage des permissions).
#
# Par souci de simplicité, tous les types de paiement sont accessibles
# par les 2 canaux "Main web" et "Web services". Ainsi tous les types
# de paiement seront accessibles par l'interface web de Cyclos pour les
# administrateurs de comptes (voir le paramétrage des permissions), ce
# qui garantit une capacité à intervenir si nécessaire. D'autre part,
# ils peuvent tous être utilisés par l'API Eusko (ce n'est pas forcément
# nécessaire mais c'est possible, il n'y aura pas de question à se
# poser.
#
def create_payment_transfer_type(name, direction, from_account_type_id,
                                 to_account_type_id, custom_fields=[],
                                 requires_authorization=False,
                                 status_flows=[], initial_statuses=[]):
    logger.info('Création du type de paiement "%s"...', name)
    r = requests.post(
            eusko_web_services + 'transferType/save',
            headers=headers,
            json={
                'class': 'org.cyclos.model.banking.transfertypes.PaymentTransferTypeDTO',
                'name': name,
                'direction': direction,
                'from': from_account_type_id,
                'to': to_account_type_id,
                'enabled': True,
                'requiresAuthorization': requires_authorization,
                'statusFlows': status_flows,
                'initialStatuses': initial_statuses,
                'maxChargebackTime': {'amount': '2', 'field': 'MONTHS'},
                'channels': [ID_CANAL_MAIN_WEB, ID_CANAL_WEB_SERVICES]
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
    if requires_authorization:
        create_authorization_level(
            transfer_type_id=payment_transfer_type_id,
            authorization_role_id=ID_ROLE_AUTORISATION_ADMIN_COMPTES,
        )
    return payment_transfer_type_id


def create_generated_transfer_type(name, direction, from_account_type_id,
                                   to_account_type_id):
    logger.info('Création du type de paiement "%s"...', name)
    r = requests.post(
            eusko_web_services + 'transferType/save',
            headers=headers,
            json={
                'class': 'org.cyclos.model.banking.transfertypes.GeneratedTransferTypeDTO',
                'name': name,
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
    r = requests.post(
            eusko_web_services + 'transferFee/save',
            headers=headers,
            json={
                'name': name,
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
ID_TYPE_PAIEMENT_SORTIE_COFFRE = create_payment_transfer_type(
    name='Sortie coffre',
    direction='SYSTEM_TO_SYSTEM',
    from_account_type_id=ID_STOCK_DE_BILLETS,
    to_account_type_id=ID_COMPTE_DE_TRANSIT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
        ID_CHAMP_PERSO_PAIEMENT_BDC,
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
ID_TYPE_PAIEMENT_ENTREE_CAISSE_EUSKO_EM = create_payment_transfer_type(
    name='Entrée caisse eusko EM',
    direction='SYSTEM_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_DE_TRANSIT,
    to_account_type_id=ID_CAISSE_EUSKO_EM,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
        ID_CHAMP_PERSO_PAIEMENT_BDC,
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
)
ID_TYPE_PAIEMENT_SORTIE_CAISSE_EUSKO_BDC = create_payment_transfer_type(
    name='Sortie caisse eusko BDC',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_CAISSE_EUSKO_BDC,
    to_account_type_id=ID_COMPTE_DE_TRANSIT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_PORTEUR,
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
        ID_STATUS_FLOW_VIREMENTS,
    ],
    initial_statuses=[
        ID_STATUS_VIREMENTS_A_FAIRE,
    ],
)
ID_TYPE_PAIEMENT_REGUL_COMPTE_DE_GESTION_VERS_BANQUE = create_payment_transfer_type(
    direction='SYSTEM_TO_USER',
    name='Régularisation Compte de gestion vers Banque de dépôt',
    from_account_type_id=ID_COMPTE_DE_GESTION,
    to_account_type_id=ID_BANQUE_DE_DEPOT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_BDC,
    ],
)
ID_TYPE_PAIEMENT_BANQUE_VERS_CAISSE_EURO_BDC = create_payment_transfer_type(
    name='Paiement de Banque de dépôt vers Caisse € BDC',
    direction='USER_TO_USER',
    from_account_type_id=ID_BANQUE_DE_DEPOT,
    to_account_type_id=ID_CAISSE_EURO_BDC,
    status_flows=[
        ID_STATUS_FLOW_REMISE_A_EM,
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
    ],
)
ID_TYPE_PAIEMENT_CAISSE_EURO_BDC_VERS_BANQUE = create_payment_transfer_type(
    name='Paiement de Caisse € BDC vers Banque de dépôt',
    direction='USER_TO_USER',
    from_account_type_id=ID_CAISSE_EURO_BDC,
    to_account_type_id=ID_BANQUE_DE_DEPOT,
)
ID_TYPE_PAIEMENT_REGUL_BANQUE_VERS_COMPTE_DE_GESTION = create_payment_transfer_type(
    name='Régularisation Banque de dépôt vers Compte de gestion',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_BANQUE_DE_DEPOT,
    to_account_type_id=ID_COMPTE_DE_GESTION,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_BDC,
    ],
)

# Type de paiement utilisé lorsqu'un BDC remet des espèces à Euskal
# Moneta suite à un refus de la banque de prendre ces espèces.
ID_TYPE_PAIEMENT_REMISE_EUROS_EN_CAISSE = create_payment_transfer_type(
    name="Remise d'€ en caisse",
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_CAISSE_EURO_BDC,
    to_account_type_id=ID_CAISSE_EURO_EM,
)
ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DE_GESTION = create_payment_transfer_type(
    name='Virement de Banque de dépôt vers le Compte de gestion',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_BANQUE_DE_DEPOT,
    to_account_type_id=ID_COMPTE_DE_GESTION,
)
ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DEDIE = create_payment_transfer_type(
    name='Virement de Banque de dépôt vers Compte dédié',
    direction='USER_TO_USER',
    from_account_type_id=ID_BANQUE_DE_DEPOT,
    to_account_type_id=ID_COMPTE_DEDIE,
)
ID_TYPE_PAIEMENT_COMPTE_DEDIE_VERS_COMPTE_DE_DEBIT = create_payment_transfer_type(
    name='Virement de Compte dédié vers le Compte de débit en €',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_DEDIE,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EURO,
    requires_authorization=True,
)
ID_TYPE_PAIEMENT_COMPTE_DEDIE_VERS_COMPTE_DE_GESTION = create_payment_transfer_type(
    name='Virement de Compte dédié vers le Compte de gestion',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_DEDIE,
    to_account_type_id=ID_COMPTE_DE_GESTION,
    requires_authorization=True,
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

# Types de paiement pour l'eusko numérique
#
ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_LIGNE = create_payment_transfer_type(
    name='Change numérique en ligne - Versement des eusko',
    direction='SYSTEM_TO_USER',
    from_account_type_id=ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
    to_account_type_id=ID_COMPTE_ADHERENT,
    custom_fields=[
        ID_CHAMP_PERSO_PAIEMENT_NUMERO_TRANSACTION_BANQUE,
    ],
)
# frais : versement des €

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

# Même fonctionnement que pour la reconversion billets, sauf que les
# virements générés par l'API Eusko sont faits à partir du compte dédié
# numérique au lieu du compte dédié billet.
ID_TYPE_PAIEMENT_RECONVERSION_NUMERIQUE = create_payment_transfer_type(
    name='Reconversion numérique',
    direction='USER_TO_SYSTEM',
    from_account_type_id=ID_COMPTE_ADHERENT,
    to_account_type_id=ID_COMPTE_DE_DEBIT_EUSKO_NUMERIQUE,
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
    ],
    initial_statuses=[
        ID_STATUS_A_REMETTRE,
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

# Et enfin, le type de paiement le plus important pour l'eusko
# numérique !
ID_TYPE_PAIEMENT_VIREMENT_INTER_ADHERENT = create_payment_transfer_type(
    name='Virement inter-adhérent',
    direction='USER_TO_USER',
    from_account_type_id=ID_COMPTE_ADHERENT,
    to_account_type_id=ID_COMPTE_ADHERENT,
)


all_system_to_system_payments = [
    ID_TYPE_PAIEMENT_IMPRESSION_BILLETS,
    ID_TYPE_PAIEMENT_SORTIE_COFFRE,
    ID_TYPE_PAIEMENT_ENTREE_COFFRE,
    ID_TYPE_PAIEMENT_ENTREE_CAISSE_EUSKO_EM,
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
    ID_TYPE_PAIEMENT_REGUL_COMPTE_DE_GESTION_VERS_BANQUE,
    ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_LIGNE,
    ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_BDC,
    ID_TYPE_PAIEMENT_DEPOT_DE_BILLETS,
    ID_TYPE_PAIEMENT_CREDIT_DU_COMPTE,
]
all_user_to_system_payments = [
    ID_TYPE_PAIEMENT_SORTIE_STOCK_BDC,
    ID_TYPE_PAIEMENT_SORTIE_CAISSE_EUSKO_BDC,
    ID_TYPE_PAIEMENT_SORTIE_RETOURS_EUSKO_BDC,
    ID_TYPE_PAIEMENT_PERTE_DE_BILLETS,
    ID_TYPE_PAIEMENT_REGUL_BANQUE_VERS_COMPTE_DE_GESTION,
    ID_TYPE_PAIEMENT_REMISE_EUROS_EN_CAISSE,
    ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DE_GESTION,
    ID_TYPE_PAIEMENT_COMPTE_DEDIE_VERS_COMPTE_DE_DEBIT,
    ID_TYPE_PAIEMENT_COMPTE_DEDIE_VERS_COMPTE_DE_GESTION,
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
]
all_payments_to_system = \
    all_system_to_system_payments \
    + all_user_to_system_payments
all_payments_to_user = \
    all_system_to_user_payments \
    + all_user_to_user_payments


########################################################################
# Création des champs personnalisés pour les profils utilisateur.
#
def create_user_custom_field_linked_user(name, internal_name,
                                         required=True):
    logger.info('Création du champ personnalisé "%s"...', name)
    r = requests.post(
            eusko_web_services + 'userCustomField/save',
            headers=headers,
            json={
                'name': name,
                'internalName': internal_name,
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
    internal_name='bdc',
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
def create_member_product(name, user_account_type_id=None):
    logger.info('Création du produit "%s"...', name)
    product = {
        'class': 'org.cyclos.model.users.products.MemberProductDTO',
        'name': name,
        'myProfileFields': [
            {
                'profileField': 'FULL_NAME',
                'enabled': True,
                'editableAtRegistration': True,
                'visible': True,
                'editable': True,
                'managePrivacy': False,
            },
            {
                'profileField': 'LOGIN_NAME',
                'enabled': True,
                'editableAtRegistration': True,
                'visible': True,
                'editable': True,
                'managePrivacy': False,
            },
        ]
    }
    if user_account_type_id:
        product['userAccount'] = user_account_type_id
    r = requests.post(
            eusko_web_services + 'product/save',
            headers=headers,
            json=product)
    check_request_status(r)
    product_id = r.json()['result']
    logger.debug('product_id = %s', product_id)
    return product_id


def assign_product_to_group(product_id, group_id):
    logger.info("Affectation du produit à un groupe...")
    r = requests.post(
            eusko_web_services + 'productsGroup/assign',
            headers=headers,
            json=[product_id, group_id])
    check_request_status(r)


# TODO Modifier en set_admin_group_permissions(group_id, ...) ?
# A faire s'il s'avère que cette fonction n'est pas adaptée pour les
# produits de membres.
def set_product_properties(
        product_id,
        my_profile_fields=[],
        passwords=[],
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
        access_user_accounts=[],
        payments_as_user_to_user=[],
        payments_as_user_to_system=[],
        chargeback_of_payments_to_user=[]):
    # Chargement du produit
    r = requests.get(
            eusko_web_services + 'product/load/' + product_id,
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
        if password_action['passwordType']['internalName'] in passwords:
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
    product['userAccountsAccess'] = access_user_accounts
    product['userPaymentsAsUser'] = payments_as_user_to_user
    product['systemPaymentsAsUser'] = payments_as_user_to_system
    product['chargebackPaymentsToUser'] = chargeback_of_payments_to_user
    # Enregistrement du produit modifié
    r = requests.post(
            eusko_web_services + 'product/save',
            headers=headers,
            json=product)
    check_request_status(r)


# TODO factoriser le code de ces 2 fonctions si elles restent telles quelles
# create_group(nature = 'ADMIN' ou 'MEMBER', name)
def create_admin_group(name):
    logger.info('Création du groupe Administrateur "%s"...', name)
    r = requests.post(
            eusko_web_services + 'group/save',
            headers=headers,
            json={
                'class': 'org.cyclos.model.users.groups.AdminGroupDTO',
                'name': name,
                'initialUserStatus': 'ACTIVE',
                'enabled': True
            })
    check_request_status(r)
    group_id = r.json()['result']
    logger.debug('group_id = %s', group_id)
    add_constant('groups', name, group_id)
    return group_id


def get_admin_product(group_id):
    r = requests.get(
            eusko_web_services + 'group/load/' + group_id,
            headers=headers,
            json={})
    check_request_status(r)
    product_id = r.json()['result']['adminProduct']['id']
    return product_id


def create_member_group(name, products=[]):
    logger.info('Création du groupe Membre "%s"...', name)
    r = requests.post(
            eusko_web_services + 'group/save',
            headers=headers,
            json={
                'class': 'org.cyclos.model.users.groups.MemberGroupDTO',
                'name': name,
                'initialUserStatus': 'ACTIVE',
                'enabled': True
            })
    check_request_status(r)
    group_id = r.json()['result']
    logger.debug('group_id = %s', group_id)
    add_constant('groups', name, group_id)
    for product_id in products:
        assign_product_to_group(product_id, group_id)
    return group_id

# Administrateurs de comptes.
ID_GROUPE_ADMINS_DE_COMPTES = create_admin_group(
    name='Administrateurs de comptes',
)

# Opérateurs BDC.
ID_GROUPE_OPERATEURS_BDC = create_admin_group(
    name='Opérateurs BDC',
)

# Bureaux de change.
ID_PRODUIT_STOCK_DE_BILLETS_BDC = create_member_product(
    name='Stock de billets BDC',
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
    user_account_type_id=ID_COMPTE_DEDIE,
)
ID_GROUPE_COMPTES_DEDIES = create_member_group(
    name='Comptes dédiés',
    products=[
        ID_PRODUIT_COMPTE_DEDIE,
    ]
)

# Adhérents.
ID_PRODUIT_ADHERENT = create_member_product(
    name='Adhérent',
    user_account_type_id=ID_COMPTE_ADHERENT,
)
ID_GROUPE_ADHERENTS_PRESTATAIRES = create_member_group(
    name='Adhérents prestataires',
    products=[
        ID_PRODUIT_ADHERENT,
    ]
)
ID_GROUPE_ADHERENTS_UTILISATEURS = create_member_group(
    name='Adhérents utilisateurs',
    products=[
        ID_PRODUIT_ADHERENT,
    ]
)

# Porteurs.
ID_PRODUIT_PORTEUR = create_member_product(
    name='Porteur',
)
ID_GROUPE_PORTEURS = create_member_group(
    name='Porteurs',
    products=[
        ID_PRODUIT_PORTEUR,
    ]
)

all_user_groups = [
    ID_GROUPE_BUREAUX_DE_CHANGE,
    ID_GROUPE_BANQUES_DE_DEPOT,
    ID_GROUPE_COMPTES_DEDIES,
    ID_GROUPE_ADHERENTS_PRESTATAIRES,
    ID_GROUPE_ADHERENTS_UTILISATEURS,
    ID_GROUPE_PORTEURS,
]

# Définition des permissions.
# Il faut faire ça en dernier car nous avons besoin de tous les objets
# créés auparavant.
set_product_properties(
    get_admin_product(ID_GROUPE_ADMINS_DE_COMPTES),
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    passwords=[
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
    user_profile_fields = [
        'FULL_NAME',
        'LOGIN_NAME',
        ID_CHAMP_PERSO_UTILISATEUR_BDC,
    ],
    change_group='MANAGE',
    user_registration=True,
    access_user_accounts=all_user_accounts,
    payments_as_user_to_user=all_user_to_user_payments,
    payments_as_user_to_system=all_user_to_system_payments,
    chargeback_of_payments_to_user=all_payments_to_user
)
set_product_properties(
    get_admin_product(ID_GROUPE_OPERATEURS_BDC),
    my_profile_fields=[
        'FULL_NAME',
        'LOGIN_NAME',
        ID_CHAMP_PERSO_UTILISATEUR_BDC,
    ],
    passwords=[
        'login',
    ],
    visible_transaction_fields=all_transaction_fields,
    transfer_status_flows=[
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
        ID_TYPE_PAIEMENT_REGUL_COMPTE_DE_GESTION_VERS_BANQUE,
        ID_TYPE_PAIEMENT_CHANGE_NUMERIQUE_EN_BDC,
        ID_TYPE_PAIEMENT_DEPOT_DE_BILLETS,
        ID_TYPE_PAIEMENT_CREDIT_DU_COMPTE,
    ],
    accessible_user_groups=all_user_groups,
    user_profile_fields = [
        'FULL_NAME',
        'LOGIN_NAME',
    ],
    user_registration=True,
    access_user_accounts=[
        ID_STOCK_DE_BILLETS_BDC,
        ID_CAISSE_EURO_BDC,
        ID_CAISSE_EUSKO_BDC,
        ID_RETOURS_EUSKO_BDC,
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
        ID_TYPE_PAIEMENT_REGUL_BANQUE_VERS_COMPTE_DE_GESTION,
        ID_TYPE_PAIEMENT_REMISE_EUROS_EN_CAISSE,
        ID_TYPE_PAIEMENT_BANQUE_VERS_COMPTE_DE_GESTION,
        ID_TYPE_PAIEMENT_RETRAIT_DE_BILLETS,
        ID_TYPE_PAIEMENT_RETRAIT_DU_COMPTE,
    ],
)

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