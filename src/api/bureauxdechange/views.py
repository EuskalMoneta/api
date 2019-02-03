import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from cyclos_api import CyclosAPIException
from dolibarr_api import DolibarrAPIException
from bureauxdechange.misc import BDC
from bureauxdechange import serializers
from pagination import CustomPagination

log = logging.getLogger()


class BDCAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(BDCAPIView, self).__init__()

    def create(self, request):
        serializer = serializers.BDCSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

        # Création du user Bureau de change
        bdc_query_data = {
            'group': str(settings.CYCLOS_CONSTANTS['groups']['bureaux_de_change']),
            'name': '{} (BDC)'.format(request.data['name']),
            'username': '{}_BDC'.format(request.data['login']),
            'skipActivationEmail': True,
        }

        try:
            bdc_id = self.cyclos.post(method='user/register', data=bdc_query_data,
                                      token=request.user.profile.cyclos_token)['result']['user']['id']
        except (CyclosAPIException, KeyError):
            return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

        # Création du user Opérateur BDC
        operator_bdc_query_data = {
            'group': str(settings.CYCLOS_CONSTANTS['groups']['operateurs_bdc']),
            'name': request.data['name'],
            'username': request.data['login'],
            'passwords': [
                {
                    'type': str(settings.CYCLOS_CONSTANTS['password_types']['login_password']),
                    'value': request.data['login'],
                    'confirmationValue': request.data['login'],
                    'assign': True,
                    'forceChange': False,
                },
            ],
            'customValues': [
                {
                    'field': str(settings.CYCLOS_CONSTANTS['user_custom_fields']['bdc']),
                    'linkedEntityValue': bdc_id,
                }
            ],
            'skipActivationEmail': True,
        }

        try:
            self.cyclos.post(method='user/register', data=operator_bdc_query_data)
        except CyclosAPIException:
            return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

        # Création du user dans Dolibarr
        try:
            user_id = self.dolibarr.post(
                model='users', api_key=request.user.profile.dolibarr_token,
                data={"login": request.data['login'], "lastname": request.data['name']})
        except (DolibarrAPIException, KeyError):
            return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)

        # Ajouter l'utilisateur au groupe "Opérateurs BDC"
        try:
            self.dolibarr.get(model='users/{}/setGroup/{}'.format(
                user_id, str(settings.DOLIBARR_CONSTANTS['groups']['operateurs_bdc'])))
        except (DolibarrAPIException, KeyError):
            return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(request.data)

    def retrieve(self, request, pk):
        """
        pk => BDC Login (eg. B001)
        """
        valid_login = BDC.validate_login(pk)

        if pk and valid_login:
            # We want to search in bureaux de change by login
            # user/load for this ID => get all BDC data
            try:
                return Response(self.cyclos.post(
                    method='user/load',
                    data=self.cyclos.get_member_id_from_login(
                        pk, token=request.user.profile.cyclos_token)))
            except CyclosAPIException:
                return Response(status=status.HTTP_204_NO_CONTENT)

        elif pk and not valid_login:
            return Response({'error': 'You need to provide a *VALID* parameter! (Format: /B001)'},
                            status=status.HTTP_400_BAD_REQUEST)

    def list(self, request):
        """
        view_all param is used for filtering, it can filter out the bureaux de change that are disabled in Cyclos
        view_all is set to False by default: It doesn't return bureaux de change that are disabled in Cyclos
        """
        view_all = request.GET.get('view_all', False)
        if view_all and view_all in [True, 'true', 'True', 'yes', 'Yes']:
            # user/search for group = 'bureaux_de_change'
            query_data = {'groups': [str(settings.CYCLOS_CONSTANTS['groups']['bureaux_de_change'])],
                          'userStatus': ['ACTIVE', 'DISABLED']}
        else:
            # user/search for group = 'bureaux_de_change'
            query_data = {'groups': [str(settings.CYCLOS_CONSTANTS['groups']['bureaux_de_change'])],
                          'userStatus': ['ACTIVE']}

        data = self.cyclos.post(method='user/search', data=query_data,
                                token=request.user.profile.cyclos_token)
        objects = [{'label': item['display'], 'value': item['id'], 'shortLabel': item['shortDisplay']}
                   for item in data['result']['pageItems']]

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(objects, request)
        return paginator.get_paginated_response(result_page)

    def destroy(self, request, pk):
        """
        Close BDC
        """
        # Récupérer le user Opérateur BDC
        try:
            operator_bdc_id = self.dolibarr.get(
                api_key=request.user.profile.dolibarr_token, model='users', sqlfilters="login='{}'".format(pk))[0]['id']
        except (KeyError, IndexError):
            return Response({'error': 'Unable to get operator_bdc_id from this username!'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Désactiver l'utilisateur Opérateur BDC
        self.dolibarr.put(model='users/{}'.format(operator_bdc_id),
                          data={'statut': str(settings.DOLIBARR_CONSTANTS['user_statuses']['disabled'])})

        # Récupérer l'opérateur BDC correspondant au bureau de change
        bdc_operator_cyclos_query = {
            'groups': [str(settings.CYCLOS_CONSTANTS['groups']['operateurs_bdc'])],
            'keywords': pk,  # par exemple B003
        }
        try:
            bdc_operator_cyclos_id = self.cyclos.post(
                token=request.user.profile.cyclos_token,
                method='user/search', data=bdc_operator_cyclos_query)['result']['pageItems'][0]['id']
        except (KeyError, IndexError):
                    return Response({'error': 'Unable to get bdc_operator_cyclos_id data!'},
                                    status=status.HTTP_400_BAD_REQUEST)

        # Désactiver l'opérateur BDC
        deactivate_operator_bdc_data = {
            'user': bdc_operator_cyclos_id,
            'status': 'DISABLED',
        }
        self.cyclos.post(method='userStatus/changeStatus', data=deactivate_operator_bdc_data)

        # Récupérer l'utilisateur bureau de change
        bdc_user_cyclos_query = {
            'groups': [str(settings.CYCLOS_CONSTANTS['groups']['bureaux_de_change'])],
            'keywords': pk,  # par exemple B003
        }
        try:
            bdc_cyclos_id = self.cyclos.post(
                method='user/search', data=bdc_user_cyclos_query)['result']['pageItems'][0]['id']
        except (KeyError, IndexError):
                    return Response({'error': 'Unable to get bdc_cyclos_id data!'},
                                    status=status.HTTP_400_BAD_REQUEST)

        # Désactiver le bureau de change
        deactivate_bdc_data = {
            'user': bdc_cyclos_id,
            'status': 'DISABLED',
        }
        self.cyclos.post(method='userStatus/changeStatus', data=deactivate_bdc_data)

        return Response(pk)

    def update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model, api_key=dolibarr_token))
        pass

    def partial_update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model, api_key=dolibarr_token))
        pass
