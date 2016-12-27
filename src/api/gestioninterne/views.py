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
        return Response(query_data['result']['pageItems'])


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
            bdc = {'id': payment['relatedAccount']['owner']['id'],
                   'login': str(payment['relatedAccount']['owner']['shortDisplay']).replace('_BDC', ''),
                   'name': str(payment['relatedAccount']['owner']['display']).replace(' (BDC)', '')}
        except KeyError:
            return Response({'error': 'Unable to get bdc info from one of your selected_payments!'},
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
        # Il faut reprendre la description de l'opération d'origine,
        # et remplacer "Sortie stock" ou "Sortie retours eusko" par "Entrée coffre".
        # Exemple:
        # "Entrée coffre - Bxxx - Nom du BDC'"
        try:
            if 'Sortie stock' in payment['description']:
                description = payment['description'].replace('Sortie stock', 'Entrée coffre')
            else:
                description = 'Entrée coffre - {} - {}'.format(bdc['login'], bdc['name'])
        except KeyError:
            description = 'Entrée coffre - {} - {}'.format(bdc['login'], bdc['name'])

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

        # Dans le cas d'une sortie retours eusko
        if payment['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_retours_eusko_bdc']):
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
            try:
                if 'Sortie retours eusko' in payment['description']:
                    description = payment['description'].replace('Sortie retours eusko', 'Entrée coffre')
                else:
                    description = "Entrée coffre - {} - {}\n{}".format(
                        bdc['login'], bdc['name'], payment['description'])
            except KeyError:
                description = "Entrée coffre - {} - {}\n{}".format(bdc['login'], bdc['name'], payment['description'])

        payment_query_data = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['entree_coffre']),
            'amount': payment['amount'],  # montant de l'opération d'origine
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
            'from': 'SYSTEM',
            'to': 'SYSTEM',
            'customValues': custom_values,
            'description': description,  # voir explications détaillées ci-dessus
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
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['sortie_caisse_eusko_bdc'])
    ]
    return Response(filtered_data)


@api_view(['POST'])
def validate_history(request):
    """
    validate_history
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


@api_view(['GET'])
def payments_available_for_banques(request):
    """
    payments_available_for_banques:
    virements & rapprochements
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.PaymentsAvailableBanqueSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    bank_user_query = {
        'keywords': request.query_params['bank_name'],  # bank_name = shortDisplay from Cyclos
    }
    try:
        bank_user_data = cyclos.post(method='user/search', data=bank_user_query)['result']['pageItems'][0]

        bank_account_query = [bank_user_data['id'], None]
        bank_account_data = cyclos.post(method='account/getAccountsSummary', data=bank_account_query)['result'][0]

        bank_account_id = bank_account_data['id']
    except (KeyError, IndexError):
                return Response({'error': 'Unable to get bank data for the provided bank_name!'},
                                status=status.HTTP_400_BAD_REQUEST)

    bank_history_query = {
        'account': bank_account_id,  # ID du compte
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }

    if request.query_params['mode'] == 'virement':
        bank_history_query.update({'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ]})
    elif request.query_params['mode'] == 'rapprochement':
        bank_history_query.update({'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher']),
        ]})
    else:
        return Response({'error': 'The mode you privded is not supported by this endpoint!'},
                        status=status.HTTP_400_BAD_REQUEST)

    bank_history_data = cyclos.post(method='account/searchAccountHistory', data=bank_history_query)
    if bank_history_data['result']['totalCount'] == 0:
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Il faut filtrer et ne garder que les paiements de type depot_en_banque
    filtered_data = [
        item
        for item in bank_history_data['result']['pageItems']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['depot_en_banque'])
    ]
    return Response(filtered_data)


