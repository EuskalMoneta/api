import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bdc_cyclos import serializers
from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException

log = logging.getLogger()


@api_view(['GET'])
def accounts_summaries(request, login_bdc=None):
    """
    List all accounts_summaries for this BDC user.
    """
    cyclos_mode = 'gi_bdc' if login_bdc else 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode, login_bdc=login_bdc)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # account/getAccountsSummary
    query_data = [cyclos.user_bdc_id, None]  # ID de l'utilisateur Bureau de change
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    # Stock de billets: stock_de_billets_bdc
    # Caisse euros: caisse_euro_bdc
    # Caisse eusko: caisse_eusko_bdc
    # Retour eusko: retours_d_eusko_bdc
    res = {}
    filter_keys = ['stock_de_billets_bdc', 'caisse_euro_bdc', 'caisse_eusko_bdc', 'retours_d_eusko_bdc']

    for filter_key in filter_keys:
        data = [item
                for item in accounts_summaries_data['result']
                if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['account_types'][filter_key])][0]

        res[filter_key] = {}
        res[filter_key]['id'] = data['id']
        res[filter_key]['balance'] = float(data['status']['balance'])
        res[filter_key]['currency'] = data['currency']['symbol']
        res[filter_key]['type'] = {'name': data['type']['name'], 'id': filter_key}

    return Response(res)


