import base64
from datetime import datetime, timedelta
import logging
from uuid import uuid4

from django.conf import settings
from drf_pdf.renderer import PDFRenderer
import jwt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from wkhtmltopdf import views as wkhtmltopdf_views

from cel import serializers
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

            if response[0]['email'] == request.data['email']:
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
                return Response(status=status.HTTP_204_NO_CONTENT)

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
    # new_password
    # confirm_password

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

        user_data = {'fk_member': member[0]['id'], 'statut': '1', 'public': '0', 'employee': '0',
                     'email': member[0]['email'], 'login': member[0]['login'],
                     'firstname': member[0]['firstname'], 'lastname': member[0]['lastname']}
        user_obj = dolibarr.post(model='users', data=user_data, api_key=dolibarr_token)

        # 2) Dans Dolibarr, ajouter ce nouvel utilisateur dans le groupe "Adhérents"
        # TODO: Comment retrouver l'id du group "Adhérents" ?
        user_group_model = 'users/{}/setGroup/{}'.format(user_obj['id'],
                                                         settings.DOLIBARR_CONSTANTS['groups']['adherents'])
        user_group_res = dolibarr.get(model=user_group_model, api_key=dolibarr_token)
        if not user_group_res == 1:
            raise EuskalMonetaAPIException

        # 3) Dans Cyclos, activer l'utilisateur
        # TODO
        cyclos_auth_string = b'{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN, settings.APPS_ANONYMOUS_PASSWORD)
        cyclos_auth_string = base64.standard_b64encode(cyclos_auth_string).decode('utf-8')

        cyclos = CyclosAPI(auth_string=cyclos_auth_string, mode='cel')

        active_user_data = {}
        # cyclos.post(method='user/active', data=active_user_data)

        # 4) Dans Cyclos, initialiser le mot de passe d'un utilisateur
        password_data = {
            'user': cyclos.user_id,  # ID de l'utilisateur
            'type': str(settings.CYCLOS_CONSTANTS['password_types']['login_password']),
            'newPassword': request.data['new_password'],  # saisi par l'utilisateur
            'confirmNewPassword': request.data['confirm_password'],  # saisi par l'utilisateur
        }
        cyclos.post(method='password/change', data=password_data)

        return Response()

    except (EuskalMonetaAPIException, DolibarrAPIException, CyclosAPIException, KeyError, IndexError):
        return Response({'error': 'Unable to get user data for this login!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def lost_password(request):
    """
    User login from dolibarr
    """
    serializer = serializers.LostPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        pass
        # dolibarr = DolibarrAPI()
        # request.data['login']
        # request.data['email']
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except (KeyError, IndexError):
        return Response({'error': 'Unable to get user ID from your username!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def validate_lost_password(request):
    """
    validate_lost_password
    """
    serializer = serializers.ValidTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        token_data = jwt.decode(request.data['token'], settings.JWT_SECRET,
                                issuer='lost-password', audience='member')
    except jwt.InvalidTokenError:
        return Response({'error': 'Unable to read token!'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(token_data)


@api_view(['GET'])
def account_summary_for_adherents(request):

    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='cel')
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
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    begin_date = datetime.strptime(request.query_params['begin'], '%Y-%m-%d')
    end_date = datetime.strptime(
        request.query_params['end'], '%Y-%m-%d').replace(hour=23, minute=59, second=59)

    query_data = [cyclos.user_id, end_date.isoformat()]
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    search_history_data = {
        'account': accounts_summaries_data['result'][0]['status']['accountId'],
        'orderBy': 'DATE_DESC',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentpage': 0,
        'period':
        {
            'begin': begin_date.isoformat(),
            'end': end_date.isoformat(),
        },
    }

    accounts_history_res = cyclos.post(method='account/searchAccountHistory', data=search_history_data)
    return Response([accounts_history_res, accounts_summaries_data['result'][0]['status']['balance']])


@api_view(['GET'])
@renderer_classes((PDFRenderer, ))
def export_history_adherent_pdf(request):

    serializer = serializers.HistorySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    try:
        cyclos = CyclosAPI(auth_string=request.user.profile.cyclos_auth_string, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [cyclos.user_id, None]

    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)
    begin_date = request.query_params['begin']
    end_date = request.query_params['end']

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
    }
    accounts_history_res = cyclos.post(method='account/searchAccountHistory', data=search_history_data)
    context = {
        'account_history': accounts_history_res['result'],
    }

    response = wkhtmltopdf_views.PDFTemplateResponse(request=request, context=context, template="summary/summary.html")
    pdf_content = response.rendered_content

    headers = {
        'Content-Disposition': 'filename="pdf_id.pdf"',
        'Content-Length': len(pdf_content),
    }

    return Response(pdf_content, headers=headers)
