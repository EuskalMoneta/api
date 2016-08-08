from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from dolibarr_api import DolibarrAPI


@api_view(['GET'])
def towns_by_zipcode(request):
    """
    List all towns, filtered by a zipcode.
    """
    search = request.GET.get('zipcode', '')
    if not search:
        Response('Zipcode must not be empty', status=status.HTTP_400_BAD_REQUEST)

    dolibarr = DolibarrAPI()
    return Response(dolibarr.get(model='towns', zipcode=search))


@api_view(['GET'])
def countries(request):
    """
    Get the list of countries.
    """
    dolibarr = DolibarrAPI()
    return Response(dolibarr.get(model='countries', lang='fr_FR'))


@api_view(['GET'])
def country_by_id(request, id):
    """
    Get country by ID.
    """
    dolibarr = DolibarrAPI()
    return Response(dolibarr.get(model='countries', id=id, lang='fr_FR'))
