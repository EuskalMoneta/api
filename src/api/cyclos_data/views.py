import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from cyclos_api import CyclosAPI, CyclosAPIException

log = logging.getLogger()


@api_view(['GET'])
def accounts_summaries(request):
    """
    List all accounts_summaries for this BDC user.
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        Response({'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # getCurrentUser => get ID for current user
    try:
        user_profile = cyclos.post(model='user/getCurrentUser', data=[])
        user_id = user_profile['result']['id']
    except CyclosAPIException:
        Response({'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)
    except KeyError:
        Response({'Unable to fetch Cyclos data! Maybe your credentials are invalid!?'},
                 status=status.HTTP_400_BAD_REQUEST)

    # user/load for this ID to get field BDC ID
    try:
        user_data = cyclos.post(model='user/load', data=user_id)
        user_bdc_id = [item['linkedEntityValue']['id']
                       for item in user_data['result']['customValues']
                       if item['field']['id'] ==
                       str(settings.CYCLOS_CONSTANTS['user_custom_fields']['bdc'])][0]
    except CyclosAPIException:
        Response({'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)
    except (KeyError, IndexError):
        Response({'Unable to fetch Cyclos data! Maybe your credentials are invalid!?'},
                 status=status.HTTP_400_BAD_REQUEST)

    # account/getAccountsSummary
    query_data = [user_bdc_id, None]
    accounts_summaries_data = cyclos.post(model='account/getAccountsSummary', data=query_data)
    res = {}

    # Stock de billets: stock_de_billets_bdc
    # Caisse euros: caisse_euro_bdc
    # Caisse eusko: caisse_eusko_bdc
    # Retour eusko: retours_d_eusko_bdc
    filter_keys = ['stock_de_billets_bdc',
                   'caisse_euro_bdc',
                   'caisse_eusko_bdc',
                   'retours_d_eusko_bdc']

    for filter_key in filter_keys:
        data = [item
                for item in accounts_summaries_data['result']
                if item['type']['id'] ==
                str(settings.CYCLOS_CONSTANTS['account_types'][filter_key])][0]

        res[filter_key] = {}
        res[filter_key]['currency'] = data['id']
        res[filter_key]['balance'] = float(data['status']['balance'])
        res[filter_key]['currency'] = data['currency']['symbol']
        res[filter_key]['type'] = {'name': data['type']['name'],
                                   'id': filter_key}

    return Response(res)
