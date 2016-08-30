import logging

import arrow
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from dolibarr_api import DolibarrAPIException
from members.serializers import MemberSerializer, MembersSubscriptionsSerializer
from members.misc import Member, Subscription
from misc import sendmail_euskalmoneta
from pagination import CustomPagination

log = logging.getLogger()


class MembersAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(MembersAPIView, self).__init__(model='members')

    def create(self, request):
        data = request.data
        dolibarr_token = request.user.profile.dolibarr_token
        serializer = MemberSerializer(data=data)
        if serializer.is_valid():
            data = Member.validate_data(data)
        else:
            log.critical(serializer.errors)
            return Response({'error': 'Oops! Something is wrong in your request data: {}'.format(serializer.errors)},
                            status=status.HTTP_400_BAD_REQUEST)

        log.info('posted data: {}'.format(data))
        response_obj = self.dolibarr.post(model=self.model, data=data, api_key=dolibarr_token)
        log.info(response_obj)
        try:
            sendmail_euskalmoneta(subject="subject", body="body", to_email=data['email'])
        except KeyError:
            log.critical("Oops! No mail sent to the member, we didn't had a email address !")
        return Response(response_obj, status=status.HTTP_201_CREATED)

    def list(self, request):
        login = request.GET.get('login', '')
        name = request.GET.get('name', '')
        valid_login = Member.validate_num_adherent(login)
        dolibarr_token = request.user.profile.dolibarr_token

        if login and valid_login:
            # We want to search in members by login (N° Adhérent)
            try:
                response = self.dolibarr.get(model='members', login=login, api_key=dolibarr_token)
            except DolibarrAPIException:
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(response)

        elif login and not valid_login:
            return Response({'error': 'You need to provide a *VALID* ?login parameter! (Format: E12345)'},
                            status=status.HTTP_400_BAD_REQUEST)

        elif name and len(name) >= 4:
            # We want to search in members by name (Firstname and Lastname)
            try:
                response = self.dolibarr.get(model='members', name=name, api_key=dolibarr_token)
            except DolibarrAPIException:
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(response)

        elif name and len(name) < 4:
            return Response({'error': 'You need to provide a ?name parameter longer than 3 characters!'},
                            status=status.HTTP_400_BAD_REQUEST)

        else:
            objects = self.dolibarr.get(model=self.model, api_key=dolibarr_token)
            paginator = CustomPagination()
            result_page = paginator.paginate_queryset(objects, request)

            serializer = MemberSerializer(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)

    def update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model, api_key=dolibarr_token))
        pass

    def partial_update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model, api_key=dolibarr_token))
        pass


class MembersSubscriptionsAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(MembersSubscriptionsAPIView, self).__init__(model='members/%_%/subscriptions')

    def create(self, request):
        data = request.data
        dolibarr_token = request.user.profile.dolibarr_token
        log.info("data: {}".format(data))
        serializer = MembersSubscriptionsSerializer(data=data)
        if not serializer.is_valid():
            log.critical("serializer.errors: {}".format(serializer.errors))
            return Response({'error': 'Oops! Something is wrong in your request data: {}'.format(serializer.errors)},
                            status=status.HTTP_400_BAD_REQUEST)

        member_id = data.get('member_id', '')
        if not member_id:
            log.critical('A member_id must be provided!')
            return Response({'error': 'A member_id must be provided!'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            member = self.dolibarr.get(model='members', id=member_id, api_key=dolibarr_token)
        except DolibarrAPIException as e:
            log.critical("member_id: {}".format(member_id))
            log.critical(e)
            log.critical('This member_id was not found in the database!')
            return Response({'error': 'This member_id was not found in the database!'},
                            status=status.HTTP_400_BAD_REQUEST)

        data['start_date'] = Subscription.calculate_start_date(member['datefin'])
        data['end_date'] = Subscription.calculate_end_date(data['start_date'])
        data['label'] = Subscription.calculate_label(data['end_date'])

        log.info("data after: {}".format(data))

        # Register new subscription
        data_res_subscription = {'start_date': data['start_date'], 'end_date': data['end_date'],
                                 'amount': data['amount'], 'label': data['label']}
        self.model = self.model.replace('%_%', member_id)
        try:
            res_id_subscription = self.dolibarr.post(
                model=self.model, data=data_res_subscription, api_key=dolibarr_token)

            log.info("res_id_subscription: {}".format(res_id_subscription))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(self.model))
            log.critical("data_res_subscription: {}".format(data_res_subscription))
            log.critical(e)
            return Response({'error': e}, status=status.HTTP_400_BAD_REQUEST)

        # Register new payment
        payment_account, payment_type = Subscription.account_and_type_from_payment_mode(data['payment_mode'])
        if not payment_account or not payment_type:
            log.critical('This payment_mode is invalid!')
            return Response({'error': 'This payment_mode is invalid!'}, status=status.HTTP_400_BAD_REQUEST)

        data_res_payment = {'date': arrow.now('Europe/Paris').timestamp, 'type': payment_type,
                            'label': data['label'], 'amount': data['amount']}
        model_res_payment = 'accounts/{}/lines'.format(payment_account)
        try:
            res_id_payment = self.dolibarr.post(
                model=model_res_payment, data=data_res_payment, api_key=dolibarr_token)

            log.info("res_id_payment: {}".format(res_id_payment))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_res_payment))
            log.critical("data_res_payment: {}".format(data_res_payment))
            log.critical(e)
            return Response({'error': e}, status=status.HTTP_400_BAD_REQUEST)

        # Link this new subscription with this new payment
        data_link_sub_payment = {'fk_bank': res_id_payment}
        model_link_sub_payment = 'subscriptions/{}'.format(res_id_subscription)
        try:
            res_id_link_sub_payment = self.dolibarr.patch(
                model=model_link_sub_payment, data=data_link_sub_payment, api_key=dolibarr_token)

            log.info("res_id_link_sub_payment: {}".format(res_id_link_sub_payment))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_link_sub_payment))
            log.critical("data_link_sub_payment: {}".format(data_link_sub_payment))
            log.critical(e)
            return Response({'error': e}, status=status.HTTP_400_BAD_REQUEST)

        # Link this payment with the related-member
        data_link_payment_member = {'label': '{} {}'.format(member['firstname'], member['lastname']),
                                    'type': 'member', 'url_id': member_id,
                                    'url': '{}/adherents/card.php?rowid={}'.format(
                                        settings.DOLIBARR_PUBLIC_URL, member_id)}
        model_link_payment_member = 'accounts/{}/lines/{}/links'.format(payment_account, res_id_payment)
        try:
            res_id_link_payment_member = self.dolibarr.post(
                model=model_link_payment_member, data=data_link_payment_member,
                api_key=dolibarr_token)

            log.info("res_id_link_payment_member: {}".format(res_id_link_payment_member))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_link_payment_member))
            log.critical("data_link_payment_member: {}".format(data_link_payment_member))
            log.critical(e)
            return Response({'error': e}, status=status.HTTP_400_BAD_REQUEST)

        current_member = self.dolibarr.get(model='members', id=member_id, api_key=dolibarr_token)
        res = {'id_subscription': res_id_subscription,
               'id_payment': res_id_payment,
               'link_sub_payment': res_id_link_sub_payment,
               'id_link_payment_member': res_id_link_payment_member,
               'member': current_member}

        try:
            sendmail_euskalmoneta(subject="subject", body="body", to_email=current_member['email'])
        except KeyError:
            log.critical("Oops! No mail sent to this member {}, "
                         "we didn't had a email address !".format(current_member['email']))

        return Response(res, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        pass

    def destroy(self, request, pk):
        pass
