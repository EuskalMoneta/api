import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from dolibarr_api import DolibarrAPI

log = logging.getLogger()


@api_view(['GET'])
def associations(request):
    """
    List all associations, and if you want, you can filter them.
    """
    dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    results = dolibarr.get(model='associations')
    approved = request.GET.get('approved', '')
    if approved:
        # We want to filter out the associations that doesn't have the required sponsorships
        filtered_results = [item
                            for item in results
                            if int(item['nb_parrains']) >= settings.MINIMUM_PARRAINAGES_3_POURCENTS]
        return Response(filtered_results)
    else:
        return Response(results)


@api_view(['GET'])
def towns_by_zipcode(request):
    """
    List all towns, filtered by a zipcode.
    """
    search = request.GET.get('zipcode', '')
    if not search:
        Response({'error': 'Zipcode must not be empty'}, status=status.HTTP_400_BAD_REQUEST)

    dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    return Response(dolibarr.get(model='towns', zipcode=search))


@api_view(['GET'])
def countries(request):
    """
    Get the list of countries.
    """
    dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    return Response(dolibarr.get(model='countries', lang='fr_FR'))


@api_view(['GET'])
def country_by_id(request, id):
    """
    Get country by ID.
    """
    dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    return Response(dolibarr.get(model='countries', id=id, lang='fr_FR'))
