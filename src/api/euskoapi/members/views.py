import logging

from rest_framework.response import Response

from base_api import BaseAPIView
from members.serializers import MemberSerializer

log = logging.getLogger('')


class MembersAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(MembersAPIView, self).__init__(model='members')

    def create(self, request):
        serializer = MemberSerializer(request.data)
        data = serializer.data
        log.critical(data)

        return Response(self.dolibarr.post(model=self.model, data=data))

    def update(self, request, pk=None):
        return Response(self.dolibarr.patch(model=self.model))

    def partial_update(self, request, pk=None):
        return Response(self.dolibarr.patch(model=self.model))

    def destroy(self, request, pk=None):
        return Response(self.dolibarr.delete(model=self.model))
