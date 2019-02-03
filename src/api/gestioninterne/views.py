from datetime import datetime, timedelta
import logging

import arrow
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.response import Response
from rest_framework_csv.renderers import CSVRenderer

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
        return Response({'error': 'The mode you provided is not supported by this endpoint!'},
                        status=status.HTTP_400_BAD_REQUEST)

    bank_history_data = cyclos.post(method='account/searchAccountHistory', data=bank_history_query)
    if bank_history_data['result']['totalCount'] == 0:
        return Response(status=status.HTTP_204_NO_CONTENT)

    data = bank_history_data['result']['pageItems']

    # Dans le cas des virements, on ne garde que les paiements rapprochés.
    if request.query_params['mode'] == 'virement':
        data = [
            item
            for item in data
            for status in item['statuses']
            if status['id'] == str(settings.CYCLOS_CONSTANTS['transfer_statuses']['rapproche'])
        ]

    return Response(data)


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
    # pouvoir les intégrer dans les données JSON de la recherche.
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
                member_data = dolibarr.get(model='members', sqlfilters="login='{}'".format(member_id))[0]
            except DolibarrAPIException:
                # Si on ne parvient pas à récupérer l'adhérent-e dans Dolibarr,
                # on ignore l'erreur et on considère simplement qu'on n'a
                # aucune information sur cet adhérent-e. Du coup c'est
                # Euskal Moneta qui recevra ses dons.
                # C'est le cas par exemple avec l'adhérent 'E00000' qui
                # n'existe que dans Cyclos. Cela pourrait arriver aussi
                # pour un adhérent supprimé de Dolibarr du fait d'un doublon.
                member_data = {}
            try:
                fk_asso = member_data['fk_asso']
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
                try:
                    fk_asso2 = member_data['fk_asso2']
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
                'montant_don': round(montant_don, 2),
                'nb_parrainages': asso['nb_parrainages'] + nb_asso2,
            }
            for id_asso1, asso in assos_3_pourcent.items()
            for id_asso2, montant_don in dons.items() if id_asso1 == id_asso2
            for id_asso3, nb_asso2 in nb_parrainages_asso2.items() if id_asso1 == id_asso3
        ],
        'montant_total_changes': montant_total_changes,
        'montant_total_dons': round(montant_total_dons, 2),
    }
    log.debug("response_data = %s", response_data)
    return Response(response_data)


class ExportVersOdooCSVRenderer(CSVRenderer):
    header = ['journal_id', 'date', 'ref', 'line_ids/account_id', 'line_ids/name', 'line_ids/debit', 'line_ids/credit']


