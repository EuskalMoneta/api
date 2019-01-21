import csv
from datetime import datetime
import io
import logging

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q
from django.forms.models import model_to_dict
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response

from cyclos_api import CyclosAPI, CyclosAPIException
from gestioninterne import models, serializers

log = logging.getLogger()


@api_view(['POST'])
@parser_classes((FileUploadParser,))
def import_csv(request, filename):
    """
    import_csv

    models.Echeance fields:
        - ref
        - adherent_name
        - adherent_id
        - montant
        - date
        - operation_date
        - cyclos_payment_id
        - cyclos_error
    """

    # DictReader needs a file-like object, I need to use StringIO to create one from the uploaded file
    f = io.StringIO(request.data['file'].read().decode('utf-8'))

    csv.register_dialect('collect.online', delimiter=';')
    reader = csv.DictReader(f, dialect='collect.online')

    # I don't like 'Sentences with Spaces And Random Caps' as key in my dicts, I slugify every key here
    reader.fieldnames = [slugify(name) for name in reader.fieldnames]

    # I need to filter out csv lines by 'statut-echeance' field, and I prefer to strip every value in my data
    csv_data = [{k: row[k].strip()
                 for k in row}
                for row in reader
                if row['statut-echeance'] == 'Exécutée']

    res = {'errors': [], 'ignore': 0, 'ok': []}

    for row in csv_data:
        try:
            echeance = models.Echeance(
                ref=row['reference-de-bout-en-bout'],
                adherent_name='{} {}'.format(row['prenom-ou-siren'], row['nom-ou-raisons-sociale']).strip(),
                adherent_id=row['reference-debiteur'],
                montant=float(row['montant-en']),
                date=datetime.strptime(row['date-decheance'], '%d/%m/%y'),
                operation_date=datetime.strptime(row['date-doperation'], '%d/%m/%y'))

            echeance.save()

            echeance_dict = model_to_dict(echeance)
            res['ok'].append(echeance_dict)

        except IntegrityError:
            res['ignore'] += 1
        except Exception as e:
            try:
                echeance_dict = model_to_dict(echeance)
                echeance_dict.update({'error': e})
                res['errors'].append(echeance_dict)
            except Exception as err_two:
                echeance_dict = {
                    'ref': row['reference-de-bout-en-bout'],
                    'adherent_name': '{} {}'.format(row['prenom-ou-siren'], row['nom-ou-raisons-sociale']).strip(),
                    'adherent_id': row['reference-debiteur'],
                    'montant': row['montant-en'],
                    'date': row['date-decheance'],
                    'operation_date': row['date-doperation'],
                    'error': '{} {}'.format(e, err_two),
                }
                res['errors'].append(echeance_dict)

    return Response(res)


@api_view(['POST'])
def perform(request):
    """
    perform
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.GenericHistoryValidationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    for payment in serializer.data['selected_payments']:
        try:
            adherent_cyclos_id = cyclos.get_member_id_from_login(member_login=payment['adherent_id'])

            # Determine whether or not our user is part of the appropriate group
            group_constants_with_account = [str(settings.CYCLOS_CONSTANTS['groups']['adherents_prestataires']),
                                            str(settings.CYCLOS_CONSTANTS['groups']['adherents_utilisateurs'])]

            # Fetching info for our current user (we look for his groups)
            user_data = cyclos.post(method='user/load', data=[adherent_cyclos_id])

            if not user_data['result']['group']['id'] in group_constants_with_account:
                error = "{} n'a pas de compte Eusko numérique...".format(payment['adherent_id'])
                log.critical(error)
                echeance = models.Echeance.objects.get(ref=payment['ref'])
                echeance.cyclos_error = error
                echeance.save()
                continue

            # Payment in Euro
            change_numerique_euro = {
                'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_ligne_versement_des_euro']),  # noqa
                'amount': float(payment['montant']),
                'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
                'from': 'SYSTEM',
                'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_mlc_numerique']),
                'customValues': [{
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['numero_de_transaction_banque']),  # noqa
                    'stringValue': payment['ref']  # référence de l'échéance
                }],
                'description': 'Change par prélèvement automatique'
            }
            cyclos.post(method='payment/perform', data=change_numerique_euro)

            # Payment in Eusko
            change_prelevement_auto = {
                'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_ligne_versement_des_mlc']),  # noqa
                'amount': float(payment['montant']),
                'currency': str(settings.CYCLOS_CONSTANTS['currencies']['mlc']),
                'from': 'SYSTEM',
                'to': adherent_cyclos_id,
                'customValues': [{
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['numero_de_transaction_banque']),  # noqa
                    'stringValue': payment['ref']  # référence de l'échéance
                }],
                'description': 'Change par prélèvement automatique'
            }
            change_prelevement_auto_id = cyclos.post(method='payment/perform', data=change_prelevement_auto)

            echeance = models.Echeance.objects.get(ref=payment['ref'])
            echeance.cyclos_payment_id = change_prelevement_auto_id['result']['id']
            echeance.cyclos_error = ''
            echeance.save()
        except Exception as e:
            echeance = models.Echeance.objects.get(ref=payment['ref'])
            echeance.cyclos_error = str(e)
            echeance.save()

    return Response(serializer.data['selected_payments'])


@api_view(['POST'])
def delete(request):
    """
    Delete one or more Echeance object(s).
    """
    serializer = serializers.GenericHistoryValidationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    for payment in serializer.data['selected_payments']:
        models.Echeance.objects.get(ref=payment['ref']).delete()

    return Response(serializer.data['selected_payments'])


@api_view(['GET'])
def list(request, mode):
    """
    List pending Echeances objects and Echeances objects in 'error' state.
    We know that a entry in our table is an error WHERE cyclos_error IS NOT NULL AND cyclos_error != "".

    See how I found this way to chain excludes via Django ORM: http://stackoverflow.com/a/844572
    """
    if mode == 'errors':
        return Response([model_to_dict(obj)
                         for obj in
                         models.Echeance.objects.exclude(cyclos_error__isnull=True).exclude(cyclos_error__exact='')])
    else:
        return Response([model_to_dict(obj)
                         for obj in
                         models.Echeance.objects.filter(
                         Q(cyclos_error__isnull=True) | Q(cyclos_error__exact=''),
                         Q(cyclos_payment_id__isnull=True) | Q(cyclos_payment_id__exact=''))
                         ])
