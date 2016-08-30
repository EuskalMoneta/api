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
    TODO
    """
    cyclos = CyclosAPI()
    data = {settings.CYCLOS_URL}
    results = cyclos.post(model='account/getAccountsSummary', data=data)
    return Response(results)
