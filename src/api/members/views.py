import logging

import arrow
from django import forms
from django.conf import settings
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.utils.translation import activate, gettext as _
from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from base_api import BaseAPIView
from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException
from odoo_api import OdooAPI
from members.serializers import MemberSerializer, MembersSubscriptionsSerializer, MemberPartialSerializer
from members.misc import Member, Subscription
from misc import sendmail_euskalmoneta
from pagination import CustomPagination
import json
log = logging.getLogger()


@permission_classes((AllowAny, ))
class MembersAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(MembersAPIView, self).__init__(model='members')

    def create(self, request):
        data = request.data
        serializer = MemberSerializer(data=data)
        if serializer.is_valid():
            data = Member.validate_data(data)
        else:
            log.critical(serializer.errors)
            return Response({'error': 'Oops! Something is wrong in your request data: {}'.format(serializer.errors)},
                            status=status.HTTP_400_BAD_REQUEST)

        log.info('posted data: {}'.format(data))

        # #841 : We need to connect to Cyclos before doing Dolibarr calls, making sure Cyclos token is still valid.
        # This way, we avoid creating a member in Dolibarr if it's not the case.
        try:
            self.cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='bdc')
        except CyclosAPIException:
            return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

        # Dolibarr: Register member
        response_obj = self.dolibarr.post(model=self.model, data=data, api_key=request.user.profile.dolibarr_token)
        log.info(response_obj)

        # Cyclos: Register member
        create_user_data = {
            'group': str(settings.CYCLOS_CONSTANTS['groups']['adherents_sans_compte']),
            'name': '{} {}'.format(data['firstname'], data['lastname']),
            'username': data['login'],
            'skipActivationEmail': True,
        }
        self.cyclos.post(method='user/register', data=create_user_data)

        return Response(response_obj, status=status.HTTP_201_CREATED)

    def list(self, request):
        email = request.GET.get('email', '')
        login = request.GET.get('login', '')
        name = request.GET.get('name', '')
        valid_login = Member.validate_num_adherent(login)
        token = request.GET.get('token', '')
        odoo = OdooAPI()
        # Si un token est fourni pour récupérer un adhérent, la
        # recherche peut être faite de manière anonyme, sinon il faut
        # être authentifié, afin d'éviter la fuite d'information sur les
        # adhérents.
        if token and not request.user.is_authenticated:
            dolibarr = DolibarrAPI()
            dolibarr_token = dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                                            password=settings.APPS_ANONYMOUS_PASSWORD)
        else:
            dolibarr_token = request.user.profile.dolibarr_token

        if login and valid_login:
            # We want to search in members by login (N° Adhérent
            try:
                response = self.odoo.get(model='res.partner',
                                         domain=[[('is_main_profile', '=', True),
                                                  ('ref', '=', login),('customer','=',True)]])
            except DolibarrAPIException:
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(Member.create_data_tab(response))
        elif login and not valid_login:
            return Response({'error': 'You need to provide a *VALID* ?login parameter! (Format: E12345)'},
                            status=status.HTTP_400_BAD_REQUEST)

        elif name and len(name) >= 3:
            # We want to search in members by name (firstname, lastname or societe)
            try:
                response = self.odoo.get(model='res.partner', domain=[[('is_main_profile', '=', True),
                                                                  '|',('firstname', 'ilike', name),
                                                                       ('lastname', 'ilike', name),('customer','=',True)
                                                                  ]])
            except DolibarrAPIException:
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(Member.create_data_tab(response))

        elif name and len(name) < 3:
            return Response({'error': 'You need to provide a ?name parameter longer than 2 characters!'},
                            status=status.HTTP_400_BAD_REQUEST)

        elif email:
            try:
                validate_email(email)
                user_results = self.odoo.get(model='res.partner',domain=[[('is_main_profile', '=', True),
                                                                          ('email', '=', email),('customer','=',True)]])
            except forms.ValidationError:
                return Response({'error': 'You need to provide a *VALID* ?email parameter! (Format: E12345)'},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response(Member.create_data_tab(user_results))
        elif token:
            try:
                response = self.odoo.get(model='res.partner',domain=[[('is_main_profile', '=', True),
                                                                      ('token', '=', token),('customer','=',True)]])
            except DolibarrAPIException:
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(Member.create_data_tab(response))
        else:
            objects = self.dolibarr.get(model='members', sqlfilters="statut=1", api_key=dolibarr_token)
            paginator = CustomPagination()
            result_page = paginator.paginate_queryset(objects, request)
            #TODO
            serializer = MemberSerializer(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)

    def update(self, request, pk=None):
        # return Response(self.dolibarr.patch(model=self.model, api_key=dolibarr_token))
        pass

    def partial_update(self, request, pk=None):
        serializer = MemberPartialSerializer(data=request.data)
        if serializer.is_valid():
            odoo = OdooAPI()
            response = odoo.get(model='res.partner',domain=[[('is_main_profile', '=', True),('id', '=', pk)]])
            member = []
            for i in range(len(response)):
                member.append({
                    "login": response[i]['ref'],
                    "address": response[i]['street'],
                    "zip": response[i]['zip'],
                    "id": response[i]['id'],
                    "town": response[i]['city'],
                    "statut": "1",
                    "typeid": response[i]['member_type_id'][0] if response[i]['member_type_id'] else 'null',
                    "type": response[i]['member_type_id'][1] if response[i]['member_type_id'] else 'null',
                    "datefin": response[i]['membership_stop'],
                    "array_options": {
                        "options_accepte_cgu_eusko_numerique": response[i]['accept_cgu_numerical_eusko'],
                        "options_documents_pour_ouverture_du_compte_valides": response[i][
                            'numeric_wallet_document_valid'],
                        "options_accord_pour_ouverture_de_compte": 'oui' if response[i][
                            'refuse_numeric_wallet_creation'] else 'non',
                    },
                    "societe": response[i]['commercial_company_name'] if response[i][
                        'commercial_company_name'] else 'null',
                    "company": response[i]['commercial_company_name'] if response[i][
                        'commercial_company_name'] else 'null',
                    "lastname": response[i]['lastname'],
                    "firstname": response[i]['firstname'],
                    "civility_id": response[i]['title'][1] if response[i]['title'] else 'null',
                })
            # Validate / modify data (serialize to match Dolibarr formats)
            data = Member.validate_data(request.data, mode='update', base_options=member['array_options'])

            # Validate / modify data (serialize to match Dolibarr formats)
            data = Member.validate_data(request.data, mode='update', base_options=member['array_options'])

            try:
                # Envoi d'un email lorsque l'option "Recevoir les actualités liées à l'Eusko" est modifiée
                if (member['array_options']['options_recevoir_actus'] !=
                   data['array_options']['options_recevoir_actus']):
                    Member.send_mail_newsletter(
                        login=str(request.user), profile=request.user.profile,
                        new_status=data['array_options']['options_recevoir_actus'],
                        lang=member['array_options']['options_langue'])

                # Envoi d'un email lorsque l'option "Montant du change automatique" est modifiée
                if (member['array_options']['options_prelevement_change_montant'] is not None
                        and data['array_options']['options_prelevement_change_montant'] is not None
                        and float(member['array_options']['options_prelevement_change_montant']) !=
                        float(data['array_options']['options_prelevement_change_montant'])):
                    Member.send_mail_change_auto(
                        login=str(request.user), profile=request.user.profile,
                        mode=data['mode'], new_amount=data['array_options']['options_prelevement_change_montant'],
                        comment=data['prelevement_change_comment'], email=member['email'],
                        lang=member['array_options']['options_langue'])

                # Envoi d'un email lorsque l'option "IBAN" est modifiée.
                if (member['array_options']['options_iban'] !=
                   data['array_options']['options_iban']):
                    sujet = _("Modification de l'IBAN pour le change automatique mensuel")
                    texte = render_to_string('mails/modification_iban.txt',
                                             {'dolibarr_member': member,
                                             'nouvel_iban': data['array_options']['options_iban']}).strip('\n')
                    sendmail_euskalmoneta(subject=sujet, body=texte)

            except KeyError:
                pass
        else:
            log.critical(serializer.errors)
            return Response({'error': 'Oops! Something is wrong in your request data: {}'.format(serializer.errors)},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(self.dolibarr.put(model='members/{}'.format(pk), data=data,
                                            api_key=request.user.profile.dolibarr_token))


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

        # #841 : We need to connect to Cyclos before doing Dolibarr calls, making sure Cyclos token is still valid.
        # This way, we avoid creating a subscription in Dolibarr if it's not the case.
        try:
            self.cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='bdc')
        except CyclosAPIException:
            return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

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
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Register new payment
        payment_account, payment_type, payment_label = Subscription.account_and_type_from_payment_mode(data['payment_mode']) # noqa
        if not payment_account or not payment_type:
            log.critical('This payment_mode is invalid!')
            return Response({'error': 'This payment_mode is invalid!'}, status=status.HTTP_400_BAD_REQUEST)

        data_res_payment = {'date': arrow.now('Europe/Paris').timestamp, 'type': payment_type,
                            'label': data['label'], 'amount': data['amount']}
        model_res_payment = 'bankaccounts/{}/lines'.format(payment_account)
        try:
            res_id_payment = self.dolibarr.post(
                model=model_res_payment, data=data_res_payment, api_key=dolibarr_token)

            log.info("res_id_payment: {}".format(res_id_payment))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_res_payment))
            log.critical("data_res_payment: {}".format(data_res_payment))
            log.critical(e)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Link this new subscription with this new payment
        data_link_sub_payment = {'fk_bank': res_id_payment}
        model_link_sub_payment = 'subscriptions/{}'.format(res_id_subscription)
        try:
            res_id_link_sub_payment = self.dolibarr.put(
                model=model_link_sub_payment, data=data_link_sub_payment, api_key=dolibarr_token)

            log.info("res_id_link_sub_payment: {}".format(res_id_link_sub_payment))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_link_sub_payment))
            log.critical("data_link_sub_payment: {}".format(data_link_sub_payment))
            log.critical(e)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Link this payment with the related-member
        data_link_payment_member = {'label': '{} {}'.format(member['firstname'], member['lastname']),
                                    'type': 'member', 'url_id': member_id,
                                    'url': '{}/adherents/card.php?rowid={}'.format(
                                        settings.DOLIBARR_PUBLIC_URL, member_id)}
        model_link_payment_member = 'bankaccounts/{}/lines/{}/links'.format(payment_account, res_id_payment)
        try:
            res_id_link_payment_member = self.dolibarr.post(
                model=model_link_payment_member, data=data_link_payment_member,
                api_key=dolibarr_token)

            log.info("res_id_link_payment_member: {}".format(res_id_link_payment_member))
        except DolibarrAPIException as e:
            log.critical("model: {}".format(model_link_payment_member))
            log.critical("data_link_payment_member: {}".format(data_link_payment_member))
            log.critical(e)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        current_member = self.dolibarr.get(model='members', id=member_id, api_key=dolibarr_token)
        res = {'id_subscription': res_id_subscription,
               'id_payment': res_id_payment,
               'link_sub_payment': res_id_link_sub_payment,
               'id_link_payment_member': res_id_link_payment_member,
               'member': current_member}

        if current_member['type'].lower() in ('particulier', 'touriste'):
            member_name = '{} {}'.format(current_member['firstname'], current_member['lastname'])
        else:
            member_name = current_member['company']

        # Get Cyclos member and create it if it does not exist.
        try:
            member_cyclos_id = self.cyclos.get_member_id_from_login(current_member['login'])
        except CyclosAPIException:
            log.debug("Member not found in Cyclos, will create it.")
            create_user_data = {
                'group': str(settings.CYCLOS_CONSTANTS['groups']['adherents_sans_compte']),
                'name': '{} {}'.format(current_member['firstname'], current_member['lastname']),
                'username': current_member['login'],
                'skipActivationEmail': True,
            }
            log.debug("create_user_data = {}".format(create_user_data))
            response_data = self.cyclos.post(method='user/register', data=create_user_data)
            member_cyclos_id = response_data['result']['user']['id']
        log.debug("member_cyclos_id = {}".format(member_cyclos_id))

        # Cyclos: Register member subscription payment
        query_data = {}

        if 'Eusko' in data['payment_mode']:
            query_data.update(
                {'type': str(settings.CYCLOS_CONSTANTS['payment_types']['cotisation_en_eusko']),
                 'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
                 'customValues': [
                    {'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                     'linkedEntityValue': member_cyclos_id}],
                 'description': 'Cotisation - {} - {}'.format(
                    current_member['login'], member_name),
                 })
            currency = 'eusko'
        elif 'Euro' in data['payment_mode']:
            query_data.update(
                {'type': str(settings.CYCLOS_CONSTANTS['payment_types']['cotisation_en_euro']),
                 'currency': str(settings.CYCLOS_CONSTANTS['currencies']['euro']),
                 'customValues': [
                    {'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['adherent']),
                     'linkedEntityValue': member_cyclos_id},
                    {'field': str(settings.CYCLOS_CONSTANTS['transaction_custom_fields']['mode_de_paiement']),
                     'enumeratedValues': data['cyclos_id_payment_mode']}],
                 'description': 'Cotisation - {} - {} - {}'.format(
                    current_member['login'], member_name, payment_label),
                 })
            currency = '€'
        else:
            return Response({'error': 'This payment_mode is invalid!'}, status=status.HTTP_400_BAD_REQUEST)

        query_data.update({
            'amount': data['amount'],
            'from': 'SYSTEM',
            'to': self.cyclos.user_bdc_id,  # ID de l'utilisateur Bureau de change
        })

        self.cyclos.post(method='payment/perform', data=query_data)

        return Response(res, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        pass

    def destroy(self, request, pk):
        pass