@api_view(['GET'])
@renderer_classes((ExportVersOdooCSVRenderer,))
def export_vers_odoo(request):
    """
    Fait un export pour la comptabilité, pour une période donnée, des
    opérations enregistrées dans Cyclos.

    Cette fonction génère un fichier CSV qui peut être importé comme
    pièces comptables dans le module comptabilité de Odoo. Le ficher
    généré contient une pièce pour chaque opération enregistrée dans
    Cyclos pour la période demandée et qui doit être enregistrée en
    comptabilité. La transposition des opérations Cyclos en écritures
    dans la comptabilité est détaillée dans le document "Comptabilité
    des eusko".
    """

    # Pseudo-constantes pour les noms des journaux et les comptes dans Odoo.
    JOURNAL_OPERATIONS_DIVERSES = 'Opérations diverses'
    COMPTE_EUSKO_BILLETS_EN_CIRCULATION = '463300'
    COMPTE_FACTURATION_EUSKO_BILLETS = '463309'
    COMPTE_EUSKO_NUMERIQUES_EN_CIRCULATION = '463400'
    COMPTE_FACTURATION_EUSKO_NUMERIQUES = '463409'
    COMPTE_FACTURATION_COTISATIONS = '463500'
    COMPTE_COTISATIONS_PARTICULIERS = '756100'

    # On valide et on récupère les paramètres de la requête.
    serializer = serializers.ExportVersOdooSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    begin_date = serializer.data['begin']
    end_date = serializer.data['end']

    # Voir le commentaire du même code ci-dessus dans calculate_3_percent.
    search_begin_date = begin_date.isoformat()
    search_end_date = (end_date + timedelta(days=1)).isoformat()

    # Connexion à Dolibarr et Cyclos.
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # On traite successivement tous les types d'opérations de Cyclos qui
    # doivent être enregistrées en comptabilité. Pour chaque opération,
    # une pièce comptable au format CSV va être créée. Chaque pièce
    # comptable est enregistrée dans un journal avec une date et une
    # référence, et contient plusieurs lignes (au moins deux) de débit
    # et de crédit. Chaque pièce comptable doit être équilibrée.
    # Toutes les pièces comptables générées pour la période demandée
    # sont enregistrées dans un seul et même fichier CSV, qui sera
    # importé en une fois dans Odoo.
    # Pour éviter de devoir faires des conversions pour avoir la valeur
    # absolue du montant, on fait la recherche des paiements à partir du
    # compte qui est crédité, sauf si la recherche est plus simple à
    # partir du compte débité (ce qui est le cas par exemple pour les
    # cotisations en eusko car c'est toujours le même compte qui est
    # débité alors qu'en faisant la recherche des crédits, il faudrait
    # passer en revue tous les bureaux de change).
    csv_content = []

    # Gains de billets d'eusko.
    payments = _search_account_history(
        cyclos=cyclos,
        account=settings.CYCLOS_CONSTANTS['system_accounts']['compte_des_billets_en_circulation'],
        direction='DEBIT',
        begin_date=search_begin_date,
        end_date=search_end_date,
        payment_types=[
            str(settings.CYCLOS_CONSTANTS['payment_types']['gain_de_billets']),
        ]
    )
    for payment in payments:
        amount = abs(float(payment['amount']))
        _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                           payment['date'], payment['description'],
                           [{ 'account_id': COMPTE_EUSKO_BILLETS_EN_CIRCULATION, 'debit': amount },
                            { 'account_id': COMPTE_FACTURATION_EUSKO_BILLETS, 'credit': amount }])

    # Pertes de billets d'eusko.
    payments = _search_account_history(
        cyclos=cyclos,
        account=settings.CYCLOS_CONSTANTS['system_accounts']['compte_des_billets_en_circulation'],
        direction='CREDIT',
        begin_date=search_begin_date,
        end_date=search_end_date,
        payment_types=[
            str(settings.CYCLOS_CONSTANTS['payment_types']['perte_de_billets']),
        ]
    )
    for payment in payments:
        _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                           payment['date'], payment['description'],
                           [{ 'account_id': COMPTE_FACTURATION_EUSKO_BILLETS, 'debit': payment['amount'] },
                            { 'account_id': COMPTE_EUSKO_BILLETS_EN_CIRCULATION, 'credit': payment['amount'] }])

    # Opérations concernant les banques de dépôt.
    for banque in ('CAMPG', 'LBPO',) :
        # On commence par récupérer l'identifiant du compte de la banque.
        bank_user_data = cyclos.post(method='user/search', data={'keywords': banque})['result']['pageItems'][0]
        bank_account_query = [bank_user_data['id'], None]
        bank_account_data = cyclos.post(method='account/getAccountsSummary', data=bank_account_query)['result'][0]
        bank_account_id = bank_account_data['id']
        # On récupère tous les dépôts en banque et on en extraie les
        # montants des cotisations, changes billet et changes numérique.
        payments = _search_account_history(
            cyclos=cyclos,
            account=bank_account_id,
            direction='CREDIT',
            begin_date=search_begin_date,
            end_date=search_end_date,
            payment_types=[
                str(settings.CYCLOS_CONSTANTS['payment_types']['depot_en_banque']),
            ]
        )
        for payment in payments:
            montant_cotisations = float()
            montant_changes_billet = float()
            montant_changes_numerique = float()
            for value in payment['customValues']:
                if value['field']['internalName'] == 'montant_cotisations':
                    montant_cotisations = float(value['decimalValue'])
                elif value['field']['internalName'] == 'montant_changes_billet':
                    montant_changes_billet = float(value['decimalValue'])
                elif value['field']['internalName'] == 'montant_changes_numerique':
                    montant_changes_numerique = float(value['decimalValue'])
            # On génère une pièce comptable par "facture".
            if montant_cotisations > float():
                _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                                   payment['date'], payment['description'],
                                   [{ 'account_id': COMPTE_FACTURATION_COTISATIONS, 'debit': montant_cotisations },
                                    { 'account_id': COMPTE_COTISATIONS_PARTICULIERS, 'credit': montant_cotisations }])
            if montant_changes_billet > float():
                _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                                   payment['date'], payment['description'],
                                   [{ 'account_id': COMPTE_FACTURATION_EUSKO_BILLETS, 'debit': montant_changes_billet },
                                    { 'account_id': COMPTE_EUSKO_BILLETS_EN_CIRCULATION, 'credit': montant_changes_billet }])
            if montant_changes_numerique > float():
                _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                                   payment['date'], payment['description'],
                                   [{ 'account_id': COMPTE_FACTURATION_EUSKO_NUMERIQUES, 'debit': montant_changes_numerique },
                                    { 'account_id': COMPTE_EUSKO_NUMERIQUES_EN_CIRCULATION, 'credit': montant_changes_numerique }])

    # Reconversions d’eusko en €.
    # On se base sur les virements de remboursement faits depuis les
    # comptes dédiés.
    payments = _search_account_history(
        cyclos=cyclos,
        account=settings.CYCLOS_CONSTANTS['system_accounts']['compte_de_debit_euro'],
        direction='CREDIT',
        begin_date=search_begin_date,
        end_date=search_end_date,
        payment_types=[
            str(settings.CYCLOS_CONSTANTS['payment_types']['virement_de_compte_dedie_vers_compte_debit_euro']),
        ]
    )
    for payment in payments:
        amount = abs(float(payment['amount']))
        if payment['relatedAccount']['owner']['id'] == str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']):
            compte_eusko_en_circulation = COMPTE_EUSKO_BILLETS_EN_CIRCULATION
            compte_facturation = COMPTE_FACTURATION_EUSKO_BILLETS
        elif payment['relatedAccount']['owner']['id'] == str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']):
            compte_eusko_en_circulation = COMPTE_EUSKO_NUMERIQUES_EN_CIRCULATION
            compte_facturation = COMPTE_FACTURATION_EUSKO_NUMERIQUES
        _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                           payment['date'], payment['description'],
                           [{ 'account_id': compte_eusko_en_circulation, 'debit': amount },
                            { 'account_id': compte_facturation, 'credit': amount }])

    # Change d’eusko numérique par virement ou prélèvement.
    # Pour ne pas avoir tous les changes de manière individuelle, afin
    # de réduire le nombre d'écritures comptables, on regroupe les
    # paiements par date et selon leur description (de manière à
    # regrouper les changes par virement d'un côté et ceux par
    # prélèvement de l'autre).
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
    grouped_payments = {}
    for payment in payments:
        date = arrow.get(payment['date']).format('YYYY-MM-DD')
        description = payment['description']
        amount = abs(float(payment['amount']))
        key = date + '#' + description
        try:
            grouped_payments[key] += amount
        except KeyError:
            grouped_payments[key] = amount
    for key, amount in grouped_payments.items():
        date = key[:len('YYYY-MM-DD')]
        description = key[len('YYYY-MM-DD#'):]
        _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                           date, description,
                           [{ 'account_id': COMPTE_FACTURATION_EUSKO_NUMERIQUES, 'debit': amount },
                            { 'account_id': COMPTE_EUSKO_NUMERIQUES_EN_CIRCULATION, 'credit': amount }])

    # Dépôts et retraits.
    # On se base sur les virements de régularisation entre comptes dédiés.
    # 1) Si retraits > dépôts, virement du Compte dédié numérique vers le Compte dédié billet.
    account_query = [str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']), None]
    account_data = cyclos.post(method='account/getAccountsSummary', data=account_query)['result'][0]
    compte_dedie_eusko_numerique_id = account_data['id']
    payments = _search_account_history(
        cyclos=cyclos,
        account=compte_dedie_eusko_numerique_id,
        direction='DEBIT',
        begin_date=search_begin_date,
        end_date=search_end_date,
        payment_types=[
            str(settings.CYCLOS_CONSTANTS['payment_types']['virement_entre_comptes_dedies']),
        ]
    )
    for payment in payments:
        amount = abs(float(payment['amount']))
        _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                           payment['date'], payment['description'],
                           [{ 'account_id': COMPTE_EUSKO_NUMERIQUES_EN_CIRCULATION, 'debit': amount },
                            { 'account_id': COMPTE_FACTURATION_EUSKO_NUMERIQUES, 'credit': amount },
                            { 'account_id': COMPTE_FACTURATION_EUSKO_BILLETS, 'debit': amount },
                            { 'account_id': COMPTE_EUSKO_BILLETS_EN_CIRCULATION, 'credit': amount }])
    # 2) Si dépôts > retraits, virement du Compte dédié billet vers le Compte dédié numérique.
    account_query = [str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_billet']), None]
    account_data = cyclos.post(method='account/getAccountsSummary', data=account_query)['result'][0]
    compte_dedie_eusko_billet_id = account_data['id']
    payments = _search_account_history(
        cyclos=cyclos,
        account=compte_dedie_eusko_billet_id,
        direction='DEBIT',
        begin_date=search_begin_date,
        end_date=search_end_date,
        payment_types=[
            str(settings.CYCLOS_CONSTANTS['payment_types']['virement_entre_comptes_dedies']),
        ]
    )
    for payment in payments:
        amount = abs(float(payment['amount']))
        _add_account_entry(csv_content, JOURNAL_OPERATIONS_DIVERSES,
                           payment['date'], payment['description'],
                           [{ 'account_id': COMPTE_EUSKO_BILLETS_EN_CIRCULATION, 'debit': amount },
                            { 'account_id': COMPTE_FACTURATION_EUSKO_BILLETS, 'credit': amount },
                            { 'account_id': COMPTE_FACTURATION_EUSKO_NUMERIQUES, 'debit': amount },
                            { 'account_id': COMPTE_EUSKO_NUMERIQUES_EN_CIRCULATION, 'credit': amount }])

    return Response(csv_content)


def _search_account_history(cyclos, account, direction, begin_date, end_date, payment_types=[]):
    """
    Search an account history for payments of the given types, ignoring
    the chargedbacked (cancelled) ones.
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


def _add_account_entry(csv_content, journal_id, date, description, lines):
    """
    Add an account entry to the given list, in order to generate a CSV
    file that will be imported in Odoo.
    The account entry is created in the given journal and with the given
    lines. A line is a dictionary:
    { 'account_id': xxx, 'debit' or 'credit': xxx }
    """
    for counter, line in enumerate(lines):
        csv_content.extend([
                {'journal_id': journal_id if counter == 0 else '',
                'date': arrow.get(date).format('YYYY-MM-DD') if counter == 0 else '',
                'ref': description if counter == 0 else '',
                'line_ids/account_id': line['account_id'],
                'line_ids/name': description,
                'line_ids/debit': line['debit'] if 'debit' in line else '',
                'line_ids/credit': line['credit'] if 'credit' in line else ''}
        ])


@api_view(['POST'])
def change_par_virement(request):
    """
    Enregistrement d'un change d'eusko numériques par virement.
    """
    serializer = serializers.ChangeParVirementSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # Connexion à Dolibarr et Cyclos.
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # On récupère les données de l'adhérent.
    try:
        member = dolibarr.get(model='members', sqlfilters="login='{}'".format(serializer.data['member_login']))[0]
    except:
        return Response({'error': 'Unable to retrieve member in Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)

    # Le code ci-dessous est un gros copier-coller venant de la fonction
    # perform() de credits_comptes_prelevements_auto.py. Il faudrait
    # factoriser tout ça mais je n'ai pas le temps de tout tester
    # correctement maintenant donc je minimise les risques.
    try:
        adherent_cyclos_id = cyclos.get_member_id_from_login(member_login=member['login'])

        # Determine whether or not our user is part of the appropriate group
        group_constants_with_account = [str(settings.CYCLOS_CONSTANTS['groups']['adherents_prestataires']),
                                        str(settings.CYCLOS_CONSTANTS['groups']['adherents_utilisateurs'])]

        # Fetching info for our current user (we look for his groups)
        user_data = cyclos.post(method='user/load', data=[adherent_cyclos_id])

        if not user_data['result']['group']['id'] in group_constants_with_account:
            error = "{} n'a pas de compte Eusko numérique...".format(member['login'])
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        # Payment in Euro
        change_numerique_euro = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_ligne_versement_des_euro']),  # noqa
            'amount': float(serializer.data['amount']),
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
            'from': 'SYSTEM',
            'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']),
            'customValues': [{
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['numero_de_transaction_banque']),  # noqa
                'stringValue': serializer.data['bank_transfer_reference']
            }],
            'description': 'Change par virement'
        }
        res_change_numerique_euro = cyclos.post(method='payment/perform', data=change_numerique_euro)

        # Payment in Eusko
        change_numerique_eusko = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_ligne_versement_des_eusko']),  # noqa
            'amount': float(serializer.data['amount']),
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
            'from': 'SYSTEM',
            'to': adherent_cyclos_id,
            'customValues': [{
                'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['numero_de_transaction_banque']),  # noqa
                'stringValue': serializer.data['bank_transfer_reference']
            }],
            'description': 'Change par virement'
        }
        res_change_numerique_eusko = cyclos.post(method='payment/perform', data=change_numerique_eusko)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    res = {'res_change_numerique_euro': res_change_numerique_euro,
           'res_change_numerique_eusko': res_change_numerique_eusko}
    return Response(res)


@api_view(['POST'])
def paiement_cotisation_eusko_numerique(request):
    """
    Paiement de la cotisation d'un membre en Eusko numérique.

    Le paiement se fait par virement du compte Eusko du membre à celui
    d'Euskal Moneta, et la cotisation est enregistrée dans Dolibarr.
    """
    serializer = serializers.PaiementCotisationEuskoNumeriqueSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # On se connecte à Cyclos.
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # On se connecte à Dolibarr et on récupère les données de l'adhérent.
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        member = dolibarr.get(model='members', sqlfilters="login='{}'".format(serializer.data['member_login']))[0]
    except DolibarrAPIException as e:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except:
        return Response({'error': 'Unable to retrieve member in Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)

    if member['type'].lower() == 'particulier':
        member_name = '{} {}'.format(member['firstname'], member['lastname'])
    else:
        member_name = member['company']

    # On récupère l'id de l'adhérent dans Cyclos (on en a besoin pour le paiement).
    try:
        data = cyclos.post(method='user/search', data={'keywords': member['login']})
        member_cyclos_id = data['result']['pageItems'][0]['id']
    except (KeyError, IndexError, CyclosAPIException) as e:
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # On récupère l'id d'Euskal Moneta dans Cyclos (on en a besoin pour le paiement).
    try:
        data = cyclos.post(method='user/search', data={'keywords': 'Z00001'})
        euskal_moneta_cyclos_id = data['result']['pageItems'][0]['id']
    except (KeyError, IndexError, CyclosAPIException) as e:
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # On fait le paiement dans Cyclos.
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_inter_adherent']),
        'amount': serializer.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': member_cyclos_id,
        'to': euskal_moneta_cyclos_id,
        'description': 'Cotisation - {} - {}'.format(member['login'], member_name),
    }
    cyclos.post(method='payment/perform', data=query_data)

    # Dans Dolibarr :
    # 1) on enregistre la cotisation
    data_res_subscription = {'start_date': serializer.data['start_date'].strftime('%s'),
                             'end_date': serializer.data['end_date'].strftime('%s'),
                             'amount': serializer.data['amount'], 'label': serializer.data['label']}

    try:
        res_id_subscription = dolibarr.post(
            model='members/{}/subscriptions'.format(member['id']), data=data_res_subscription)
    except Exception as e:
        log.critical("data_res_subscription: {}".format(data_res_subscription))
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    if str(res_id_subscription) == '-1':
        return Response({'data returned': str(res_id_subscription)}, status=status.HTTP_409_CONFLICT)

    # 2) on enregistre le paiement
    payment_account = 4
    payment_type = 'VIR'
    data_res_payment = {'date': arrow.now('Europe/Paris').timestamp, 'type': payment_type,
                        'label': serializer.data['label'], 'amount': serializer.data['amount']}
    model_res_payment = 'bankaccounts/{}/lines'.format(payment_account)
    try:
        res_id_payment = dolibarr.post(
            model=model_res_payment, data=data_res_payment)

        log.info("res_id_payment: {}".format(res_id_payment))
    except DolibarrAPIException as e:
        log.critical("model: {}".format(model_res_payment))
        log.critical("data_res_payment: {}".format(data_res_payment))
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # 3) on lie la cotisation au paiement
    data_link_sub_payment = {'fk_bank': res_id_payment}
    model_link_sub_payment = 'subscriptions/{}'.format(res_id_subscription)
    try:
        res_id_link_sub_payment = dolibarr.put(
            model=model_link_sub_payment, data=data_link_sub_payment)

        log.info("res_id_link_sub_payment: {}".format(res_id_link_sub_payment))
    except DolibarrAPIException as e:
        log.critical("model: {}".format(model_link_sub_payment))
        log.critical("data_link_sub_payment: {}".format(data_link_sub_payment))
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # 4) on lie le paiement à l'adhérent
    data_link_payment_member = {'label': '{} {}'.format(member['firstname'], member['lastname']),
                                'type': 'member', 'url_id': member['id'],
                                'url': '{}/adherents/card.php?rowid={}'.format(
                                    settings.DOLIBARR_PUBLIC_URL, member['id'])}
    model_link_payment_member = 'bankaccounts/{}/lines/{}/links'.format(payment_account, res_id_payment)
    try:
        res_id_link_payment_member = dolibarr.post(
            model=model_link_payment_member, data=data_link_payment_member)

        log.info("res_id_link_payment_member: {}".format(res_id_link_payment_member))
    except DolibarrAPIException as e:
        log.critical("model: {}".format(model_link_payment_member))
        log.critical("data_link_payment_member: {}".format(data_link_payment_member))
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # On construit l'objet qui sera envoyé dans la réponse.
    res = {'id_subscription': res_id_subscription,
           'id_payment': res_id_payment,
           'link_sub_payment': res_id_link_sub_payment,
           'id_link_payment_member': res_id_link_payment_member,
           'member': member}

    return Response(res, status=status.HTTP_201_CREATED)
