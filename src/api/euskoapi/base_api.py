import logging

from rest_framework import viewsets
from rest_framework.response import Response

from dolibarr_api import DolibarrAPI
from members.serializers import MemberSerializer
from pagination import CustomPagination

log = logging.getLogger(__name__)


class BaseAPIView(viewsets.ViewSet):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.dolibarr = DolibarrAPI(model=self.model)

    def list(self, request, *args, **kwargs):
        objects = self.dolibarr.get(model=self.model)
        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(objects, request)

        serializer = MemberSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request, pk=None):
        return Response(self.dolibarr.get(model=self.model, id=pk))

    def create(self, request):
        pass

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        pass

    def destroy(self, request, pk=None):
        pass
