from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from cyclos_api import CyclosAPI, CyclosAPIException


@api_view(['GET'])
def payment_modes(request):
    """
    List all payment modes.
    """
    return Response([{'value': 'Euro-LIQ', 'label': 'Espèces (€)',
                      'cyclos_id': str(settings.CYCLOS_CONSTANTS['payment_modes']['especes'])},
                     {'value': 'Euro-CHQ', 'label': 'Chèque (€)',
                      'cyclos_id': str(settings.CYCLOS_CONSTANTS['payment_modes']['cheque'])},
                     {'value': 'Eusko-LIQ', 'label': 'Eusko',
                      'cyclos_id': str(settings.CYCLOS_CONSTANTS['payment_modes']['especes'])}
                     ])


@api_view(['GET'])
def porteurs_eusko(request):
    """
    List porteurs d'euskos.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # user/search for group = 'Porteurs'
    porteurs_data = cyclos.post(method='user/search',
                                data={'groups': [settings.CYCLOS_CONSTANTS['groups']['porteurs']]})
    res = [{'label': item['display'], 'value': item['id']}
           for item in porteurs_data['result']['pageItems']]

    return Response(res)


@api_view(['GET'])
def deposit_banks(request):
    """
    List available banks.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # user/search for group = 'Banques de dépot'
    banks_data = cyclos.post(method='user/search',
                             data={'groups': [settings.CYCLOS_CONSTANTS['groups']['banques_de_depot']]})
    res = [{'label': item['display'], 'value': item['id'], 'shortLabel': item['shortDisplay']}
           for item in banks_data['result']['pageItems']]

    return Response(res)
