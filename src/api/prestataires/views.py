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
        super(AnnuairePrestatairesAPIView, self).__init__()

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
        keyword = request.GET.get('mot_cle')
        category_id = request.GET.get('categorie')
        town = request.GET.get('ville')
        zipcode = request.GET.get('code_postal')
        bdc = True if request.GET.get('bdc') == '1' else False
        euskokart = True if request.GET.get('euskokart') == '1' else False

        logger.debug('keyword=' + str(keyword))
        logger.debug('category_id=' + str(category_id))
        logger.debug('town=' + str(town))
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
        # Les filtres sont appliqués le plus tôt possible, pour réduire
        # le temps de traitement.
        thirdparties = self.dolibarr.get(model='thirdparties',
                                         mode='1',
                                         api_key=request.user.profile.dolibarr_token)

        logger.debug('len(thirdparties) = ' + str(len(thirdparties)))

        resultat = []
        for thirdparty in thirdparties:
            if thirdparty['status'] == '1':
                logger.debug('thirdparty = ' + thirdparty['id'] + ' - ' + thirdparty['nom'])

                # Si le champ est vide, il vaut None. Dans ce cas, on
                # met une chaine vide dans la réponse.
                description = thirdparty['array_options']['options_description_'+language_name]
                horaires = thirdparty['array_options']['options_horaires_'+language_name]
                autres_lieux_activite = thirdparty['array_options']['options_autres_lieux_activite_'+language_name]

                prestataire = {
                          'id': thirdparty['id'],
                          'nom': thirdparty['nom'],
                          'description': description if description else '',
                          'horaires': horaires if horaires else '',
                          'autres_lieux_activite': autres_lieux_activite if autres_lieux_activite else '',
                          'site_web': thirdparty['url'],
                         }

                logger.debug('keyword = ' + keyword)
                logger.debug("prestataire['description'] = " + prestataire['description'])
                logger.debug("prestataire['horaires'] = " + prestataire['horaires'])
                logger.debug("prestataire['autres_lieux_activite'] = " + prestataire['autres_lieux_activite'])

                # Si le filtre "mot_cle" est actif, on ignore les prestataires
                # dont la description (horaires et autres lieux d'acticité inclus)
                # ne contient pas ce mot-clé. Le filtre est insensible à la casse.
                if (keyword
                    and keyword.lower() not in prestataire['description'].lower()
                    and keyword.lower() not in prestataire['horaires'].lower()
                    and keyword.lower() not in prestataire['autres_lieux_activite'].lower()):
                    continue

                # Le prestataire est-il équipé pour accepter les paiements par Euskokart ?
                champ_perso_euskokart = thirdparty['array_options']['options_equipement_pour_euskokart']
                logger.debug('champ_perso_euskokart = ' + champ_perso_euskokart)
                prestataire['euskokart'] = champ_perso_euskokart and champ_perso_euskokart.startswith('oui')

                # Si le filtre "euskokart" est actif, on ignore les prestataires
                # qui ne sont pas équipés pour accepter les paiements par Euskokart.
                if euskokart and not prestataire['euskokart']:
                    continue

                # On charge la liste des catégories de ce prestataire et
                # on récupère ses activités et ses étiquettes.
                categories = self.dolibarr.get(model='thirdparties',
                                               id=prestataire['id']+'/categories',
                                               api_key=request.user.profile.dolibarr_token)
                logger.debug('len(categories) = ' + str(len(categories)))

                activites = [ {'id': cat['id'],
                               'nom': cat['label'].split(' / ')[language_index]}
                              for cat in categories
                              if cat['fk_parent'] == '0'
                              and cat['label'] not in ('--- Etiquettes', '--- Euskal Moneta') ]
                prestataire['categories'] = activites
                logger.debug('len(activites) = ' + str(len(activites)))

                etiquettes = [ {'id': cat['id'],
                                'nom': cat['label'].split(' / ')[language_index]}
                               for cat in categories
                               # 360 = '--- Etiquettes'
                               if cat['fk_parent'] == '360' ]
                prestataire['etiquettes'] = etiquettes
                logger.debug('len(etiquettes) = ' + str(len(etiquettes)))

                # Si le filtre "categorie" est actif, on l'applique.
                if category_id and category_id not in [ cat['id'] for cat in activites ] :
                    continue

                # Le prestataire est-il bureau de change ?
                prestataire['bdc'] = len([ cat for cat in categories if cat['label'] == 'Bureau de change' ]) > 0

                # Si le filtre "bdc" est actif, on ignore les prestataires
                # qui ne sont pas des bureaux de change.
                if bdc and not prestataire['bdc']:
                    continue

                # On charge la liste des contacts de ce prestataire et
                # on filtre cette liste pour ne garder que les adresses
                # d'activité.
                contacts = self.dolibarr.get(model='contacts',
                                             socid=prestataire['id'],
                                             api_key=request.user.profile.dolibarr_token)
                adresses = [ c for c in contacts if c['lastname'] == "Adresse d'activité" ]

                # Chaque adresse d'activité peut être un élément du résultat (s'il correspond aux filtres).
                for adresse in adresses:

                    # Si le filtre "code_postal" est actif, on l'applique.
                    if zipcode and adresse['zip'] != zipcode:
                        continue

                    # Recopie de toutes les infos venant du prestataire
                    prestataire_pour_annuaire = prestataire
                    # Recopie de toutes les infos venant de l'adresse d'activité
                    prestataire_pour_annuaire['adresse'] = adresse['address']
                    prestataire_pour_annuaire['code_postal'] = adresse['zip']
                    prestataire_pour_annuaire['ville'] = adresse['town'].split('/')[language_index].strip()
                    prestataire_pour_annuaire['latitude'] = adresse['array_options']['options_latitude']
                    prestataire_pour_annuaire['longitude'] = adresse['array_options']['options_longitude']
                    prestataire_pour_annuaire['telephone'] = adresse['phone_pro']
                    prestataire_pour_annuaire['telephone2'] = adresse['phone_mobile']
                    prestataire_pour_annuaire['email'] = adresse['mail']

                    # Si le filtre "ville" est actif, on l'applique
                    # (on l'applique après la recopie des infos car il faut que le nom
                    # de la ville ait été extrait dans la langue demandée).
                    if town and prestataire_pour_annuaire['ville'] != town:
                        continue

                    resultat.append(prestataire_pour_annuaire)

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(resultat, request)
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
