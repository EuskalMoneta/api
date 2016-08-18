import logging

import arrow
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from dolibarr_api import DolibarrAPIException
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
        super(MembersSubscriptionsAPIView, self).__init__(model='members/%_%/subscriptions')

    def create(self, request):
        data = request.data
        log.info("data: {}".format(data))
        serializer = MembersSubscriptionsSerializer(data=data)
        if not serializer.is_valid():
            log.critical("serializer.errors: {}".format(serializer.errors))
            return Response('Oops! Something is wrong in your request data: {}'.format(serializer.errors),
                            status=status.HTTP_400_BAD_REQUEST)

        member_id = data.get('member_id', '')
        if not member_id:
            log.critical('A member_id must be provided!')
            return Response('A member_id must be provided!', status=status.HTTP_400_BAD_REQUEST)

        try:
            member = self.dolibarr.get(model='members', id=member_id)
        except DolibarrAPIException as e:
            log.critical("member_id: {}".format(member_id))
            log.critical(e)
            log.critical('This member_id was not found in the database!')
            return Response('This member_id was not found in the database!', status=status.HTTP_400_BAD_REQUEST)

        data['start_date'] = Subscription.calculate_start_date(member['datefin'])
        data['end_date'] = Subscription.calculate_end_date(data['start_date'])
        data['label'] = Subscription.calculate_label(data['end_date'])

        log.info("data after: {}".format(data))

        # Register new subscription
        data_res_subscription = {'start_date': data['start_date'], 'end_date': data['end_date'],
                                 'amount': data['amount'], 'label': data['label']}
        self.model = self.model.replace('%_%', member_id)
        try:
            res_id_subscription = self.dolibarr.post(model=self.model, data=data_res_subscription)
            log.info("res_id_subscription: {}".format(res_id_subscription))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(self.model))
            log.critical("data_res_subscription: {}".format(data_res_subscription))
            log.critical(e)
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        # Register new payment
        payment_account, payment_type = Subscription.account_and_type_from_payment_mode(data['payment_mode'])
        if not payment_account or not payment_type:
            log.critical('This payment_mode is invalid!')
            return Response('This payment_mode is invalid!', status=status.HTTP_400_BAD_REQUEST)

        data_res_payment = {'date': arrow.now('Europe/Paris').timestamp, 'type': payment_type,
                            'label': data['label'], 'amount': data['amount']}
        model_res_payment = 'accounts/{}/lines'.format(payment_account)
        try:
            res_id_payment = self.dolibarr.post(model=model_res_payment, data=data_res_payment)
            log.info("res_id_payment: {}".format(res_id_payment))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_res_payment))
            log.critical("data_res_payment: {}".format(data_res_payment))
            log.critical(e)
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        # Link this new subscription with this new payment
        data_link_sub_payment = {'fk_bank': res_id_payment}
        model_link_sub_payment = 'subscriptions/{}'.format(res_id_subscription)
        try:
            res_id_link_sub_payment = self.dolibarr.patch(model=model_link_sub_payment, data=data_link_sub_payment)
            log.info("res_id_link_sub_payment: {}".format(res_id_link_sub_payment))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_link_sub_payment))
            log.critical("data_link_sub_payment: {}".format(data_link_sub_payment))
            log.critical(e)
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        # Link this payment with the related-member
        data_link_payment_member = {'label': '{} {}'.format(member['firstname'], member['lastname']),
                                    'type': 'member', 'url_id': member_id,
                                    'url': '{}/adherents/card.php?rowid={}'.format(
                                        settings.DOLIBARR_PUBLIC_URL, member_id)}
        model_link_payment_member = 'accounts/{}/lines/{}/links'.format(payment_account, res_id_payment)
        try:
            res_id_link_payment_member = self.dolibarr.post(model=model_link_payment_member,
                                                            data=data_link_payment_member)
            log.info("res_id_link_payment_member: {}".format(res_id_link_payment_member))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_link_payment_member))
            log.critical("data_link_payment_member: {}".format(data_link_payment_member))
            log.critical(e)
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        res = {'id_subscription': res_id_subscription,
               'id_payment': res_id_payment,
               'link_sub_payment': res_id_link_sub_payment,
               'id_link_payment_member': res_id_link_payment_member,
               'member': self.dolibarr.get(model='members', id=member_id)}
        return Response(res, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        pass

    def destroy(self, request, pk):
        pass
