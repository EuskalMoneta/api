import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bdc_cyclos.serializers import (AccountsHistorySerializer, ChangeEuroEuskoSerializer,
                                    IOStockBDCSerializer, ReconversionSerializer)
from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException

log = logging.getLogger()


@api_view(['GET'])
def accounts_summaries(request):
    """
    List all accounts_summaries for this BDC user.
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='bdc')
    except CyclosAPIException:
        return Response({'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

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


@api_view(['POST'])
def entree_stock(request):
    """
    Enregistre une entrée dans le stock billets d'un BDC.
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='bdc')
    except CyclosAPIException:
        return Response({'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = IOStockBDCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # payment/perform
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['entree_stock_bdc']),
        'amount': request.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': 'SYSTEM',
        'to': cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
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
def sortie_stock(request):
    """
    Enregistre une sortie dans le stock billets d'un BDC.
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='bdc')
    except CyclosAPIException:
        return Response({'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = IOStockBDCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

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
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='bdc')
    except CyclosAPIException:
        return Response({'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ChangeEuroEuskoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        dolibarr_member = dolibarr.get(model='members', login=request.data['member_login'])[0]
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except IndexError:
        return Response({'error': 'Unable to fetch Dolibarr data! Maybe your credentials are invalid!?'},
                        status=status.HTTP_400_BAD_REQUEST)

    if dolibarr_member['type'].lower() == 'entreprise':
        return Response({'error': 'Forbidden, reconversion operation if not available for business members!'},
                        status=status.HTTP_403_FORBIDDEN)

    member_cyclos_id = cyclos.get_member_id_from_login(request.data['member_login'])

    # payment/perform
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_billets_versement_des_euro']),
        'amount': request.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': 'SYSTEM',
        'to': cyclos.user_bdc_id,         # ID de l'utilisateur Bureau de change
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                'linkedEntityValue': member_cyclos_id  # ID de l'adhérent
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['mode_de_paiement']),
                'enumeratedValues': request.data['payment_mode']   # ID du mode de paiement (chèque ou espèces)
            },
        ],
        'description': 'Change - {}'.format(request.data['member_login']),
    }

    return Response(cyclos.post(method='payment/perform', data=query_data))


@api_view(['POST'])
def reconversion(request):
    """
    Reconversion eusko en euros pour un adhérent (prestataire) via un BDC.
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ReconversionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        dolibarr_member = dolibarr.get(model='members', login=request.data['member_login'])[0]
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except IndexError:
        return Response({'error': 'Unable to fetch Dolibarr data! Maybe your credentials are invalid!?'},
                        status=status.HTTP_400_BAD_REQUEST)

    if dolibarr_member['type'].lower() == 'entreprise':
        return Response({'error': 'Forbidden, reconversion operation if not available for business members!'},
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
                'enumeratedValues': request.data['facture']  # ID du mode de paiement (chèque ou espèces)
            },
        ],
        'description': 'Reconversion - {}'.format(request.data['member_login']),
    }

    return Response(cyclos.post(method='payment/perform', data=query_data))


@api_view(['GET'])
def accounts_history(request):
    """
    Reconversion eusko en euros pour un adhérent (prestataire) via un BDC.
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='bdc')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = AccountsHistorySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # account/getAccountsSummary
    query_data = [cyclos.user_bdc_id, None]  # ID de l'utilisateur Bureau de change
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    # FYI available account types are:
    account_types = ['stock_de_billets_bdc', 'caisse_euro_bdc', 'caisse_eusko_bdc', 'retours_d_eusko_bdc']

    if request.query_params['account_type'] not in account_types:
        return Response({'error': 'The account_type you provided: {}, is not available for this query!'
                         .format(request.query_params['account_type'])},
                        status=status.HTTP_400_BAD_REQUEST)

    data = [item
            for item in accounts_summaries_data['result']
            if item['type']['id'] ==
            str(settings.CYCLOS_CONSTANTS['account_types'][request.query_params['account_type']])][0]

    # account/searchAccountHistory
    search_history_data = {
        'account': data['id'],  # ID du compte
        'orderBy': 'DATE_DESC',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }

    return Response(cyclos.post(method='account/searchAccountHistory', data=search_history_data))
