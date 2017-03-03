import csv
from datetime import datetime
import io
import logging

from django.conf import settings
from django.db import IntegrityError
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
    # I also need to decode data from iso-8859-15 to utf-8
    f = io.StringIO(request.data['file'].read().decode('iso-8859-15'))

    csv.register_dialect('credit-coop', delimiter=';')
    reader = csv.DictReader(f, dialect='credit-coop')

    # I don't like 'Sentences with Spaces And Random Caps' as key in my dicts, I slugify every key here
    reader.fieldnames = [slugify(name) for name in reader.fieldnames]

    # I need to filter out csv lines with 'statut-echeance' field, and I prefer to strip every value in my data
    csv_data = [{k: row[k].strip()
                 for k in row}
                for row in reader
                if row['statut-echeance'] == 'exécutée avec succès']

    res = {'errors': [], 'ignore': 0, 'ok': []}

    for row in csv_data:
        try:
            echeance = models.Echeance(
                ref=row['reference-echeance'],
                adherent_name='{} {}'.format(row['prenom-ou-siren'], row['nom-ou-raison-sociale']).strip(),
                adherent_id=row['numero-du-debiteur'],
                montant=float(row['montant-de-lecheance-en-euro'].replace(',', '.')),
                date=datetime.strptime(row['date-decheance'], '%d/%m/%Y'),
                operation_date=datetime.strptime(row['date-doperation'], '%d/%m/%Y'))

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
                    'ref': row['reference-echeance'],
                    'adherent_name': '{} {}'.format(row['prenom-ou-siren'], row['nom-ou-raison-sociale']).strip(),
                    'adherent_id': row['numero-du-debiteur'],
                    'montant': row['montant-de-lecheance-en-euro'].replace(',', '.'),
                    'date': row['date-decheance'],
                    'operation_date': row['date-doperation'],
                    'error': '{} {}'.format(e, err_two),
                }
                res['errors'].append(echeance_dict)

    return Response(res)


@api_view(['POST'])
def credit(request):
    """
    credit
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token)
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.GenericHistoryValidationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    for payment in serializer.data['selected_payments']:
        # try:
            change_numerique_euro = {
                'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_ligne_versement_des_euro']),  # noqa
                'amount': payment['montant'],
                'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
                'from': 'SYSTEM',
                'to': str(settings.CYCLOS_CONSTANTS['users']['compte_dedie_eusko_numerique']),
                'customValues': [{
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['numero_de_transaction_banque']),  # noqa
                    'stringValue': payment['ref']  # référence de l'échéance
                }],
                'description': 'Change par prélèvement automatique'
            }
            cyclos.post(method='payment/perform', data=change_numerique_euro)

            change_prelevement_auto = {
                'type': str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_ligne_versement_des_eusko']),  # noqa
                'amount': payment['montant'],
                'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
                'from': 'SYSTEM',
                'to': cyclos.user_id,
                'customValues': [{
                    'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['numero_de_transaction_banque']),  # noqa
                    'stringValue': payment['ref']  # référence de l'échéance
                }],
                'description': 'Change par prélèvement automatique'
            }
            change_prelevement_auto_id = cyclos.post(method='payment/perform', data=change_prelevement_auto)
            return Response(change_prelevement_auto_id)

            echeance = models.Echeance.objects.get(ref=change_prelevement_auto_id)
            echeance.cyclos_payment_id = change_prelevement_auto_id
            echeance.cyclos_error = ''
            echeance.save()

        # except Exception as e:
        #     echeance = models.Echeance.objects.get(ref=payment['ref'])
        #     echeance.cyclos_error = str(e)
        #     echeance.save()

    return Response(serializer.data['selected_payments'])


@api_view(['GET'])
def errors(request):
    """
    List errors stored in our Echeance table.
    We know that a entry in our table is an error WHERE cyclos_error IS NOT NULL AND cyclos_error != "".

    See how I found this way to filter / exclude via Django ORM: http://stackoverflow.com/a/844572
    """
    # return Response([model_to_dict(obj)
    #                  for obj in
    #                  models.Echeance.objects.all()])
    return Response([model_to_dict(obj)
                     for obj in
                     models.Echeance.objects.exclude(cyclos_error__isnull=True).exclude(cyclos_error__exact='')])
