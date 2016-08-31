import logging

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

from cyclos_api import CyclosAPI

log = logging.getLogger()


@api_view(['GET'])
def accounts_summaries(request):
    """
    List all accounts_summaries.
    """
    cyclos = CyclosAPI()
    # TODO steps:
    # getCurrentUser => get ID
    #  - user/load for this ID
    #   - get BDC ID
    #      - account/getAccountsSummary
    #        results

    settings.CYCLOS_CONSTANTS['cyclos_constants']['user_custom_fields']['bdc']
    bdc_id = ''
    query_data = [bdc_id, None]
    results = cyclos.post(model='account/getAccountsSummary', data=query_data)
    return Response(results)
