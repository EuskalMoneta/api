import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from dolibarr_api import DolibarrAPIException
from prestataires import serializers
from pagination import CustomPagination

logger = logging.getLogger()


class PrestatairesAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(PrestatairesAPIView, self).__init__()

    def list(self, request):
        objects = []
        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(objects, request)
        return paginator.get_paginated_response(result_page)

    def retrieve(self, request, pk):
        pass