@api_view(['POST'])
def validate_banques_virement(request):
    """
    validate_banques_virement
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ValidateBanquesVirementsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    bank_user_query = {
        'keywords': request.data['bank_name'],  # bank_name = shortDisplay from Cyclos
    }
    try:
        bank_fullname = cyclos.post(method='user/search', data=bank_user_query)['result']['pageItems'][0]['display']
    except (KeyError, IndexError):
                return Response({'error': 'Unable to get bank data for the provided bank_name!'},
                                status=status.HTTP_400_BAD_REQUEST)

    try:
        user_id = cyclos.post(method='user/getCurrentUser', data=[])['result']['id']
    except KeyError:
        return Response({'error': 'Unable to get current user Cyclos data!'}, status=status.HTTP_400_BAD_REQUEST)

    # Cotisations
    cotisation_query = {
        'type': str(
            settings.CYCLOS_CONSTANTS['payment_types']['virement_de_banque_de_depot_vers_le_compte_de_debit_en_euro']),
        'amount': 60,  # montant du virement "Cotisations"
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': user_id,  # ID de l'utilisateur Banque de dépôt
        'to': 'SYSTEM',
        'description': '{} - Cotisations'.format(bank_fullname)  # nom de la banque de dépôt
    }
    cyclos.post(method='payment/perform', data=cotisation_query)

    # Ventes
    ventes_query = {
        'type': str(
            settings.CYCLOS_CONSTANTS['payment_types']['virement_de_banque_de_depot_vers_le_compte_de_debit_en_euro']),
        'amount': 12,  # montant du virement "Ventes"
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': user_id,  # ID de l'utilisateur Banque de dépôt
        'to': 'SYSTEM',
        'description': '{} - Ventes'.format(bank_fullname)  # nom de la banque de dépôt
    }
    cyclos.post(method='payment/perform', data=ventes_query)

    # Change eusko billet
    change_eusko_billet_query = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_banque_de_depot_vers_compte_dedie']),
        'amount': 2450,  # montant du virement "Changes eusko billets"
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': user_id,  # ID de l'utilisateur Banque de dépôt
        'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']),
        'description': '{} - Changes Eusko billet'.format(bank_fullname)  # nom de la banque de dépôt
    }
    cyclos.post(method='payment/perform', data=change_eusko_billet_query)

    # Change eusko numérique
    change_eusko_numerique_query = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_banque_de_depot_vers_compte_dedie']),
        'amount': 180,  # montant du virement "Changes eusko numérique"
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': user_id,  # ID de l'utilisateur Banque de dépôt
        'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']),
        'description': '{} - Changes Eusko numérique'.format(bank_fullname)  # nom de la banque de dépôt
    }
    cyclos.post(method='payment/perform', data=change_eusko_numerique_query)

    for payment in request.data['selected_payments']:
        # Passer l'opération à l'état "Virements faits"
        status_query_data = {
            'transfer': payment['id'],  # ID de l'opération d'origine (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_faits'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=status_query_data)

    return Response(request.data['selected_payments'])


@api_view(['GET'])
def payments_available_depots_retraits(request):
    """
    payments_available_depots_retraits
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    res = []

    depots_query = {
        'account': str(settings.CYCLOS_CONSTANTS['account_types']['compte_des_billets_en_circulation']),
        'orderBy': 'DATE_DESC',
        'direction': 'DEBIT',
        'toNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }
    depots_data = cyclos.post(method='account/searchAccountHistory', data=depots_query)

    # Il faut filtrer et ne garder que les opérations de type depot_de_billets
    depots_filtered_data = [
        item
        for item in depots_data['result']['pageItems']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['depot_de_billets'])
    ]
    res.extend(depots_filtered_data)

    retraits_query = {
        'account': str(settings.CYCLOS_CONSTANTS['account_types']['compte_des_billets_en_circulation']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }
    retraits_data = cyclos.post(method='account/searchAccountHistory', data=retraits_query)

    # Il faut filtrer et ne garder que les opérations de type retrait_de_billets
    retraits_filtered_data = [
        item
        for item in retraits_data['result']['pageItems']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['retrait_de_billets'])
    ]
    res.extend(retraits_filtered_data)

    return Response(res) if res else Response({}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def validate_depots_retraits(request):
    """
    validate_depots_retraits
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ValidateDepotsRetraitsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # 1) Enregistrer le virement :

    # Si montant_total_depots > montant_total_retraits
    if request.data['montant_total_depots'] > request.data['montant_total_retraits']:
        virement_query = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_entre_comptes_dedies']),
            'amount': request.data['montant_total_depots'] - request.data['montant_total_retraits'],
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']),
            'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']),
            'description': "Régularisation entre comptes dédiés suite à des dépôts et retraits d'eusko.",
        }
        cyclos.post(method='payment/perform', data=virement_query)

    elif request.data['montant_total_depots'] > request.data['montant_total_retraits']:
        # Si montant_total_depots < montant_total_retraits
        virement_query = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_entre_comptes_dedies']),
            'amount': request.data['montant_total_retraits'] - request.data['montant_total_depots'],
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']),
            'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']),
            'description': "Régularisation entre comptes dédiés suite à des dépôts et retraits d'eusko.",
        }
        cyclos.post(method='payment/perform', data=virement_query)

    # 2) Passer chaque opération sélectionnée à l'état "Virements faits" :
    for payment in request.data['selected_payments']:
        # Passer l'opération à l'état "Virements faits"
        status_query_data = {
            'transfer': payment['id'],  # ID de l'opération d'origine (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_faits'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=status_query_data)

    return Response(request.data['selected_payments'])


@api_view(['GET'])
def payments_available_for_reconversions(request):
    """
    payments_available_for_reconversions
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    res = []

    # Reconversions d'eusko billets
    query_billets = {
        'account': str(settings.CYCLOS_CONSTANTS['account_types']['compte_des_billets_en_circulation']),
        'orderBy': 'DATE_DESC',
        'direction': 'DEBIT',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }
    query_billets_data = cyclos.post(method='account/searchAccountHistory', data=query_billets)

    # Il faut filtrer et ne garder que les paiements de type reconversion_billets_versement_des_eusko
    filtered_billets_data = [
        item
        for item in query_billets_data['result']['pageItems']
        if item['type']['id'] ==
        str(settings.CYCLOS_CONSTANTS['payment_types']['reconversion_billets_versement_des_eusko'])
    ]
    res.extend(filtered_billets_data)

    # Reconversions d'eusko numériques
    query_numeriques = {
        'account': str('-7371965201600299221'),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
    }
    query_numeriques_data = cyclos.post(method='account/searchAccountHistory', data=query_numeriques)

    # Il faut filtrer et ne garder que les paiements de type reconversion_numerique
    filtered_numeriques_data = [
        item
        for item in query_numeriques_data['result']['pageItems']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['reconversion_numerique'])
    ]
    res.extend(filtered_numeriques_data)

    return Response(res) if res else Response({}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def validate_reconversions(request):
    """
    validate_reconversions
    """
    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ValidateReconversionsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # 1) Enregistrer le virement pour les eusko billet
    billets_query = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_compte_dedie_vers_compte_debit_euro']),
        # montant total des reconversions billet sélectionnées
        'amount': float(request.data['montant_total_billets']),
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']),
        'to': 'SYSTEM',
        'description': 'Reconversions - Remboursement des prestataires + commission pour Euskal Moneta.',
    }
    cyclos.post(method='payment/perform', data=billets_query)

    # 2) Enregistrer le virement pour les eusko numériques
    numeriques_query = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_compte_dedie_vers_compte_debit_euro']),
        # montant total des reconversions numériques sélectionnées
        'amount': float(request.data['montant_total_numerique']),
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
        'from': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']),
        'to': 'SYSTEM',
        'description': 'Reconversions - Remboursement des prestataires + commission pour Euskal Moneta.',
    }
    cyclos.post(method='payment/perform', data=numeriques_query)

    # 3) Passer chaque opération sélectionnée à l'état "Virements faits" :
    for payment in request.data['selected_payments']:
        # Passer l'opération à l'état "Virements faits"
        status_query_data = {
            'transfer': payment['id'],  # ID de l'opération d'origine (récupéré dans l'historique)
            'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_faits'])
        }
        cyclos.post(method='transferStatus/changeStatus', data=status_query_data)

    return Response(request.data['selected_payments'])
