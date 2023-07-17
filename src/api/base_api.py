import logging

from rest_framework import viewsets
from rest_framework.response import Response
from odoo_api import OdooAPI
from cyclos_api import CyclosAPI
from dolibarr_api import DolibarrAPI
from members.serializers import MemberSerializer
from pagination import CustomPagination
from members.misc import Member

log = logging.getLogger()


class BaseAPIView(viewsets.ViewSet):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.cyclos = CyclosAPI()

        try:
            if self.model:
                self.dolibarr = DolibarrAPI(model=self.model)
                self.odoo = OdooAPI()
        except AttributeError:
            self.dolibarr = DolibarrAPI()

    def list(self, request, *args, **kwargs):
        objects = self.dolibarr.get(model=self.model, api_key=request.user.profile.dolibarr_token)
        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(objects, request)

        serializer = MemberSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request, pk=None):
        response = self.odoo.get(model='res.partner',domain=[[('is_main_profile', '=', True),('id', '=', pk)]])
        return Response(Member.create_data_tab(response)[0])

    def create(self, request):
        pass

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        pass

    def destroy(self, request, pk):
        return Response(self.dolibarr.delete(model=self.model, id=pk, api_key=request.user.profile.dolibarr_token))