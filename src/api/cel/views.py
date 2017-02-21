from base64 import b64encode
from datetime import datetime, timedelta
import logging
from uuid import uuid4

import arrow
from django.conf import settings
from drf_pdf.renderer import PDFRenderer
import jwt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_csv.renderers import CSVRenderer
from wkhtmltopdf import views as wkhtmltopdf_views

from cel import models, serializers
from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException
from members.misc import Member
from misc import EuskalMonetaAPIException, sendmail_euskalmoneta

log = logging.getLogger()


@api_view(['POST'])
@permission_classes((AllowAny, ))
def first_connection(request):
    """
    First connection
    """
    serializer = serializers.FirstConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI()
        dolibarr_token = dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                                        password=settings.APPS_ANONYMOUS_PASSWORD)

        valid_login = Member.validate_num_adherent(request.data['login'])

        if valid_login:
            # We want to search in members by login (N° Adhérent)
            response = dolibarr.get(model='members', login=request.data['login'], api_key=dolibarr_token)
            user_data = [item
                         for item in response
                         if item['login'] == request.data['login']][0]

            if user_data['email'] == request.data['email']:
                # We got a match!

                # We need to mail a token etc...
                payload = {'login': request.data['login'],
                           'aud': 'guest', 'iss': 'first-connection',
                           'jti': str(uuid4()), 'iat': datetime.utcnow(),
                           'nbf': datetime.utcnow(), 'exp': datetime.utcnow() + timedelta(hours=1)}

                jwt_token = jwt.encode(payload, settings.JWT_SECRET)
                confirm_url = '{}/valide-premiere-connexion?token={}'.format(settings.CEL_PUBLIC_URL,
                                                                             jwt_token.decode("utf-8"))

                sendmail_euskalmoneta(subject="subject", body="body blabla, token: {}".format(confirm_url),
                                      to_email=request.data['email'])
                return Response({'member': 'OK'})
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({'error': 'You need to provide a *VALID* login parameter! (Format: E12345)'},
                            status=status.HTTP_400_BAD_REQUEST)

    except (DolibarrAPIException, KeyError, IndexError):
        return Response({'error': 'Unable to get user data for this login!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def validate_first_connection(request):
    """
    validate_first_connection
    """
    serializer = serializers.ValidTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        token_data = jwt.decode(request.data['token'], settings.JWT_SECRET,
                                issuer='first-connection', audience='guest')
    except jwt.InvalidTokenError:
        return Response({'error': 'Unable to read token!'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        dolibarr = DolibarrAPI()
        dolibarr_token = dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                                        password=settings.APPS_ANONYMOUS_PASSWORD)

        # 1) Dans Dolibarr, créer un utilisateur lié à l'adhérent
        member = dolibarr.get(model='members', login=token_data['login'], api_key=dolibarr_token)

        create_user = 'members/{}/createUser'.format(member[0]['id'])
        create_user_data = {'login': token_data['login']}

        # user_id will be the ID for this new user
        user_id = dolibarr.post(model=create_user, data=create_user_data, api_key=dolibarr_token)

        # 2) Dans Dolibarr, ajouter ce nouvel utilisateur dans le groupe "Adhérents"
        user_group_model = 'users/{}/setGroup/{}'.format(user_id, settings.DOLIBARR_CONSTANTS['groups']['adherents'])
        user_group_res = dolibarr.get(model=user_group_model, api_key=dolibarr_token)
        if not user_group_res == 1:
            raise EuskalMonetaAPIException

        # 3) Dans Cyclos, activer l'utilisateur
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                       settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))

        cyclos_user_id = cyclos.get_member_id_from_login(member_login=token_data['login'], token=cyclos_token)

        active_user_data = {
            'user': cyclos_user_id,  # ID de l'utilisateur
            'status': 'ACTIVE'
        }
        cyclos.post(method='userStatus/changeStatus', data=active_user_data, token=cyclos_token)

        # 4) Dans Cyclos, initialiser le mot de passe d'un utilisateur
        password_data = {
            'user': cyclos_user_id,  # ID de l'utilisateur
            'type': str(settings.CYCLOS_CONSTANTS['password_types']['login_password']),
            'newPassword': request.data['new_password'],  # saisi par l'utilisateur
            'confirmNewPassword': request.data['confirm_password'],  # saisi par l'utilisateur
        }
        cyclos.post(method='password/change', data=password_data, token=cyclos_token)

        return Response({'status': 'success'})

    except (EuskalMonetaAPIException, DolibarrAPIException, CyclosAPIException, KeyError, IndexError):
        return Response({'error': 'Unable to get user data for this login!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def lost_password(request):
    """
    Lost password function for Compte en Ligne members
    """
    serializer = serializers.LostPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI()
        dolibarr_token = dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                                        password=settings.APPS_ANONYMOUS_PASSWORD)

        valid_login = Member.validate_num_adherent(request.data['login'])

        if valid_login:
            # We want to search in members by login (N° Adhérent)
            response = dolibarr.get(model='members', login=request.data['login'], api_key=dolibarr_token)
            user_data = [item
                         for item in response
                         if item['login'] == request.data['login']][0]

            if user_data['email'] == request.data['email']:
                # We got a match!

                # We need to mail a token etc...
                payload = {'login': request.data['login'],
                           'aud': 'guest', 'iss': 'lost-password',
                           'jti': str(uuid4()), 'iat': datetime.utcnow(),
                           'nbf': datetime.utcnow(), 'exp': datetime.utcnow() + timedelta(hours=1)}

                jwt_token = jwt.encode(payload, settings.JWT_SECRET)
                confirm_url = '{}/valide-passe-perdu?token={}'.format(settings.CEL_PUBLIC_URL,
                                                                      jwt_token.decode("utf-8"))

                sendmail_euskalmoneta(subject="subject", body="body blabla, token: {}".format(confirm_url),
                                      to_email=request.data['email'])
                return Response({'member': 'OK'})
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({'error': 'You need to provide a *VALID* login parameter! (Format: E12345)'},
                            status=status.HTTP_400_BAD_REQUEST)

    except (DolibarrAPIException, KeyError, IndexError):
        return Response({'error': 'Unable to get user data for this login!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def validate_lost_password(request):
    """
    validate_lost_password
    """
    serializer = serializers.ValidLostPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        token_data = jwt.decode(request.data['token'], settings.JWT_SECRET,
                                issuer='lost-password', audience='guest')
    except jwt.InvalidTokenError:
        return Response({'error': 'Unable to read token!'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Check SecurityQA with custom methods in models.SecurityAnswer
        answer = models.SecurityAnswer.objects.get(owner=token_data['login'])
        if not answer.check_answer(serializer.data['answer']):
            return Response({'status': 'NOK'}, status=status.HTTP_400_BAD_REQUEST)

        # Dans Cyclos, activer l'utilisateur (au cas où il soit à l'état bloqué)
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                       settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))

        cyclos_user_id = cyclos.get_member_id_from_login(member_login=token_data['login'], token=cyclos_token)

        active_user_data = {
            'user': cyclos_user_id,  # ID de l'utilisateur
            'status': 'ACTIVE'
        }
        cyclos.post(method='userStatus/changeStatus', data=active_user_data, token=cyclos_token)

        # Dans Cyclos, reset le mot de passe d'un utilisateur
        password_data = {
            'user': cyclos_user_id,  # ID de l'utilisateur
            'type': str(settings.CYCLOS_CONSTANTS['password_types']['login_password']),
            'newPassword': serializer.data['new_password'],  # saisi par l'utilisateur
            'confirmNewPassword': serializer.data['confirm_password'],  # saisi par l'utilisateur
        }
        cyclos.post(method='password/change', data=password_data, token=cyclos_token)

        return Response({'status': 'success'})

    except (EuskalMonetaAPIException, CyclosAPIException, KeyError, IndexError):
        return Response({'error': 'Unable to get user data for this login!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def account_summary_for_adherents(request):

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [cyclos.user_id, None]

    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)
    return Response(accounts_summaries_data)


@api_view(['GET'])
def payments_available_for_adherents(request):

    serializer = serializers.HistorySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    begin_date = serializer.data['begin'].isoformat()
    end_date = serializer.data['end'].replace(hour=23, minute=59, second=59).isoformat()

    query_data = [cyclos.user_id, end_date]
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    search_history_data = {
        'orderBy': 'DATE_DESC',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
        'period':
        {
            'begin': begin_date,
            'end': end_date,
        },
    }
    try:
        search_history_data.update({'account': request.query_params['account']})
    except KeyError:
        search_history_data.update({'account': accounts_summaries_data['result'][0]['status']['accountId']})
    try:
        search_history_data.update({'description': request.query_params['description']})
    except KeyError:
        pass

    accounts_history_res = cyclos.post(method='account/searchAccountHistory', data=search_history_data)
    return Response([accounts_history_res, accounts_summaries_data['result'][0]['status']['balance']])


class ExportHistoryCSVRenderer(CSVRenderer):
    header = ['Date', 'Libellé', 'Débit', 'Crédit', 'Solde']


@api_view(['GET'])
@renderer_classes((PDFRenderer, ExportHistoryCSVRenderer))
def export_history_adherent(request):

    serializer = serializers.ExportHistorySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [cyclos.user_id, None]
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    begin_date = serializer.data['begin'].isoformat()
    end_date = serializer.data['end'].replace(hour=23, minute=59, second=59).isoformat()

    search_history_data_with_balance = {
        'account': accounts_summaries_data['result'][0]['status']['accountId'],
        'orderBy': 'DATE_DESC',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
        'period':
        {
            'begin': begin_date,
            'end': end_date,
        },
    }
    accounts_history_res_with_balance = cyclos.post(
        method='account/searchAccountHistory', data=search_history_data_with_balance)

    balance = accounts_summaries_data['result'][0]['status']['balance']
    for line in accounts_history_res_with_balance['result']['pageItems']:
        line['balance'] = balance
        balance = float(balance) - float(line['amount'])

    search_history_data = {
        'account': accounts_summaries_data['result'][0]['status']['accountId'],
        'orderBy': 'DATE_DESC',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
        'period':
        {
            'begin': begin_date,
            'end': end_date,
        },
        'description': request.query_params['description']
    }
    accounts_history_res = cyclos.post(method='account/searchAccountHistory', data=search_history_data)

    for line_without_balance in accounts_history_res['result']['pageItems']:
        for line_with_balance in accounts_history_res_with_balance['result']['pageItems']:
            if line_without_balance['id'] == line_with_balance['id']:
                line_without_balance['balance'] = line_with_balance['balance']

    for line in accounts_history_res['result']['pageItems']:
        line['date'] = arrow.get(line['date']).format('Le YYYY-MM-DD à HH:mm')

    context = {
        'account_history': accounts_history_res['result'],
        'period': {
            'begin': serializer.data['begin'].replace(hour=0, minute=0, second=0),
            'end': serializer.data['end'].replace(hour=23, minute=59, second=59),
        },
    }
    if request.query_params['mode'] == 'pdf':
        response = wkhtmltopdf_views.PDFTemplateResponse(
            request=request, context=context, template="summary/summary.html")
        pdf_content = response.rendered_content

        headers = {
            'Content-Disposition': 'filename="pdf_id.pdf"',
            'Content-Length': len(pdf_content),
        }

        return Response(pdf_content, headers=headers)
    else:
        csv_content = [{'Date': line['date'],
                        'Libellé': line['description'],
                        'Crédit': line['amount'],
                        'Débit': '',
                        'Solde': line['balance']}
                       if float(line['amount']) > float()
                       else
                       {'Date': line['date'],
                        'Libellé': line['description'],
                        'Crédit': '',
                        'Débit': line['amount'],
                        'Solde': line['balance']}
                       for line in context['account_history']['pageItems']]
        return Response(csv_content)


@api_view(['GET'])
@renderer_classes((PDFRenderer, ))
def export_rie_adherent(request):
    serializer = serializers.ExportRIESerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)
    query_data = [cyclos.user_id, None]
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    for account in (accounts_summaries_data['result']):
        if account['number'] == request.query_params['account']:
            # add loop to context to display rie 6 times
            context = {'account': account, 'loop': range(0, 3)}
            response = wkhtmltopdf_views.PDFTemplateResponse(
                request=request, context=context, template="summary/rie.html")
            pdf_content = response.rendered_content

            headers = {
                'Content-Disposition': 'filename="pdf_id.pdf"',
                'Content-Length': len(pdf_content),
            }

            return Response(pdf_content, headers=headers)


@api_view(['GET'])
def check_account(request):

    res = False
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')

        # Determine whether or not our user is an "utilisateur" or a "prestataire"
        if request.user.profile.companyname:
            group_constant = str(settings.CYCLOS_CONSTANTS['groups']['adherents_prestataires'])
        else:
            group_constant = str(settings.CYCLOS_CONSTANTS['groups']['adherents_utilisateurs'])

        # Fetching info for our current user (we look for his groups)
        data = cyclos.post(method='user/load', data=[cyclos.user_id], token=request.user.profile.cyclos_token)

        # Determine whether or not our user is part of the appropriate group
        res = True if data['result']['group']['id'] == group_constant else False
    except KeyError:
        pass

    return Response({'status': res})


@api_view(['GET'])
def euskokart_list(request):

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [str(settings.CYCLOS_CONSTANTS['tokens']['carte_nfc']), cyclos.user_id]

    euskokart_data = cyclos.post(method='token/getListData', data=query_data)
    return Response(euskokart_data)


@api_view(['GET'])
def euskokart_block(request):

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [request.query_params['id']]

    euskokart_data = cyclos.post(method='token/block', data=query_data)
    return Response(euskokart_data)


@api_view(['GET'])
def euskokart_unblock(request):

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [request.query_params['id']]

    euskokart_data = cyclos.post(method='token/unblock', data=query_data)
    return Response(euskokart_data)


@api_view(['POST'])
def one_time_transfer(request):
    """
    Transfer d'eusko entre compte de particulier.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.OneTimeTransferSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # payment/perform
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_inter_adherent']),
        'amount': serializer.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': serializer.data['debit'],
        'to': serializer.data['beneficiaire'],
        'description': serializer.data['description'],
    }

    return Response(cyclos.post(method='payment/perform', data=query_data))