@api_view(['GET'])
def system_accounts_summaries(request):
    """
    List all system_accounts_summaries.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='gi_bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # account/getAccountsSummary
    query_data = ['SYSTEM', None]
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    # Stock de billets: stock_de_billets
    # Compte de transit: compte_de_transit
    res = {}
    filter_keys = ['stock_de_billets', 'compte_de_transit']
    for filter_key in filter_keys:
        data = [item
                for item in accounts_summaries_data['result']
                if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['account_types'][filter_key])][0]

        res[filter_key] = {}
        res[filter_key]['id'] = data['id']
        res[filter_key]['balance'] = float(data['status']['balance'])
        res[filter_key]['currency'] = data['currency']['symbol']
        res[filter_key]['type'] = {'name': data['type']['name'], 'id': filter_key}

    return Response(res)


@api_view(['GET'])
def dedicated_accounts_summaries(request):
    """
    Accounts summaries for dedicated accounts.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='gi_bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = []
    # Compte dédié Eusko billet: compte_dedie_eusko_billet
    # Compte dédié Eusko numérique: compte_dedie_eusko_numerique
    query_data_billet = [str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']), None]
    query_data.extend(cyclos.post(method='account/getAccountsSummary', data=query_data_billet)['result'])

    query_data_numerique = [str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']), None]
    query_data.extend(cyclos.post(method='account/getAccountsSummary', data=query_data_numerique)['result'])

    res = {}
    filter_keys = ['compte_dedie_eusko_billet', 'compte_dedie_eusko_numerique']
    for filter_key in filter_keys:
        data = [item
                for item in query_data
                if item['owner']['id'] == str(settings.CYCLOS_CONSTANTS['users'][filter_key])][0]

        res[filter_key] = {}
        res[filter_key]['id'] = data['id']
        res[filter_key]['balance'] = float(data['status']['balance'])
        res[filter_key]['currency'] = data['currency']['symbol']
        res[filter_key]['type'] = {'name': data['type']['name'], 'id': filter_key}

    return Response(res)


@api_view(['GET'])
def deposit_banks_summaries(request):
    """
    Accounts summaries for deposit banks.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='gi_bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # user/search for group = 'Banques de dépot'
    banks_data = cyclos.post(method='user/search',
                             data={'groups': [settings.CYCLOS_CONSTANTS['groups']['banques_de_depot']]})
    bank_names = [{'label': item['display'], 'value': item['id'], 'shortLabel': item['shortDisplay']}
                  for item in banks_data['result']['pageItems']]

    res = {}
    for bank in bank_names:
        bank_user_query = {
            'keywords': bank['shortLabel'],  # shortLabel = shortDisplay from Cyclos
        }
        try:
            bank_user_data = cyclos.post(method='user/search', data=bank_user_query)['result']['pageItems'][0]

            bank_account_query = [bank_user_data['id'], None]
            bank_data = cyclos.post(method='account/getAccountsSummary', data=bank_account_query)['result'][0]
        except (KeyError, IndexError):
                    return Response({'error': 'Unable to get bank data for one of the depositbank!'},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        res[bank['shortLabel']] = bank
        res[bank['shortLabel']]['balance'] = float(bank_data['status']['balance'])
        res[bank['shortLabel']]['currency'] = bank_data['currency']['symbol']
        res[bank['shortLabel']]['type'] = {'name': bank_data['type']['name'],
                                           'id': bank_data['type']['id']}

    return Response(res)


@api_view(['POST'])
def entree_stock(request):
    """
    Enregistre une entrée dans le stock billets d'un BDC.
    """
    serializer = serializers.EntreeStockBDCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        login_bdc = request.data['login_bdc']
        cyclos_mode = 'gi_bdc'
    except KeyError:
        login_bdc = None
        cyclos_mode = 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode, login_bdc=login_bdc)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    for payment in request.data['selected_payments']:
        try:
            porteur = [
                value['linkedEntityValue']['id']
                for value in payment['customValues']
                if value['field']['id'] == str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur']) and
                value['field']['internalName'] == 'porteur'
            ][0]
        except (KeyError, IndexError):
            # TODO ?
            porteur = ''

        try:
            bdc_name = [
                value['linkedEntityValue']['name']
                for value in payment['customValues']
                if value['field']['internalName'] == 'bdc'
            ][0]
        except (KeyError, IndexError):
            # TODO ?
            bdc_name = ''

        try:
            if 'Sortie coffre' in payment['description']:
                description = payment['description'].replace('Sortie coffre', 'Entrée stock')
            else:
                description = 'Entrée stock - {} - {}'.format(request.data['login_bdc'], bdc_name)
        except KeyError:
            description = 'Entrée stock - {} - {}'.format(request.data['login_bdc'], bdc_name)

        # payment/perform
        payment_query_data = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['entree_stock_bdc']),
            'amount': payment['amount'],
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
            'from': 'SYSTEM',
            'to': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
            'customValues': [
                {
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur']),
                    'linkedEntityValue': porteur  # ID du porteur
                },
            ],
            'description': description,
        }
        cyclos.post(method='payment/perform', data=payment_query_data)

        status_query_data = {
            'transfer': payment['id'],       # ID de l'opération d'origine (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['rapproche'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=status_query_data)

    return Response(request.data['selected_payments'])


@api_view(['POST'])
def sortie_stock(request):
    """
    Enregistre une sortie dans le stock billets d'un BDC.
    """

    serializer = serializers.SortieStockBDCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        login_bdc = request.data['login_bdc']
        cyclos_mode = 'gi_bdc'
    except KeyError:
        login_bdc = None
        cyclos_mode = 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode, login_bdc=login_bdc)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # payment/perform
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_stock_bdc']),
        'amount': request.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        'to': 'SYSTEM',
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur']),
                'linkedEntityValue': request.data['porteur']  # ID du porteur
            },
        ],
        'description': request.data['description'],
    }

    return Response(cyclos.post(method='payment/perform', data=query_data))


@api_view(['POST'])
def change_euro_eusko(request):
    """
    Change d'€ en eusko pour un adhérent via un BDC.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ChangeEuroEuskoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    member_cyclos_id = cyclos.get_member_id_from_login(request.data['member_login'])

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        dolibarr_member = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.data['member_login']))[0]
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except IndexError:
        return Response({'error': 'Unable to fetch Dolibarr data! Maybe your credentials are invalid!?'},
                        status=status.HTTP_400_BAD_REQUEST)

    if dolibarr_member['type'].lower() == 'particulier':
        member_name = '{} {}'.format(dolibarr_member['firstname'], dolibarr_member['lastname'])
    else:
        member_name = dolibarr_member['company']

    # payment/perform
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_billets_versement_des_euro']),
        'amount': request.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': 'SYSTEM',
        'to': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                'linkedEntityValue': member_cyclos_id  # ID de l'adhérent
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['mode_de_paiement']),
                'enumeratedValues': request.data['payment_mode']  # ID du mode de paiement (chèque ou espèces)
            },
        ],
        # "Change - E12345 - Nom de l'adhérent - Mode de paiement"
        'description': 'Change billets - {} - {} - {}'.format(
            request.data['member_login'], member_name, request.data['payment_mode_name']),
    }

    return Response(cyclos.post(method='payment/perform', data=query_data))


