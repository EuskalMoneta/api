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


@api_view(['GET'])
def payments_available_for_entree_coffre(request):
    """
    payments_available_for_entree_coffre
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    entree_coffre_query = {
        'account': str(settings.CYCLOS_CONSTANTS['account_types']['compte_de_transit']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }
    query_data = cyclos.post(method='account/searchAccountHistory', data=entree_coffre_query)
    if query_data['result']['totalCount'] == 0:
        return Response({}, status=status.HTTP_204_NO_CONTENT)
    else:
        return Response(query_data)


@api_view(['POST'])
def entree_coffre(request):
    """
    entree_coffre
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.GenericHistoryValidationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    for payment in request.data['selected_payments']:
        try:
            bdc = [
                {'id': value['linkedEntityValue']['id'], 'name': value['linkedEntityValue']['name']}
                for value in payment['customValues']
                if value['field']['id'] == str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['bdc']) and
                value['field']['internalName'] == 'bdc'
            ][0]
        except (KeyError, IndexError):
            return Response({'error': 'Unable to get bdc_id from one of your selected_payments!'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            porteur_id = [
                value['linkedEntityValue']['id']
                for value in payment['customValues']
                if value['field']['id'] == str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur']) and
                value['field']['internalName'] == 'porteur'
            ][0]
        except (KeyError, IndexError):
            return Response({'error': 'Unable to get porteur_id from one of your selected_payments!'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Comment construire le champ Description de l'entrée coffre ?
        # Si l'opération d'origine est une sortie stock BDC, la description doit être :
        # "Entrée coffre - Bxxx - Nom du BDC'"
        login_bdc = ''
        description = "Entrée coffre - {} - {}".format(login_bdc, bdc['name'])

        custom_values = [
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['bdc']),
                'linkedEntityValue': bdc['id']  # ID du BDC d'origine
            },
            {
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['porteur']),
                'linkedEntityValue': porteur_id  # porteur de l'opération d'origine
            },
        ]
        operation_type = str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_stock_bdc'])

        if payment['mode'] == 'retour-eusko':
            try:
                adherent_id = [
                    value['linkedEntityValue']['id']
                    for value in payment['customValues']
                    if value['field']['id'] == str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']) and  # noqa
                    value['field']['internalName'] == 'adherent'
                ][0]
            except (KeyError, IndexError):
                return Response({'error': 'Unable to get adherent_id from one of your selected_payments!'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Le champ Adhérent n'est présent que pour les entrées coffre correspondant des retours d'eusko
            custom_values.append({
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent_facultatif']),
                'linkedEntityValue': adherent_id  # adhérent associé à l'opération d'origine
            })

            # Si l'opération d'origine est une sortie retour d'eusko, la description doit être, sur 2 lignes :
            # "Entrée coffre - Bxxx - Nom du BDC\n
            # Opération de Z12345 - Nom du prestataire" où
            # "Opération" est "Reconversion" ou "Dépôt sur le compte", selon le type de l'opération d'origine.
            description = "Entrée coffre - {} - {}\n{}".format(login_bdc, bdc['name'], payment['description'])
            operation_type = str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_retours_eusko_bdc'])

        payment_query_data = {
            'type': operation_type,
            'amount': payment['amount'],  # montant de l'opération d'origine
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
            'from': 'SYSTEM',
            'to': 'SYSTEM',
            'customValues': custom_values,
            'description': description,  # voir explications détaillées ci-dessous
        }
        # Enregistrer l'Entrée coffre dans Cyclos
        cyclos.post(method='payment/perform', data=payment_query_data)

        # Passer l'opération à l'état "Rapproché"
        status_query_data = {
            'transfer': payment['id'],  # ID de l'opération d'origine (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['rapproche'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=status_query_data)

    return Response(request.data['selected_payments'])


@api_view(['GET'])
def payments_available_for_entrees_euro(request):
    """
    payments_available_for_entrees_euro
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query = {
        'account': str(settings.CYCLOS_CONSTANTS['account_types']['compte_de_debit_euro']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }

    query_data = cyclos.post(method='account/searchAccountHistory', data=query)
    if query_data['result']['totalCount'] == 0:
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Il faut filtrer et ne garder que les paiements de type remise_d_euro_en_caisse
    filtered_data = [
        item
        for item in query_data['result']['pageItems']
        for value in item['customValues']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['remise_d_euro_en_caisse'])
    ]
    return Response(filtered_data)


@api_view(['GET'])
def payments_available_for_entrees_eusko(request):
    """
    payments_available_for_entrees_eusko
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query = {
        'account': str(settings.CYCLOS_CONSTANTS['account_types']['compte_des_billets_en_circulation']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }

    query_data = cyclos.post(method='account/searchAccountHistory', data=query)
    if query_data['result']['totalCount'] == 0:
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Il faut filtrer et ne garder que les paiements de type sortie_caisse_eusko_bdc
    filtered_data = [
        item
        for item in query_data['result']['pageItems']
        for value in item['customValues']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_caisse_eusko_bdc'])
    ]
    return Response(filtered_data)


@api_view(['POST'])
def validate_entrees_eusko_euro(request):
    """
    validate_entrees_eusko_euro
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.GenericHistoryValidationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    for payment in request.data['selected_payments']:
        # Passer l'opération à l'état "Rapproché"
        status_query_data = {
            'transfer': payment['id'],  # ID de l'opération d'origine (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['rapproche'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=status_query_data)

    return Response(request.data['selected_payments'])
