from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from cyclos_api import CyclosAPI, CyclosAPIException
from gestioninterne import serializers


@api_view(['POST'])
def sortie_coffre(request):
    """
    sortie_coffre
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.SortieCoffreSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    sortie_coffre_query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_coffre']),
        'amount': request.data['amount'],  # montant saisi par l'utilisateur
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': 'SYSTEM',
        'to': 'SYSTEM',
        'customValues': [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['bdc']),
                'linkedEntityValue': request.data['bdc_dest']  # ID du BDC destinataire (sélectionné par l'utilisateur)
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur']),
                'linkedEntityValue': request.data['porteur']  # porteur sélectionné par l'utilisateur
            },
        ],
        'description': request.data['description'],        # description saisie par l'utilisateur
    }

    return Response(cyclos.post(method='payment/perform', data=sortie_coffre_query_data))
