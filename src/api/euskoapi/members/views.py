import logging

# from rest_framework.response import Response

from base_api import BaseAPIView
# from pagination import CustomPagination
# from members.serializers import MemberSerializer

log = logging.getLogger(__name__)


class MembersAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(MembersAPIView, self).__init__(model='members')

    def create(self, request):
        self.dolibarr.post(model=self.model)

    def update(self, request, pk=None):
        self.dolibarr.patch(model=self.model)

    def partial_update(self, request, pk=None):
        self.dolibarr.patch(model=self.model)

    def destroy(self, request, pk=None):
        self.dolibarr.delete(model=self.model)
