import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from dolibarr_api import DolibarrAPI, DolibarrAPIException
from prestataires import serializers
from pagination import CustomPagination

logger = logging.getLogger()


class AnnuairePrestatairesAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(PrestatairesAPIView, self).__init__()

    def list(self, request):
        """
        Récupérer la liste des prestataires pour l'annuaire.
        """
        # Vérification du paramètre "langue".
        language = request.GET.get('langue')
        logger.debug('language=' + str(language))
        if not language:
            return Response({'error': 'The "langue" parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if language not in ('eu', 'fr'):
            return Response({'error': 'Invalid value for the "langue" parameter.'}, status=status.HTTP_400_BAD_REQUEST)

        language_index = 0 if language == 'eu' else 1
        language_name = 'euskara' if language == 'eu' else 'francais'

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

        # Récupération des prestataires correspondant aux filtres passés
        # en paramètre.
        #
        # On récupère d'abord la liste de tous les prestataires agréés
        # et on ne garde que ceux qui sont en activité.
        # Pour chacun d'entre eux, on récupère ensuite toutes les
        # autres informations dont on va avoir besoin soit pour les
        # mettre dans la réponse, soit pour filtrer les résultats :
        #     - le prestataire est-il équipé pour accepter les paiements par Euskokart ?
        #     - les catégories (les catégories d'activité, et les
        #       étiquettes comme "Bai Euskarari" ou "Idoki")
        #     - le prestataire est-il bureau de change ?
        #     - les adresses d'activité; en fait ce sont ces adresses
        #       d'activité qui sont les éléments de base du résultat (si
        #       un prestataire a 2 adresses d'activité, il apparaitra
        #       2 fois dans le résultat; s'il n'a pas d'adresse
        #       d'activité, il n'apparaitra jamais dans les résultats).
        # A chaque fois, on ne garde que les informations dans la langue
        # demandée. C'est important de faire cela avant d'appliquer le
        # filtre par mot-clé, sinon cela peut fausser le résultat.
        #
        # Enfin, on applique les filtres passés en paramètre (ce n'est
        # peut-être pas optimal mais c'est le plus simple; s'il y a des
        # problèmes de performance, il faudra revoir cela).
        thirdparties = self.dolibarr.get(model='thirdparties',
                                         mode='1',
                                         api_key=request.user.profile.dolibarr_token)
        prestataires = []
        for thirdparty in thirdparties:
            if thirdparty['status'] == '1':
                prestataire = {
                          'id': thirdparty['id'],
                          'nom': thirdparty['nom'],
                          'description': thirdparty['array_options']['options_description_'+language_name],
                          'horaires': thirdparty['array_options']['options_horaires_'+language_name],
                          'autres_lieux_activite': thirdparty['array_options']['options_autres_lieux_activite_'+language_name],
                          'adresse': 'TODO',
                          'longitude': 'TODO',
                          'latitude': 'TODO',
                          'telephone': 'TODO',
                          'telephone2': 'TODO',
                          'email': 'TODO',
                          'site_web': thirdparty['url'],
                         }

                # Le prestataire est-il équipé pour accepter les paiements par Euskokart ?
                champ_perso_euskokart = thirdparty['array_options']['options_equipement_pour_euskokart']
                euskokart = champ_perso_euskokart and champ_perso_euskokart.startswith('Oui')
                prestataire['euskokart'] = euskokart

                # On charge la liste des catégories de ce prestataire et
                # on récupère ses activités et ses étiquettes.
                categories = self.dolibarr.get(model='thirdparties',
                                               id=prestataire['id']+'/categories',
                                               api_key=request.user.profile.dolibarr_token)
                activites = [ {'id': cat['id'],
                               'nom': cat['label'].split(' / ')[language_index]}
                              for cat in categories
                              if cat['fk_parent'] == '0'
                              and cat['label'] not in ('--- Etiquettes', '--- Euskal Moneta') ]
                prestataire['categories'] = activites
                etiquettes = [ {'id': cat['id'],
                                'nom': cat['label'].split(' / ')[language_index]}
                               for cat in categories
                               # 360 = '--- Etiquettes'
                               if cat['fk_parent'] == '360' ]
                prestataire['etiquettes'] = etiquettes

                # Le prestataire est-il bureau de change ?
                prestataire['bdc'] = len([ cat for cat in categories if cat['label'] == 'Bureau de change' ]) > 0

                # On charge la liste des contacts de ce prestataire et
                # on filtre cette liste pour ne garder que les adresses
                # d'activité.
                # TODO ajouter GET /thirdparties/{id}/contacts dans l'API de Dolibarr.
                contacts = self.dolibarr.get(model='thirdparties',
                                             id=prestataire['id']+'/contacts',
                                             api_key=request.user.profile.dolibarr_token)
                adresses = [ c for c in contacts if c['label'] == "Adresse d'activité" ]

                prestataires.append(prestataire)

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(prestataires, request)
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


class VillesPrestatairesAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(VillesPrestatairesAPIView, self).__init__()

    def list(self, request):
        """
        Récupérer la liste des villes dans lesquelles il peut y avoir
        des prestataires (toutes les communes du Pays Basque Nord, en fait).
        """
        # Vérification du paramètre "langue".
        language = request.GET.get('langue')
        logger.debug('language=' + str(language))
        if not language:
            return Response({'error': 'The "langue" parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if language not in ('eu', 'fr'):
            return Response({'error': 'Invalid value for the "langue" parameter.'}, status=status.HTTP_400_BAD_REQUEST)

        language_index = 0 if language == 'eu' else 1

        # Récupération des communes enregistrées dans Dolibarr qui sont
        # dans le 64 et dont le nom contient '/' (ce sont celles du
        # Pays Basque Nord car nous avons mis leur nom en bilingue
        # euskara / français).
        towns = self.dolibarr.get(model='towns', zipcode='64', town='/', api_key=request.user.profile.dolibarr_token)
        localized_towns = [ {'id': town['id'],
                             'code_postal': town['zip'],
                             'nom': town['town'].split('/')[language_index].strip()}
                            for town in towns ]
        return Response(localized_towns)
