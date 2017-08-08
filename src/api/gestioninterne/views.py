import logging

from datetime import datetime, timedelta

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException
from gestioninterne import serializers

log = logging.getLogger()


@api_view(['POST'])
def sortie_coffre(request):
    """
    sortie_coffre
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
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
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    entree_coffre_query = {
        'account': str(settings.CYCLOS_CONSTANTS['system_accounts']['compte_de_transit']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
    }
    query_data = cyclos.post(method='account/searchAccountHistory', data=entree_coffre_query)
    if query_data['result']['totalCount'] == 0:
        return Response(status=status.HTTP_204_NO_CONTENT)
    else:
        return Response(query_data['result']['pageItems'])


@api_view(['POST'])
def entree_coffre(request):
    """
    entree_coffre
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
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
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query = {
        'account': str(settings.CYCLOS_CONSTANTS['system_accounts']['compte_de_debit_euro']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
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
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query = {
        'account': str(settings.CYCLOS_CONSTANTS['system_accounts']['compte_des_billets_en_circulation']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
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
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
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
    virements, rapprochements et historique des banques
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
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
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
    }

    if request.query_params['mode'] == 'virement':
        bank_history_query.update({'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ], 'fromNature': 'USER'})
    elif request.query_params['mode'] == 'rapprochement':
        bank_history_query.update({'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['a_rapprocher']),
        ], 'fromNature': 'USER'})
    elif request.query_params['mode'] == 'historique':
        pass
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
    ]
    return Response(filtered_data)


@api_view(['POST'])
def validate_banques_virement(request):
    """
    validate_banques_virement
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ValidateBanquesVirementsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    bank_user_query = {
        'keywords': request.data['bank_name'],  # bank_name = shortDisplay from Cyclos
    }
    try:
        bank_user_data = cyclos.post(method='user/search', data=bank_user_query)['result']['pageItems'][0]
    except (KeyError, IndexError):
                return Response({'error': 'Unable to get bank data for the provided bank_name!'},
                                status=status.HTTP_400_BAD_REQUEST)

    # Cotisations
    if request.data['montant_total_cotisations']:
        cotisation_query = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_banque_de_depot_vers_compte_debit_euro']),  # noqa
            'amount': request.data['montant_total_cotisations'],  # montant du virement "Cotisations"
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': bank_user_data['id'],  # ID de l'utilisateur Banque de dépôt
            'to': 'SYSTEM',
            'description': '{} - Cotisations'.format(bank_user_data['display'])  # nom de la banque de dépôt
        }
        cyclos.post(method='payment/perform', data=cotisation_query)

    # Ventes
    if request.data['montant_total_ventes']:
        ventes_query = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_banque_de_depot_vers_compte_debit_euro']),  # noqa
            'amount': request.data['montant_total_ventes'],  # montant du virement "Ventes"
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': bank_user_data['id'],  # ID de l'utilisateur Banque de dépôt
            'to': 'SYSTEM',
            'description': '{} - Ventes'.format(bank_user_data['display'])  # nom de la banque de dépôt
        }
        cyclos.post(method='payment/perform', data=ventes_query)

    # Change eusko billet
    if request.data['montant_total_billet']:
        change_eusko_billet_query = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_banque_de_depot_vers_compte_dedie']),
            'amount': request.data['montant_total_billet'],  # montant du virement "Changes eusko billets"
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': bank_user_data['id'],  # ID de l'utilisateur Banque de dépôt
            'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']),
            'description': '{} - Changes Eusko billet'.format(bank_user_data['display'])  # nom de la banque de dépôt
        }
        cyclos.post(method='payment/perform', data=change_eusko_billet_query)

    # Change eusko numérique
    if request.data['montant_total_numerique']:
        change_eusko_numerique_query = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_banque_de_depot_vers_compte_dedie']),
            'amount': request.data['montant_total_numerique'],  # montant du virement "Changes eusko numérique"
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': bank_user_data['id'],  # ID de l'utilisateur Banque de dépôt
            'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']),
            'description': '{} - Changes Eusko numérique'.format(bank_user_data['display'])  # noqa: nom de la banque de dépôt
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
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    res = []

    depots_query = {
        'account': str(settings.CYCLOS_CONSTANTS['system_accounts']['compte_des_billets_en_circulation']),
        'orderBy': 'DATE_DESC',
        'direction': 'DEBIT',
        'toNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
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
        'account': str(settings.CYCLOS_CONSTANTS['system_accounts']['compte_des_billets_en_circulation']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'fromNature': 'USER',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
    }
    retraits_data = cyclos.post(method='account/searchAccountHistory', data=retraits_query)

    # Il faut filtrer et ne garder que les opérations de type retrait_de_billets
    retraits_filtered_data = [
        item
        for item in retraits_data['result']['pageItems']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['retrait_de_billets'])
    ]
    res.extend(retraits_filtered_data)

    return Response(res) if res else Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def validate_depots_retraits(request):
    """
    validate_depots_retraits
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ValidateDepotsRetraitsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # 1) Enregistrer le virement :
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
    elif request.data['montant_total_depots'] < request.data['montant_total_retraits']:
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
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    res = []

    # Reconversions d'eusko billets
    query_billets = {
        'account': str(settings.CYCLOS_CONSTANTS['system_accounts']['compte_des_billets_en_circulation']),
        'orderBy': 'DATE_DESC',
        'direction': 'DEBIT',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
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
        'account': str(settings.CYCLOS_CONSTANTS['system_accounts']['compte_de_debit_eusko_numerique']),
        'orderBy': 'DATE_DESC',
        'direction': 'CREDIT',
        'statuses': [
            str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_a_faire']),
        ],
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
    }
    query_numeriques_data = cyclos.post(method='account/searchAccountHistory', data=query_numeriques)

    # Il faut filtrer et ne garder que les paiements de type reconversion_numerique
    filtered_numeriques_data = [
        item
        for item in query_numeriques_data['result']['pageItems']
        if item['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['reconversion_numerique'])
    ]
    res.extend(filtered_numeriques_data)

    return Response(res) if res else Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def validate_reconversions(request):
    """
    validate_reconversions
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ValidateReconversionsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # Verify whether or not dedicated accounts have enough money
    query_data_billet = [str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']), None]
    accounts_summaries_billet = cyclos.post(method='account/getAccountsSummary', data=query_data_billet)
    try:
        if (float(accounts_summaries_billet['result'][0]['status']['balance']) <
           float(request.data['montant_total_billets'])):
            return Response({'error': "error-system-not-enough-money-billet"})
    except (KeyError, IndexError):
        return Response({'error': "Unable to fetch compte_dedie_eusko_billet account data!"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    query_data_numerique = [str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']), None]
    accounts_summaries_numerique = cyclos.post(method='account/getAccountsSummary', data=query_data_numerique)

    try:
        if (float(accounts_summaries_numerique['result'][0]['status']['balance']) <
           float(request.data['montant_total_numerique'])):
            return Response({'error': "error-system-not-enough-money-numerique"})
    except (KeyError, IndexError):
        return Response({'error': "Unable to fetch compte_dedie_eusko_numerique account data!"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if float(request.data['montant_total_billets']) > float(0):
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

        # 2) Passer chaque opération (reconversion d'eusko billet) sélectionnée à l'état "Virements faits" :
        for payment in request.data['selected_payments']:
            if (payment['type']['id'] ==
               str(settings.CYCLOS_CONSTANTS['payment_types']['reconversion_billets_versement_des_eusko'])):

                # Passer l'opération à l'état "Virements faits"
                status_query_data = {
                    'transfer': payment['id'],  # ID de l'opération d'origine (récupéré dans l'historique)
                    'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_faits'])
                }
                cyclos.post(method='transferStatus/changeStatus', data=status_query_data)

    if float(request.data['montant_total_numerique']) > float(0):
        # 3) Enregistrer le virement pour les eusko numériques
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

        # 4) Passer chaque opération (reconversion d'eusko numérique) sélectionnée à l'état "Virements faits" :
        for payment in request.data['selected_payments']:
            if payment['type']['id'] == str(settings.CYCLOS_CONSTANTS['payment_types']['reconversion_numerique']):

                # Passer l'opération à l'état "Virements faits"
                status_query_data = {
                    'transfer': payment['id'],  # ID de l'opération d'origine (récupéré dans l'historique)
                    'newStatus': str(settings.CYCLOS_CONSTANTS['transfer_statuses']['virements_faits'])
                }
                cyclos.post(method='transferStatus/changeStatus', data=status_query_data)

    return Response(request.data['selected_payments'])


@api_view(['GET'])
def calculate_3_percent(request):
    """
    calculate_3_percent
    """
    # On valide et on récupère les paramètres de la requête.
    log.debug("calculate_3_percent")
    serializer = serializers.Calculate3PercentSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    begin_date = serializer.data['begin']
    end_date = serializer.data['end']
    log.debug("begin_date = %s", begin_date)
    log.debug("end_date = %s", end_date)

    # Pour les recherches dans les historiques de compte de Cyclos, on
    # prend le lendemain de la date de fin demandée car Cyclos utilise
    # des DateTime et si l'heure n'est pas précisée, c'est minuit (heure
    # zéro, début de la journée).
    # Donc si on a end_date = 2017-06-30 par exemple, Cyclos fera la
    # recherche jusqu'à 2017-06-30T00:00 et les paiements du 30 juin
    # seront exclus. Pour avoir les paiements du 30 juin, il faut faire
    # la recherche jusqu'au 1er juillet à minuit.
    # D'autre part on convertit les dates en chaines de caractères pour
    # pouvoir les intégrer dans les données JSON de de la recherche.
    search_begin_date = begin_date.isoformat()
    search_end_date = (end_date + timedelta(days=1)).isoformat()
    log.debug("search_begin_date = %s", search_begin_date)
    log.debug("search_end_date = %s", search_end_date)

    # Connexion à Dolibarr et Cyclos.
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # On récupère la liste de tous les changes d'€ en eusko pour la
    # période demandée et on détermine à chaque fois qui est l'adhérent
    # qui a fait le change.
    # Il y a 3 types d'opérations à prendre en compte :
    # 1) change billets
    # 2) change numérique en BDC
    # 3) change numérique en ligne
    # Pour 1) et 2) on considère le paiement correspondant au versement
    # des € : le compte d'origine est le Compte de débit €, le numéro
    # d'adhérent est dans un champ personnalisé du paiement.
    # Pour 3) on considère le versement des eusko : le compte d'origine
    # est le Compte de débit eusko numérique, le compte destinataire est
    # le compte de l'adhérent.
    changes = []
    # 1) et 2) On récupère tous les débits du Compte de débit € pour la
    # période puis on filtre le résultat pour ne garder que les 2 types
    # de paiements "change billets" et "change numérique en BDC".
    payments = _search_account_history(
        cyclos=cyclos,
        account=settings.CYCLOS_CONSTANTS['system_accounts']['compte_de_debit_euro'],
        direction='DEBIT',
        begin_date=search_begin_date,
        end_date=search_end_date,
        payment_types=[
            str(settings.CYCLOS_CONSTANTS['payment_types']['change_billets_versement_des_euro']),
            str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_bdc_versement_des_euro']),
        ]
    )
    changes.extend([
        {'amount' : abs(float(payment['amount'])),
         'member_id' : value['linkedEntityValue']['internalName'],}
        for payment in payments
        for value in payment['customValues']
        if value['field']['internalName'] == 'adherent'
    ])
    # 3) On récupère tous les débits du Compte de débit eusko numérique
    # pour la période puis on filtre le résultat pour ne garder que les
    # paiements de type "change numérique en ligne".
    payments = _search_account_history(
        cyclos=cyclos,
        account=settings.CYCLOS_CONSTANTS['system_accounts']['compte_de_debit_eusko_numerique'],
        direction='DEBIT',
        begin_date=search_begin_date,
        end_date=search_end_date,
        payment_types=[
            str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_ligne_versement_des_eusko']),
        ]
    )
    changes.extend([
        {'amount' : abs(float(payment['amount'])),
         'member_id' : payment['relatedAccount']['owner']['shortDisplay'],}
        for payment in payments
    ])

    # On récupère la liste de toutes les associations
    # et on construit un dictionnaire qui va donner la correspondance :
    #     id de l'asso dans Dolibarr -> numéro d'adhérent
    results = dolibarr.get(model='associations')
    dolibarr_id_2_member_id = {item['id'] : item['code_client']
                              for item in results}
    log.debug("dolibarr_id_2_member_id = %s", dolibarr_id_2_member_id)
    # On récupère aussi la liste des associations bénéficiaires des 3%,
    # avec le nombre de parrainages de chaque asso.
    assos_3_pourcent = {item['code_client'] : {
                           'nom': item['nom'],
                           'nb_parrainages': int(item['nb_parrains']),
                       }
                       for item in results
                       if int(item['nb_parrains']) >= settings.MINIMUM_PARRAINAGES_3_POURCENTS}
    log.debug("assos_3_pourcent = %s", assos_3_pourcent)

    # On crée 3 dictionnaires qui vont servir pour la suite du calcul:
    # 1) un pour mémoriser quelle asso bénéficie des dons de chaque adhérent-e;
    #     numéro d'adhérent de l'adhérent-e -> numéro d'adhérent de l'asso
    assos_beneficiaires = {}
    # 2) un pour additionner les dons pour chaque asso
    #     numéro d'adhérent de l'asso -> montant du don
    dons = {id_asso : 0.0 for id_asso in assos_3_pourcent.keys()}
    # 3) un pour compter le nombre de parrainages supplémentaires de
    # chaque asso, c'est-à-dire le nombre de parrainages en 2è choix
    # qui bénéficient à chaque asso.
    #     numéro d'adhérent de l'asso -> nb de parrainages
    nb_parrainages_asso2 = {id_asso : 0 for id_asso in assos_3_pourcent.keys()}

    montant_total_changes = 0.0
    montant_total_dons = 0.0

    # Pour chaque change, on regarde qui est l'adhérent qui a fait le change,
    # on récupère l'association bénéficiaire des dons de cet adhérent
    # et on ajoute à cette asso 3% du montant du change.
    for change in changes:
        member_id = change['member_id']
        try:
            asso_beneficiaire = assos_beneficiaires[member_id]
        except KeyError:
            # On doit déterminer quelle association va recevoir les dons de cet adhérent.
            # Pour cela on récupère l'adhérent dans Dolibarr et on regarde quelle
            # association il parraine en 1er choix.
            # Si c'est une asso 3%, c'est elle qui reçoit les dons.
            try:
                member_data = dolibarr.get(model='members', login=member_id)[0]
            except DolibarrAPIException:
                # Si on ne parvient pas à récupérer l'adhérent-e dans Dolibarr,
                # on ignore l'erreur et on considère simplement qu'on n'a
                # aucune information sur cet adhérent-e. Du coup c'est
                # Euskal Moneta qui recevra ses dons.
                # C'est le cas par exemple avec l'adhérent 'E00000' qui
                # n'existe que dans Cyclos. Cela pourrait arriver aussi
                # pour un adhérent supprimé de Dolibarr du fait d'un doublon.
                member_data = []
            fk_asso = member_data['fk_asso']
            try:
                asso1 = dolibarr_id_2_member_id[fk_asso]
            except KeyError:
                asso1 = None
            log.debug("asso1 = %s", asso1)
            if asso1 and asso1 in assos_3_pourcent.keys():
                asso_beneficiaire = asso1
            else:
                # Si l'association parrainée en 1er choix n'est pas une asso 3%
                # (ou s'il n'y a pas d'asso parrainée en 1er choix),
                # on regarde celle parrainée en 2è choix.
                fk_asso2 = member_data['fk_asso2']
                try:
                    asso2 = dolibarr_id_2_member_id[fk_asso2]
                except KeyError:
                    asso2 = None
                log.debug("asso2 = %s", asso2)
                if asso2 and asso2 in assos_3_pourcent.keys():
                    asso_beneficiaire = asso2
                    nb_parrainages_asso2[asso2] += 1
                else:
                    # Si ni l'asso 1 ni l'asso 2 ne sont des assos 3%,
                    # c'est Euskal Moneta qui reçoit les dons de cet adhérent.
                    asso_beneficiaire = 'Z00001'
            # On enregistre ce résultat pour ne pas avoir à le
            # recalculer pour chaque change de cet adhérent.
            assos_beneficiaires[member_id] = asso_beneficiaire
        don = change['amount'] * 0.03
        dons[asso_beneficiaire] += don
        montant_total_changes += change['amount']
        montant_total_dons += don

    log.debug("dons = %s", dons)
    log.debug("nb_parrainages_asso2 = %s", nb_parrainages_asso2)

    # On construit l'objet qui sera envoyé dans la réponse.
    # Pour le nombre de parrainages de chaque association, on compte :
    # - les parrainages en 1er choix, que les adhérent-e-s aient fait du
    #   change ou pas
    # - plus les parrainages en 2è choix lorsque ceux-ci s'appliquent
    #   (ils s'agit donc d'adhérent-e-s qui ont fait du change).
    # Cette manière de calculer est plus proche de ce qui était fait
    # avant la migration de Cyclos 3 à Cyclos 4 et avant l'introduction
    # du 2è choix pour le parrainage.
    response_data = {
        'debut': begin_date,
        'fin': end_date,
        'dons': [{
                'association': {
                    'num_adherent': id_asso1,
                    'nom': asso['nom'],
                },
                'montant_don': montant_don,
                'nb_parrainages': asso['nb_parrainages'] + nb_asso2,
            }
            for id_asso1, asso in assos_3_pourcent.items()
            for id_asso2, montant_don in dons.items() if id_asso1 == id_asso2
            for id_asso3, nb_asso2 in nb_parrainages_asso2.items() if id_asso1 == id_asso3
        ],
        'montant_total_changes': montant_total_changes,
        'montant_total_dons': montant_total_dons,
    }
    log.debug("response_data = %s", response_data)
    return Response(response_data)


def _search_account_history(cyclos, account, direction, begin_date, end_date, payment_types=[]):
    """
    Search an account history for payments of the given types, ignoring
    the chargedbacked (canceled) ones.
    """
    current_page = 0
    account_history = []
    while True:
        search_history_data = {
            'account': account,
            'direction': direction,
            'period':
            {
                'begin': begin_date,
                'end': end_date,
            },
            'orderBy': 'DATE_ASC',
            'pageSize': 1000,  # maximum pageSize: 1000
            'currentPage': current_page,
        }
        search_history_res = cyclos.post(method='account/searchAccountHistory', data=search_history_data)
        account_history.extend(search_history_res['result']['pageItems'])
        page_count = search_history_res['result']['pageCount']
        if page_count == 0 or current_page + 1 == page_count:
            break
        else:
           current_page += 1
    filtered_history = []
    for entry in account_history:
        # On filtre d'abord par type de paiement et ensuite on regarde
        # si le paiement a fait l'objet d'une opposition de paiement
        # (dans cet ordre car pour voir s'il y a une oppostion de
        # paiement, il faut faire une requête au serveur).
        # On récupère les données de la transaction et on vérifie si la
        # donnée 'chargedBackBy' est présente dans le transfert associé.
        #
        # Note : Les transactions importées lors de la migration de
        # Cyclos 3 à Cyclos 4 sont de type ImportedTransactionData et
        # n'ont pas de transfert associé. Elles ne peuvent pas être
        # annulées. Les transactions enregistrées depuis (les
        # transactions "normales" en quelque sorte), sont de type
        # PaymentData.
        if entry['type']['id'] in payment_types:
            get_data_res = cyclos.get(method='transaction/getData/{}'.format(entry['transactionId']))
            transaction_data = get_data_res['result']
            if (transaction_data['class'] ==
                    'org.cyclos.model.banking.transactions.ImportedTransactionData'
                    or (transaction_data['class'] ==
                    'org.cyclos.model.banking.transactions.PaymentData'
                    and'chargedBackBy' not in transaction_data['transfer'].keys())):
                filtered_history.append(entry)
    return filtered_history