@api_view(['POST'])
def reconversion(request):
    """
    Reconversion eusko en euros pour un adhérent (prestataire) via un BDC.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ReconversionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        dolibarr_member = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.data['member_login']))[0]
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except IndexError:
        return Response({'error': 'Unable to fetch Dolibarr data! Maybe your credentials are invalid!?'},
                        status=status.HTTP_400_BAD_REQUEST)

    if dolibarr_member['type'].lower() == 'particulier':
        return Response({'error': 'Forbidden, reconversion is not available for non-business members!'},
                        status=status.HTTP_403_FORBIDDEN)

    member_cyclos_id = cyclos.get_member_id_from_login(request.data['member_login'])

    # payment/perform
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['reconversion_billets_versement_des_eusko']),
        'amount': request.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': 'SYSTEM',
        'to': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                'linkedEntityValue': member_cyclos_id  # ID de l'adhérent
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['numero_de_facture']),
                'stringValue': request.data['facture']  # ID Facture
            },
        ],
        'description': 'Reconversion - {} - {}'.format(request.data['member_login'], dolibarr_member['company']),
    }

    return Response(cyclos.post(method='payment/perform', data=query_data))


@api_view(['GET'])
def accounts_history(request):
    """
    Accounts history for BDC and system accounts.
    For a Bureau De Change the available accounts types are:
    ['stock_de_billets_bdc', 'caisse_euro_bdc', 'caisse_eusko_bdc', 'retours_d_eusko_bdc'].

    If your user is 'Gestion Interne' you can request some other accounts:
    'stock_de_billets' (aka Coffre), and 'compte_de_transit'.

    You can also filter out results with the 'filter' query param
    """

    serializer = serializers.AccountsHistorySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # CyclosAPI has 3 modes: gi, gi_bdc, and bdc
    try:
        login_bdc = None
        cyclos_mode = request.query_params['cyclos_mode']
    except KeyError:
        try:
            login_bdc = request.query_params['login_bdc']
            cyclos_mode = 'gi_bdc'
        except KeyError:
            login_bdc = None
            cyclos_mode = 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode, login_bdc=login_bdc)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # If you are a BDC user
    if cyclos_mode in ['bdc', 'gi_bdc']:
        query_data = [cyclos.user_bdc_id, None]  # ID de l'utilisateur Bureau de change
        account_types = ['stock_de_billets_bdc', 'caisse_euro_bdc', 'caisse_eusko_bdc', 'retours_d_eusko_bdc']

    # If you are Gestion Interne
    elif cyclos_mode == 'gi':
        query_data = ['SYSTEM', None]
        account_types = ['stock_de_billets', 'compte_de_transit',
                         'compte_dedie_eusko_billet', 'compte_dedie_eusko_numerique']

    # Available account types verification
    if request.query_params['account_type'] not in account_types:
        return Response({'error': 'The account type you provided: {}, is not available for this query!'
                         .format(request.query_params['account_type'])},
                        status=status.HTTP_400_BAD_REQUEST)

    if 'compte_dedie' in request.query_params['account_type']:
        query_data = [str(settings.CYCLOS_CONSTANTS['users'][request.query_params['account_type']]), None]

    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    try:
        if 'compte_dedie' in request.query_params['account_type']:
            data = accounts_summaries_data['result'][0]
        else:
            data = [item
                    for item in accounts_summaries_data['result']
                    if item['type']['id'] ==
                    str(settings.CYCLOS_CONSTANTS['account_types'][request.query_params['account_type']])][0]
    except IndexError:
        return Response(status=status.HTTP_204_NO_CONTENT)

    # account/searchAccountHistory
    search_history_data = {
        'account': data['id'],  # ID du compte
        'orderBy': 'DATE_DESC',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
    }

    try:
        if request.query_params['filter']:
            search_history_data['statuses'] = [
                str(settings.CYCLOS_CONSTANTS['transfer_statuses'][request.query_params['filter']])
            ]
        if request.query_params['direction']:
            search_history_data['direction'] = request.query_params['direction']
    except KeyError:
        pass

    return Response(cyclos.post(method='account/searchAccountHistory', data=search_history_data))


@api_view(['POST'])
def bank_deposit(request):
    """
    bank_deposit: bank deposit
    """

    serializer = serializers.BankDepositSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        login_bdc = request.data['login_bdc']
        cyclos_mode = 'gi_bdc'
    except KeyError:
        login_bdc = None
        cyclos_mode = 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode, login_bdc=login_bdc)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # Récupére les détails de chaque paiement,
    # nécessaire pour connaître le type de chaque paiement, ce qui va servir à calculer la ventilation
    payments_data = {}
    for payment in request.data['selected_payments']:
        try:
            bdc_name = [
                value['linkedEntityValue']['name']
                for value in payment['customValues']
                if value['field']['internalName'] == 'bdc'
            ][0]
        except (KeyError, IndexError):
            # TODO ?
            bdc_name = ''

        payment_res = cyclos.get(method='transfer/load/{}'.format(payment['id']))
        payment_amount = float(payment_res['result']['currencyAmount']['amount'])
        try:
            payments_data[payment_res['result']['type']['id']] += payment_amount
        except KeyError:
            payments_data[payment_res['result']['type']['id']] = payment_amount

    try:
        montant_changes_billet = payments_data[
            str(settings.CYCLOS_CONSTANTS['payment_types']['change_billets_versement_des_euro'])]
    except KeyError:
        montant_changes_billet = float()

    try:
        montant_changes_numerique = payments_data[
            str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_bdc_versement_des_euro'])]
    except KeyError:
        montant_changes_numerique = float()

    try:
        montant_cotisations = payments_data[str(settings.CYCLOS_CONSTANTS['payment_types']['cotisation_en_euro'])]
    except KeyError:
        montant_cotisations = float()

    try:
        montant_ventes = payments_data[str(settings.CYCLOS_CONSTANTS['payment_types']['vente_en_euro'])]
    except KeyError:
        montant_ventes = float()

    # Enregistrer le dépôt en banque sur le compte approprié
    try:
        bordereau = request.data['bordereau']
    except KeyError:
        bordereau = ''

    bank_deposit_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['depot_en_banque']),
        'amount': request.data['deposit_calculated_amount'],  # montant total calculé
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        'to': request.data['deposit_bank'],  # ID de la banque de dépôt (Crédit Agricole ou La Banque Postale)
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['mode_de_paiement']),
                'enumeratedValues': request.data['payment_mode']  # ID du mode de paiement (chèque ou espèces)
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['numero_de_bordereau']),
                'stringValue': bordereau  # saisi par l'utilisateur
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['montant_cotisations']),
                'decimalValue': montant_cotisations  # calculé
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['montant_ventes']),
                'decimalValue': montant_ventes  # calculé
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['montant_changes_billet']),
                'decimalValue': montant_changes_billet  # calculé
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['montant_changes_numerique']),
                'decimalValue': montant_changes_numerique  # calculé
            },
        ],
        'description': 'Dépôt en banque - {} - {}\n{} - {}'.format(
            request.data['login_bdc'], bdc_name,
            request.data['deposit_bank_name'], request.data['payment_mode_name'])
    }
    cyclos.post(method='payment/perform', data=bank_deposit_data)

    if request.data['deposit_amount']:
        deposit_amount = float(request.data['deposit_amount'])
    else:
        deposit_amount = float(0)

    if request.data['deposit_calculated_amount']:
        deposit_calculated_amount = float(request.data['deposit_calculated_amount'])
    else:
        deposit_calculated_amount = float(0)

    if deposit_amount < deposit_calculated_amount:
        regularisation = deposit_calculated_amount - deposit_amount

        # Enregistrer un paiement de la Banque de dépôt vers la Caisse € du BDC
        payment_deposit_to_caisse_bdc_data = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['paiement_de_banque_de_depot_vers_caisse_euro_bdc']),  # noqa
            'amount': regularisation,  # Montant de la régularisation
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': request.data['deposit_bank'],  # ID de la banque de dépôt (Crédit Agricole ou La Banque Postale)
            'to': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
            'description': 'Espèces non déposées'
        }
        cyclos.post(method='payment/perform', data=payment_deposit_to_caisse_bdc_data)

        # Enregistrer un paiement du Compte de débit € vers la Banque de dépôt
        payment_gestion_to_deposit_data = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['regularisation_depot_insuffisant']),
            'amount': regularisation,  # Montant de la régularisation
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': 'SYSTEM',
            'to': request.data['deposit_bank'],  # ID de la banque de dépôt (Crédit Agricole ou La Banque Postale)
            'customValues': [
                {
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['bdc']),
                    'linkedEntityValue': cyclos.user_bdc_id  # ID de l'utilisateur Bureau de change
                },
            ],
            'description': 'Régularisation espèces non déposées'
        }
        cyclos.post(method='payment/perform', data=payment_gestion_to_deposit_data)

    elif deposit_amount > deposit_calculated_amount:

        regularisation = deposit_amount - deposit_calculated_amount

        # Enregistrer un paiement de la Caisse € du BDC vers la Banque de dépôt
        payment_caisse_bdc_to_deposit_data = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['paiement_de_caisse_euro_bdc_vers_banque_de_depot']),  # noqa
            'amount': regularisation,  # Montant de la régularisation
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': cyclos.user_bdc_id,          # ID de l'utilisateur Bureau de change
            'to': request.data['deposit_bank'],  # ID de la banque de dépôt (Crédit Agricole ou La Banque Postale)
            'description': 'Espèces déposées en trop'
        }
        cyclos.post(method='payment/perform', data=payment_caisse_bdc_to_deposit_data)

        # Enregistrer un paiement de la Banque de dépôt vers le Compte de débit €
        payment_deposit_to_gestion_data = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['regularisation_depot_excessif']),
            'amount': regularisation,  # Montant de la régularisation
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': request.data['deposit_bank'],     # ID de la banque de dépôt (Crédit Agricole ou La Banque Postale)
            'to': 'SYSTEM',
            'customValues': [
                {
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['bdc']),
                    'linkedEntityValue': cyclos.user_bdc_id  # ID de l'utilisateur Bureau de change
                },
            ],
            'description': 'Régularisation espèces déposées en trop'
        }
        cyclos.post(method='payment/perform', data=payment_deposit_to_gestion_data)

    # Passer tous les paiements à l'origine du dépôt à l'état "Remis à Euskal Moneta"
    for payment in request.data['selected_payments']:
        transfer_change_status_data = {
            'transfer': payment['id'],  # ID du paiement (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['remis_a_euskal_moneta'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=transfer_change_status_data)

    return Response(bank_deposit_data)


@api_view(['POST'])
def cash_deposit(request):
    """
    cash_deposit
    """
    serializer = serializers.CashDepositSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        login_bdc = request.data['login_bdc']
        cyclos_mode = 'gi_bdc'
    except KeyError:
        login_bdc = None
        cyclos_mode = 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode, login_bdc=login_bdc)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        bdc_code = request.data['login_bdc']
        bdc_name = dolibarr.get(model='users', sqlfilters="login='{}'".format(bdc_code))[0]['lastname']
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except (IndexError, KeyError):
        return Response({'error': 'Unable to get user data from your user!'}, status=status.HTTP_400_BAD_REQUEST)

    if request.data['mode'] == 'cash-deposit':
        payment_type = str(settings.CYCLOS_CONSTANTS['payment_types']['remise_d_euro_en_caisse'])
        currency = str(settings.CYCLOS_CONSTANTS['currencies']['euro'])
        description = "Remise d'espèces - {} - {}".format(bdc_code, bdc_name)
    elif request.data['mode'] == 'sortie-caisse-eusko':
        try:
            porteur = request.data['porteur']
        except KeyError:
            return Response({'error': 'Porteur parameter is incorrect!'}, status=status.HTTP_400_BAD_REQUEST)

        payment_type = str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_caisse_eusko_bdc'])
        currency = str(settings.CYCLOS_CONSTANTS['currencies']['eusko'])
        description = 'Sortie caisse eusko - {} - {}'.format(bdc_code, bdc_name)

    else:
        return Response({'error': 'Mode parameter is incorrect!'}, status=status.HTTP_400_BAD_REQUEST)

    # Enregistrer la remise d'espèces
    cash_deposit_data = {
        'type': payment_type,
        'amount': request.data['deposit_amount'],  # montant total calculé
        'currency': currency,
        'from': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        'to': 'SYSTEM',  # System account
        'description': description
    }

    if request.data['mode'] == 'sortie-caisse-eusko':
        cash_deposit_data.update({'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur']),
                'linkedEntityValue': porteur  # ID du porteur
            },
        ]})

    cyclos.post(method='payment/perform', data=cash_deposit_data)

    for payment in request.data['selected_payments']:
        # Passer tous les paiements à l'origine du dépôt à l'état "Remis à Euskal Moneta"
        transfer_change_status_data = {
            'transfer': payment['id'],  # ID du paiement (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['remis_a_euskal_moneta'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=transfer_change_status_data)

    return Response(cash_deposit_data)


@api_view(['POST'])
def sortie_retour_eusko(request):
    """
    sortie_retour_eusko
    """
    serializer = serializers.SortieRetourEuskoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        login_bdc = request.data['login_bdc']
        cyclos_mode = 'gi_bdc'
    except KeyError:
        login_bdc = None
        cyclos_mode = 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode, login_bdc=login_bdc)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        bdc_code = request.data['login_bdc']
        bdc_name = dolibarr.get(model='users', sqlfilters="login='{}'".format(bdc_code))[0]['lastname']
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except (IndexError, KeyError):
        return Response({'error': 'Unable to get user data from your user!'}, status=status.HTTP_400_BAD_REQUEST)

    for payment in request.data['selected_payments']:
        try:
            adherent_id = [
                value['linkedEntityValue']['id']
                for value in payment['customValues']
                if value['field']['id'] == str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']) and
                value['field']['internalName'] == 'adherent'
            ][0]
        except (KeyError, IndexError):
            return Response({'error': 'Unable to get adherent_id from one of your selected_payments!'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Enregistrer les retours d'eusko
        sortie_retour_eusko_data = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_retours_eusko_bdc']),
            'amount': payment['amount'],  # montant de l'opération correspondante
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
            'from': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
            'to': 'SYSTEM',  # System account
            'customValues': [
                {
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                    'linkedEntityValue': adherent_id,  # ID de l'adhérent
                },
                {
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur']),
                    'linkedEntityValue': request.data['porteur']  # ID du porteur
                },
            ],
            # "Sortie retour d'eusko - Bxxx - Nom du BDC
            # Opération de Z12345 - Nom du prestataire" -> description du payment initial
            'description': 'Sortie retours eusko - {} - {}\n{}'.format(
                bdc_code, bdc_name, payment['description'])
        }
        cyclos.post(method='payment/perform', data=sortie_retour_eusko_data)

        # Passer tous les paiements à l'origine du dépôt à l'état "Remis à Euskal Moneta"
        transfer_change_status_data = {
            'transfer': payment['id'],  # ID du paiement (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['remis_a_euskal_moneta'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=transfer_change_status_data)

    return Response(request.data)


@api_view(['POST'])
def depot_eusko_numerique(request):
    """
    depot-eusko-numerique
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.DepotEuskoNumeriqueSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    member_cyclos_id = cyclos.get_member_id_from_login(request.data['member_login'])

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        dolibarr_member = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.data['member_login']))[0]
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except IndexError:
        return Response({'error': 'Unable to fetch Dolibarr data! Maybe your credentials are invalid!?'},
                        status=status.HTTP_400_BAD_REQUEST)

    if dolibarr_member['type'].lower() == 'particulier':
        member_name = '{} {}'.format(dolibarr_member['firstname'], dolibarr_member['lastname'])
    else:
        member_name = dolibarr_member['company']

    # Retour des Eusko billets
    retour_eusko_billets_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['depot_de_billets']),
        'amount': request.data['amount'],  # montant saisi
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': 'SYSTEM',
        'to': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                'linkedEntityValue': member_cyclos_id  # ID de l'adhérent
            },
        ],
        'description': 'Dépôt - {} - {}'.format(request.data['member_login'], member_name),
    }
    cyclos.post(method='payment/perform', data=retour_eusko_billets_data)

    # Crédit du compte Eusko numérique du prestataire
    depot_eusko_numerique_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['credit_du_compte']),
        'amount': request.data['amount'],  # montant saisi
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': 'SYSTEM',
        'to': member_cyclos_id,  # ID de l'adhérent
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['bdc']),
                'linkedEntityValue': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
            },
        ],
        'description': 'Dépôt',
    }
    cyclos.post(method='payment/perform', data=depot_eusko_numerique_data)

    return Response(depot_eusko_numerique_data)


