import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bdc_cyclos.serializers import ChangeEuroEuskoSerializer, IOStockBDCSerializer
from cyclos_api import CyclosAPI, CyclosAPIException

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
        res[filter_key]['currency'] = data['id']
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

    query_data = {'keywords': request.data['member_login']}
    try:
        member_login_data = cyclos.post(method='user/search', data=query_data)
        member_cyclos_id = member_login_data['result']['pageItems'][0]['id']
    except CyclosAPIException:
        raise CyclosAPIException(detail='Unable to connect to Cyclos!')
    except (KeyError, IndexError):
        raise CyclosAPIException(detail='Unable to fetch Cyclos data! Maybe your credentials are invalid!?')

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
