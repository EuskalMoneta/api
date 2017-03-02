import csv
from datetime import datetime
import io
import json
import logging

# from django.conf import settings
from django.db import IntegrityError
from django.forms.models import model_to_dict
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response

# from cyclos_api import CyclosAPI, CyclosAPIException
from gestioninterne import models  # , serializers

log = logging.getLogger()


def datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")


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

    res = {'errors': [], 'ignore': 0, 'ok': 0}

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
            res['ok'] += 1

        except IntegrityError:
            res['ignore'] += 1
        except Exception as e:
            try:
                res['errors'].append({'item': json.dumps(model_to_dict(echeance), default=datetime_handler),
                                      'error': e})
            except Exception as e:
                res['errors'].append({'item': json.dumps(row), 'error': e})

    return Response(res)
