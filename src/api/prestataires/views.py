import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from dolibarr_api import DolibarrAPI, DolibarrAPIException
from prestataires import serializers
from pagination import CustomPagination

logger = logging.getLogger()


class PrestatairesAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(PrestatairesAPIView, self).__init__()

    def list(self, request):
        """
        Récupérer la liste des prestataires.
        """
        # Vérification du paramètre "langue".
        language = request.GET.get('langue')
        logger.debug('language=' + str(language))
        if not language:
            return Response({'error': 'The "langue" parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if language not in ('eu', 'fr'):
            return Response({'error': 'Invalid value for the "langue" parameter.'}, status=status.HTTP_400_BAD_REQUEST)

        # Récupération des autres paramètres (qui sont optionnels).
        keyword = request.GET.get('mot-cle')
        category_id = request.GET.get('categorie')
        town_id = request.GET.get('ville')
        zipcode = request.GET.get('code-postal')
        bdc = request.GET.get('bdc', False)
        euskokart = request.GET.get('euskokart', False)

        logger.debug('keyword=' + str(keyword))
        logger.debug('category_id=' + str(category_id))
        logger.debug('town_id=' + str(town_id))
        logger.debug('zipcode=' + str(zipcode))
        logger.debug('bdc=' + str(bdc))
        logger.debug('euskokart=' + str(euskokart))

        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
#        return Response(dolibarr.get(model='towns', zipcode=search))

        objects = []
        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(objects, request)
        return paginator.get_paginated_response(result_page)

    def retrieve(self, request, pk):
        pass


class CategoriesPrestatairesAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(CategoriesPrestatairesAPIView, self).__init__()

    def list(self, request):
        """
        Récupérer la liste des catégories de prestataires (il s'agit ici des catégories pour l'annuaire, autrement dit de l'activité).
        """
        # Vérification du paramètre "langue".
        language = request.GET.get('langue')
        logger.debug('language=' + str(language))
        if not language:
            return Response({'error': 'The "langue" parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if language not in ('eu', 'fr'):
            return Response({'error': 'Invalid value for the "langue" parameter.'}, status=status.HTTP_400_BAD_REQUEST)

        language_index = 0 if language == 'eu' else 1

        # Récupération de toutes les catégories de clients de Dolibarr.
        # On filtre ensuite ces catégories pour ne garder que celles qui
        # sont des catégories pour l'annuaire c'est-à-dire toutes celles
        # de 1er niveau sauf '--- Etiquettes' et '--- Euskal Moneta'.
        # En même temps que l'on filtre les catégories, on construit une
        # nouvelle liste simplifiée, avec uniquement l'id et le nom de
        # chaque catégorie.
        customer_categories = self.dolibarr.get(model='categories', type='customer', api_key=request.user.profile.dolibarr_token)
        filtered_categories = [ {'id': cat['id'],
                                'nom': cat['label'].split(' / ')[language_index]}
                                for cat in customer_categories
                                if cat['fk_parent'] == '0'
                                and cat['label'] not in ('--- Etiquettes', '--- Euskal Moneta')]
        return Response(filtered_categories)
