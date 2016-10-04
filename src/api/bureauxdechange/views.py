import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from cyclos_api import CyclosAPIException
from bureauxdechange.misc import BDC
# from bureauxdechange.serializers import BDCSerializer
from pagination import CustomPagination

log = logging.getLogger()


class BDCAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(BDCAPIView, self).__init__()

    def create(self, request):
        pass

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
                        pk, auth_string=request.user.profile.cyclos_auth_string)))
            except CyclosAPIException:
                return Response(status=status.HTTP_204_NO_CONTENT)

        elif pk and not valid_login:
            return Response({'error': 'You need to provide a *VALID* ?login parameter! (Format: B001)'},
                            status=status.HTTP_400_BAD_REQUEST)

    def list(self, request):
        """
        view_all param is used for filtering, it can filter out the bureaux de change that are disabled in Cyclos
        view_all is set to False by default: It doesn't return bureaux de change that are disabled in Cyclos
        """
        view_all = request.GET.get('view_all', False)
        if view_all and view_all in [True, 'true', 'True', 'yes', 'Yes']:
            # user/search for group = 'bureaux_de_change'
            query_data = {'groups': []}
        else:
            # user/search for group = 'bureaux_de_change'
            query_data = {'groups': [str(settings.CYCLOS_CONSTANTS['groups']['bureaux_de_change'])]}

        data = self.cyclos.post(method='user/search', data=query_data,
                                auth_string=request.user.profile.cyclos_auth_string)
        objects = [{'label': item['display'], 'value': item['id'], 'shortLabel': item['shortDisplay']}
                   for item in data['result']['pageItems']]

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(objects, request)
        return paginator.get_paginated_response(result_page)

    def update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model, api_key=dolibarr_token))
        pass

    def partial_update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model, api_key=dolibarr_token))
        pass