@api_view(['POST'])
def retrait_eusko_numerique(request):
    """
    Retrait eusko: numerique vers billets
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.RetraitEuskoNumeriqueSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    member_cyclos_id = cyclos.get_member_id_from_login(request.data['member_login'])

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        dolibarr_member = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.data['member_login']))[0]
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except IndexError:
        return Response({'error': 'Unable to fetch Dolibarr data! Maybe your credentials are invalid!?'},
                        status=status.HTTP_400_BAD_REQUEST)

    if dolibarr_member['type'].lower() == 'particulier':
        member_name = '{} {}'.format(dolibarr_member['firstname'], dolibarr_member['lastname'])
    else:
        member_name = dolibarr_member['company']

    # Verify whether or not member account has enough money
    member_account_summary_query = [member_cyclos_id, None]  # ID de l'adhérent
    member_account_summary_res = cyclos.post(method='account/getAccountsSummary', data=member_account_summary_query)

    try:
        if (member_account_summary_res['result'][0]['type']['id'] !=
           str(settings.CYCLOS_CONSTANTS['account_types']['compte_d_adherent'])):
            return Response({'error': "Unable to fetch account data!"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except (KeyError, IndexError):
        return Response({'error': "Unable to fetch account data!"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        if float(member_account_summary_res['result'][0]['status']['balance']) < float(request.data['amount']):
            return Response({'error': "error-member-not-enough-money"})
    except (KeyError, IndexError):
        return Response({'error': "Unable to fetch account data!"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Verify whether or not bdc cash stock have enough money
    bdc_account_summary_query = [cyclos.user_bdc_id, None]  # ID de l'utilisateur Bureau de change
    bdc_account_summary_res = cyclos.post(method='account/getAccountsSummary', data=bdc_account_summary_query)

    bdc_account_summary_data = [
        item
        for item in bdc_account_summary_res['result']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['account_types']['stock_de_billets_bdc'])][0]

    if float(bdc_account_summary_data['status']['balance']) < float(request.data['amount']):
        return Response({'error': "error-bureau-not-enough-money"})

    # Débit du compte
    debit_compte_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['retrait_du_compte']),
        'amount': request.data['amount'],  # montant saisi
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': member_cyclos_id,  # ID de l'adhérent
        'to': 'SYSTEM',
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['bdc']),
                'linkedEntityValue': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
            },
        ],
        'description': 'Retrait',
    }
    cyclos.post(method='payment/perform', data=debit_compte_data)

    # Retrait des billets
    retrait_billets_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['retrait_de_billets']),
        'amount': request.data['amount'],  # montant saisi
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        'to': 'SYSTEM',
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                'linkedEntityValue': member_cyclos_id,  # ID de l'adhérent
            },
        ],
        'description': 'Retrait - {} - {}'.format(request.data['member_login'], member_name),
    }
    cyclos.post(method='payment/perform', data=retrait_billets_data)

    return Response(retrait_billets_data)


@api_view(['GET'])
def payments_available_for_entree_stock(request):
    """
    payments_available_for_entree_stock
    """
    serializer = serializers.PaymentsAvailableEntreeStockSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        login_bdc = request.query_params['login_bdc']
        cyclos_mode = 'gi_bdc'
    except KeyError:
        login_bdc = None
        cyclos_mode = 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode, login_bdc=login_bdc)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # account/searchAccountHistory
    search_history_data = {
        'account': str(settings.CYCLOS_CONSTANTS['system_accounts']['compte_de_transit']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'SYSTEM',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher'])
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
    }
    accounts_summaries_res = cyclos.post(method='account/searchAccountHistory', data=search_history_data)

    # Filter out the results that are not "Sortie coffre" and items that are not for this BDC
    accounts_summaries_data = [
        item
        for item in accounts_summaries_res['result']['pageItems']
        for value in item['customValues']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_coffre']) and
        value['field']['internalName'] == 'bdc' and
        value['linkedEntityValue']['id'] == cyclos.user_bdc_id
    ]

    return Response(accounts_summaries_data)


@api_view(['POST'])
def change_password(request):
    """
    change_password
    """
    serializer = serializers.ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        cyclos_mode = request.data['cyclos_mode']
    except KeyError:
        cyclos_mode = 'bdc'

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode=cyclos_mode)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # password/change
    change_password_data = {
        'user': cyclos.user_id,  # ID de l'utilisateur
        'type': str(settings.CYCLOS_CONSTANTS['password_types']['login_password']),
        'oldPassword': request.data['old_password'],  # saisi par l'utilisateur
        'newPassword': request.data['new_password'],  # saisi par l'utilisateur
        'confirmNewPassword': request.data['confirm_password'],  # saisi par l'utilisateur
    }

    return Response(cyclos.post(method='password/change', data=change_password_data))


@api_view(['POST'])
def change_euro_eusko_numeriques(request):
    """
    Change d'€ en eusko numériques pour un adhérent via un BDC.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ChangeEuroEuskoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    member_cyclos_id = cyclos.get_member_id_from_login(request.data['member_login'])

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        dolibarr_member = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.data['member_login']))[0]
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except IndexError:
        return Response({'error': 'Unable to fetch Dolibarr data! Maybe your credentials are invalid!?'},
                        status=status.HTTP_400_BAD_REQUEST)

    if dolibarr_member['type'].lower() == 'particulier':
        member_name = '{} {}'.format(dolibarr_member['firstname'], dolibarr_member['lastname'])
    else:
        member_name = dolibarr_member['company']

    # payment/perform
    bdc_query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_bdc_versement_des_euro']),
        'amount': request.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': 'SYSTEM',
        'to': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                'linkedEntityValue': member_cyclos_id  # ID de l'adhérent
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['mode_de_paiement']),
                'enumeratedValues': request.data['payment_mode']  # ID du mode de paiement (chèque ou espèces)
            },
        ],
        # "Change - E12345 - Nom de l'adhérent - Mode de paiement"
        'description': 'Change numérique - {} - {} - {}'.format(
            request.data['member_login'], member_name, request.data['payment_mode_name']),
    }
    cyclos.post(method='payment/perform', data=bdc_query_data)

    # payment/perform
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['credit_du_compte']),
        'amount': request.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': 'SYSTEM',
        'to': member_cyclos_id,  # ID de l'adhérent
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['bdc']),
                'linkedEntityValue': cyclos.user_bdc_id  # ID de l'utilisateur Bureau de change
            },
        ],
        # "Change numérique - Nom du BDC"
        'description': 'Change numérique - {}'.format(request.user.profile.lastname),
    }
    cyclos.post(method='payment/perform', data=query_data)

    return Response({'status': 'OK'})
