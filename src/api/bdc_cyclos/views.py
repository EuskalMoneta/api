import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from bdc_cyclos.serializers import EntreeStockBDCSerializer
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
    return Response(accounts_summaries_data)
    res = {}

    # Stock de billets: stock_de_billets_bdc
    # Caisse euros: caisse_euro_bdc
    # Caisse eusko: caisse_eusko_bdc
    # Retour eusko: retours_d_eusko_bdc
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

    serializer = EntreeStockBDCSerializer(data=request.data)
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
                'field': request.data['porteur'],
                'linkedEntityValue': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur'])
            },
        ],
    }

    return Response(cyclos.post(method='payment/perform', data=query_data))
