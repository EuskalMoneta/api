import logging

from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from members.serializers import MemberSerializer, MembersSubscriptionsSerializer
from members.misc import Member, Subscription

log = logging.getLogger()


class MembersAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(MembersAPIView, self).__init__(model='members')

    def create(self, request):
        data = request.data
        serializer = MemberSerializer(data=data)
        if serializer.is_valid():  # raise_exception=True ?
            data = Member.validate_data(data)
        else:
            log.critical(serializer.errors)

        response_obj = self.dolibarr.post(model=self.model, data=data)
        log.info(response_obj)
        return Response(response_obj, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model))
        pass

    def partial_update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model))
        pass


class MembersSubscriptionsAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(MembersSubscriptionsAPIView, self).__init__(model='members/%_%/subcriptions')

    def create(self, request):
        data = request.data
        log.critical("data: {}".format(data))
        serializer = MembersSubscriptionsSerializer(data=data)
        if not serializer.is_valid():  # raise_exception=True ?
            log.critical("serializer.errors: {}".format(serializer.errors))

        member_id = data.get('member_id', '')
        if not member_id:
            Response('A member id must be provided !', status=status.HTTP_400_BAD_REQUEST)
        self.model = self.model.replace('%_%', member_id)
        log.critical("self.model: {}".format(self.model))

        member = self.dolibarr.get(model='members', id=member_id)
        data['start_date'] = Subscription.calculate_start_date(member['datefin'])
        data['end_date'] = Subscription.calculate_end_date(data['start_date'])
        data['label'] = Subscription.calculate_label(data['end_date'])

        log.critical("data after: {}".format(data))
        return Response({'member': member, 'data': data})

        response_obj = self.dolibarr.post(model=self.model, data=data)
        log.critical("response_obj: {}".format(response_obj))
        return Response(response_obj, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        pass

    def destroy(self, request, pk):
        pass
