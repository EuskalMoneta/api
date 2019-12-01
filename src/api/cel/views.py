from base64 import b64encode
from datetime import date, datetime, timedelta
import logging
from uuid import uuid4

import arrow
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import activate, gettext as _
from drf_pdf.renderer import PDFRenderer
import jwt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework_csv.renderers import CSVRenderer
from wkhtmltopdf import views as wkhtmltopdf_views

from cel import models, serializers
from cel.models import Mandat
from cel.mandat import get_current_user_account_number
from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException
from gestioninterne.views import _search_account_history
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

        try:
            dolibarr.get(model='users', sqlfilters="login='{}'".format(request.data['login']), api_key=dolibarr_token)
            return Response({'error': 'User already exist!'}, status=status.HTTP_201_CREATED)
        except DolibarrAPIException:
            pass

        if valid_login:
            # We want to search in members by login (N° Adhérent)
            response = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.data['login']), api_key=dolibarr_token)
            member = [item
                         for item in response
                         if item['login'] == request.data['login']][0]

            if member['email'] == request.data['email']:
                # We got a match!

                # On enregistre la langue choisie par l'adhérent.
                data = Member.validate_data({'options_langue': request.data['language']}, mode='update',
                                            base_options=member['array_options'])
                dolibarr.put(model='members/{}'.format(member['id']), data=data, api_key=dolibarr_token)

                # We need to mail a token etc...
                payload = {'login': request.data['login'],
                           'aud': 'guest', 'iss': 'first-connection',
                           'jti': str(uuid4()), 'iat': datetime.utcnow(),
                           'nbf': datetime.utcnow(), 'exp': datetime.utcnow() + timedelta(hours=1)}

                jwt_token = jwt.encode(payload, settings.JWT_SECRET)
                confirm_url = '{}/valide-premiere-connexion?token={}'.format(settings.CEL_PUBLIC_URL,
                                                                             jwt_token.decode("utf-8"))

                # Activate user pre-selected language
                activate(member['array_options']['options_langue'])

                # Translate subject & body for this email
                subject = _('Première connexion à votre compte en ligne Eusko')
                body = render_to_string('mails/first_connection.txt', {'token': confirm_url, 'user': member})

                sendmail_euskalmoneta(subject=subject, body=body, to_email=request.data['email'])
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
    serializer = serializers.ValidFirstConnectionSerializer(data=request.data)
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
        # We check if the user already exist, if he already exist we return a 400
        try:
            dolibarr.get(model='users', sqlfilters="login='{}'".format(token_data['login']), api_key=dolibarr_token)
            return Response({'error': 'User already exist!'}, status=status.HTTP_201_CREATED)
        except DolibarrAPIException:
            pass

        # 1) Créer une SecurityAnswer.
        res = models.SecurityAnswer.objects.create(owner=token_data['login'], question=serializer.data['question'])
        res.set_answer(raw_answer=serializer.data['answer'])
        res.save()

        if not res:
            Response({'error': 'Unable to save security answer!'}, status=status.HTTP_400_BAD_REQUEST)

        # 2) Dans Dolibarr, créer un utilisateur lié à l'adhérent
        member = dolibarr.get(model='members', sqlfilters="login='{}'".format(token_data['login']), api_key=dolibarr_token)[0]

        create_user_data = {
            'login': member['login'],
            'admin': 0,
            'employee': 0,
            'lastname': member['lastname'],
            'firstname': member['firstname'],
            'fk_member': member['id'],
        }
        user_id = dolibarr.post(model='users', data=create_user_data, api_key=dolibarr_token)

        # 3) Dans Dolibarr, ajouter ce nouvel utilisateur dans le groupe "Adhérents"
        user_group_model = 'users/{}/setGroup/{}'.format(user_id, settings.DOLIBARR_CONSTANTS['groups']['adherents'])
        user_group_res = dolibarr.get(model=user_group_model, api_key=dolibarr_token)
        if not user_group_res == 1:
            raise EuskalMonetaAPIException

        # 4) Dans Cyclos, activer l'utilisateur
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

        # 5) Dans Cyclos, initialiser le mot de passe d'un utilisateur
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
            response = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.data['login']), api_key=dolibarr_token)
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

                # Activate user pre-selected language
                activate(user_data['array_options']['options_langue'])

                # Translate subject & body for this email
                subject = _('Changement de mot de passe pour votre compte en ligne Eusko')
                body = render_to_string('mails/lost_password.txt', {'token': confirm_url, 'user': user_data})

                sendmail_euskalmoneta(subject=subject, body=body, to_email=request.data['email'])
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

    begin_date = serializer.data['begin'].replace(hour=0, minute=0, second=0).isoformat()
    end_date = serializer.data['end'].replace(hour=23, minute=59, second=59).isoformat()

    query_data = [cyclos.user_id, end_date]
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=query_data)

    search_history_data = {
        'orderBy': 'DATE_DESC',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
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

    # Quand on envoie une requête à Cyclos, une date signifie le jour indiqué à zéro heure donc pour avoir un
    # historique de date à date, il faut que end_date soit le lendemain de la date de fin souhaitée.
    begin_date = serializer.data['begin'].isoformat()
    end_date = (serializer.data['end'] + timedelta(days=1)).isoformat()

    # On récupère un résumé des comptes de l'utilisateur à la date
    # begin_date, ce qui nous permet d'avoir l'id du compte et son solde
    # à cette date (càd le solde initial pour l'historique).
    # On ne garde que le premier élément de la réponse car on sait qu'un
    # adhérent n'a qu'un compte.
    accounts_summary_query_data = [cyclos.user_id, begin_date]
    accounts_summary_res = cyclos.post(method='account/getAccountsSummary', data=accounts_summary_query_data)
    account_summary = accounts_summary_res['result'][0]
    initial_balance = account_summary['status']['balance']

    # On récupère l'historique du compte pour la période demandée, avec
    # les opérations triées par ordre chronologique.
    account_history_query_data = {
        'account': account_summary['status']['accountId'],
        'orderBy': 'DATE_ASC',
        'pageSize': 1000,  # maximum pageSize: 1000
        'currentPage': 0,
        'period':
        {
            'begin': begin_date,
            'end': end_date,
        },
    }
    account_history_res = cyclos.post(method='account/searchAccountHistory', data=account_history_query_data)
    account_history = account_history_res['result']['pageItems']

    # Pour chaque ligne de l'historique :
    # - on calcule le solde (en faisant le cumul avec les lignes précédentes)
    # - on met la date au format JJ/MM/AAAA (on n'affiche pas l'heure dans l'historique)
    # - on ajoute "Vers : xxx" ou "De : xxx" dans la description sauf lorsque l'autre compte est un compte système
    balance = initial_balance
    for line in account_history:
        balance = float(balance) + float(line['amount'])
        line['balance'] = balance
        line['date'] = arrow.get(line['date']).format('DD/MM/YYYY')
        if line['relatedAccount']['type']['nature'] != 'SYSTEM':
            line['description'] = "{}\r\n{} : {}".format(line['description'],
                                                         'Vers' if float(line['amount']) < 0 else 'De',
                                                         line['relatedAccount']['owner']['display'])

    # On ajoute une première ligne avec le solde initial du compte.
    account_history.insert(0, {
        'date': arrow.get(begin_date).format('DD/MM/YYYY'),
        'description': 'Solde initial',
        'amount': 0,
        'balance': initial_balance,
    })

    # On fabrique l'objet qui va servir à l'export PDF ou CSV.
    context = {
        'account_number': account_summary['number'],
        'name': account_summary['owner']['display'],
        'account_history': account_history,
        'account_login': str(request.user),
        'period': {
            'begin': arrow.get(serializer.data['begin']).format('DD MMMM YYYY', locale='fr'),
            'end': arrow.get(serializer.data['end']).format('DD MMMM YYYY', locale='fr'),
        },
    }

    if request.accepted_media_type == 'application/pdf':
        response = wkhtmltopdf_views.PDFTemplateResponse(
            request=request, context=context, template="summary/summary.html")
        pdf_content = response.rendered_content

        headers = {
            'Content-Disposition': 'filename="pdf_id.pdf"',
            'Content-Length': len(pdf_content),
        }

        return Response(pdf_content, headers=headers)
    elif request.accepted_media_type == 'text/csv':
        csv_content = [{'Date': line['date'],
                        'Libellé': line['description'],
                        'Crédit': "{0:.2f}".format(float(line['amount'])).replace('.', ',')
                                  if float(line['amount']) > float() else '',
                        'Débit': "{0:.2f}".format(float(line['amount'])).replace('.', ',')
                                  if float(line['amount']) < float() else '',
                        'Solde': "{0:.2f}".format(float(line['balance'])).replace('.', ',')}
                       for line in context['account_history']]
        return Response(csv_content)
    else:
        return Response(status=status.HTTP_406_NOT_ACCEPTABLE)


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
def has_account(request):

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')

        # Determine whether or not our user is an "utilisateur" or a "prestataire"
        group_constants_without_account = [str(settings.CYCLOS_CONSTANTS['groups']['adherents_sans_compte'])]

        group_constants_with_account = [str(settings.CYCLOS_CONSTANTS['groups']['adherents_prestataires']),
                                        str(settings.CYCLOS_CONSTANTS['groups']['adherents_utilisateurs'])]

        # Fetching info for our current user (we look for his groups)
        data = cyclos.post(method='user/load', data=[cyclos.user_id], token=request.user.profile.cyclos_token)

        # Determine whether or not our user is part of the appropriate group
        if data['result']['group']['id'] in group_constants_without_account:
            return Response({'status': False})
        elif data['result']['group']['id'] in group_constants_with_account:
            return Response({'status': True})
        else:
            raise PermissionDenied()
    except KeyError:
        raise PermissionDenied()


@api_view(['GET'])
def euskokart_list(request):
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [str(settings.CYCLOS_CONSTANTS['tokens']['carte_nfc']), cyclos.user_id]

    euskokart_data = cyclos.post(method='token/getListData', data=query_data)
    try:
        euskokart_res = [item for item in euskokart_data['result']['tokens']]
    except KeyError:
        return Response({'error': 'Unable to fetch euskokart data!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(euskokart_res)


@api_view(['GET'])
def euskokart_block(request):
    serializer = serializers.EuskokartLockSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [serializer.data['id']]

    euskokart_data = cyclos.post(method='token/block', data=query_data)
    return Response(euskokart_data)


@api_view(['GET'])
def euskokart_unblock(request):
    serializer = serializers.EuskokartLockSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    query_data = [serializer.data['id']]

    euskokart_data = cyclos.post(method='token/unblock', data=query_data)
    return Response(euskokart_data)


@api_view(['POST'])
def one_time_transfer(request):
    """
    Transfer d'eusko entre compte d'adhérent.
    """
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
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
        'from': cyclos.user_id,
        'to': serializer.data['beneficiaire'],
        'description': serializer.data['description'],
    }
    payment_res = cyclos.post(method='payment/perform', data=query_data)

    # Si on arrive jusqu'ici, c'est que le paiement dans Cyclos s'est exécuté sans erreur.
    # On récupère les infos de l'utilisateur Cyclos correspondant au bénéficiaire (pour connaître son numéro d'adhérent)
    # puis on charge les informations de cet adhérent dans Dolibarr, pour savoir s'il souhaite recevoir une notification
    # lorsqu'il reçoit un virement. Si c'est le cas, on lui envoie un email.
    data = cyclos.get(method='user/load', id=serializer.data['beneficiaire'])
    beneficiaire_cyclos = data['result']
    beneficiaire_dolibarr = dolibarr.get(model='members',
                                         sqlfilters="login='{}'".format(beneficiaire_cyclos['username']))[0]
    if beneficiaire_dolibarr['array_options']['options_notifications_virements']:
        # Activate user pre-selected language
        activate(beneficiaire_dolibarr['array_options']['options_langue'])
        # Translate subject & body for this email
        subject = _('Compte Eusko : virement reçu')
        body = render_to_string('mails/virement_recu.txt',
                                {'user': beneficiaire_dolibarr,
                                 'emetteur': cyclos.user_profile['result']['display'],
                                 'montant': serializer.data['amount']})
        sendmail_euskalmoneta(subject=subject, body=body, to_email=beneficiaire_dolibarr['email'])

    return Response(payment_res)


@api_view(['POST'])
def reconvert_eusko(request):
    """
    Transfer d'eusko entre compte de particulier.
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.ReconvertEuskoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # payment/perform
    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['reconversion_numerique']),
        'amount': serializer.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': cyclos.user_id,
        'to': 'SYSTEM',
        'description': serializer.data['description'],
    }

    return Response(cyclos.post(method='payment/perform', data=query_data))


@api_view(['GET'])
def user_rights(request):

    # Get useful data from Cyclos for this user
    try:
        res = {'username': str(request.user)}
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')

        # Determine whether or not our user is an "utilisateur" or a "prestataire"
        group_constants_without_account = [str(settings.CYCLOS_CONSTANTS['groups']['adherents_sans_compte'])]

        group_constants_with_account = [str(settings.CYCLOS_CONSTANTS['groups']['adherents_prestataires']),
                                        str(settings.CYCLOS_CONSTANTS['groups']['adherents_utilisateurs'])]

        # Fetching info for our current user (we look for his groups)
        user_data = cyclos.post(method='user/load', data=[cyclos.user_id], token=request.user.profile.cyclos_token)

        # Determine whether or not our user is part of the appropriate group
        if user_data['result']['group']['id'] in group_constants_without_account:
            res.update({'has_account_eusko_numerique': False})
        elif user_data['result']['group']['id'] in group_constants_with_account:
            res.update({'has_account_eusko_numerique': True})
        else:
            raise PermissionDenied()

        # Member Display name
        res.update({'display_name': user_data['result']['name']})
    except (CyclosAPIException, KeyError):
        raise PermissionDenied()

    # Get useful data from Dolibarr for this user
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        member_data = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.user))[0]

        # return Response(member_data)
        now = arrow.now('Europe/Paris')
        try:
            end_date_arrow = arrow.get(member_data['datefin']).to('Europe/Paris')
        except arrow.parser.ParserError:
            end_date_arrow = now

        res.update({
            'member_type': member_data['type'],
            'has_valid_membership': True if end_date_arrow > now else False,
            'lang':
            member_data['array_options']['options_langue'] if member_data['array_options']['options_langue'] else 'fr',
            'has_accepted_cgu':
            True if member_data['array_options']['options_accepte_cgu_eusko_numerique'] else False})
    except (DolibarrAPIException, KeyError):
        raise PermissionDenied()

    return Response(res)


@api_view(['GET'])
def euskokart_pin(request):
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)
    response = cyclos.post(method='password/getData', data=cyclos.user_id)
    pin_code = [p
                for p in response['result']['passwords']
                if p['type']['id'] == str(settings.CYCLOS_CONSTANTS['password_types']['pin'])][0]
    return Response(pin_code['status'])


@api_view(['POST'])
def euskokart_update_pin(request):
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = serializers.UpdatePinSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    query_data = {
        'user': cyclos.user_id,
        'type': str(settings.CYCLOS_CONSTANTS['password_types']['pin']),
        'newPassword': serializer.data['pin1'],
        'confirmNewPassword': serializer.data['pin2']
    }

    try:
        query_data.update({'oldPassword': serializer.data['ex_pin']})
        mode = 'modifiy'
    except KeyError:
        mode = 'add'

    try:
        cyclos.post(method='password/change', data=query_data)
    except CyclosAPIException:
        return Response({'error': 'Unable to set your pin code!'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        response = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.user))

        # Activate user pre-selected language
        activate(response[0]['array_options']['options_langue'])

        if mode == 'modifiy':
            subject = _('Modification du code secret de votre euskokart')
            response_data = {'status': 'Pin modified!'}
        elif mode == 'add':
            subject = _('Choix du code secret de votre euskokart')
            response_data = {'status': 'Pin added!'}

        body = render_to_string('mails/euskokart_update_pin.txt', {'mode': mode, 'user': response[0]})

        sendmail_euskalmoneta(subject=subject, body=body, to_email=response[0]['email'])
    except DolibarrAPIException as e:
        return Response({'error': 'Unable to resolve user in dolibarr! error : {}'.format(e)},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': 'Unable to send mail! error : {}'.format(e)},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response(response_data, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
def accept_cgu(request):
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        member_data = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.user))[0]

        data = {'array_options': member_data['array_options']}
        data['array_options'].update({'options_accepte_cgu_eusko_numerique': True})

        dolibarr.put(model='members/{}'.format(member_data['id']), data=data)
        return Response({'status': 'OK'})
    except (DolibarrAPIException, KeyError, IndexError):
        return Response({'error': 'Unable to update CGU field!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def refuse_cgu(request):
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        member_data = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.user))[0]

        data = {'array_options': member_data['array_options']}
        data['array_options'].update({'options_accepte_cgu_eusko_numerique': False})

        dolibarr.put(model='members/{}'.format(member_data['id']), data=data)

        # Activate user pre-selected language
        activate(member_data['array_options']['options_langue'])

        # Translate subject & body for this email
        subject = _('Refus des CGU')
        body = render_to_string('mails/refuse_cgu.txt', {'user': member_data})

        sendmail_euskalmoneta(subject=subject, body=body)

        return Response({'status': 'OK'})
    except (DolibarrAPIException, KeyError, IndexError):
        return Response({'error': 'Unable to update CGU field!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def members_cel_subscription(request):

    serializer = serializers.MembersSubscriptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        member = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.user))
    except DolibarrAPIException as e:
        return Response({'error': 'Unable to resolve user in dolibarr! error : {}'.format(e)},
                        status=status.HTTP_400_BAD_REQUEST)

    current_member = dolibarr.get(model='members', id=member[0]['id'])
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    if current_member['type'].lower() == 'particulier':
        member_name = '{} {}'.format(current_member['firstname'], current_member['lastname'])
    else:
        member_name = current_member['company']

    try:
        data = cyclos.post(method='user/search', data={'keywords': 'Z00001'})
        euskal_moneta_cyclos_id = data['result']['pageItems'][0]['id']
    except (KeyError, IndexError, CyclosAPIException) as e:
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    query_data = {
        'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_inter_adherent']),
        'amount': serializer.data['amount'],
        'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
        'from': cyclos.user_id,
        'to': euskal_moneta_cyclos_id,
        'description': 'Cotisation - {} - {}'.format(current_member['login'], member_name),
    }
    cyclos.post(method='payment/perform', data=query_data)

    # Register new subscription
    data_res_subscription = {'start_date': serializer.data['start_date'].strftime('%s'),
                             'end_date': serializer.data['end_date'].strftime('%s'),
                             'amount': serializer.data['amount'], 'label': serializer.data['label']}

    try:
        res_id_subscription = dolibarr.post(
            model='members/{}/subscriptions'.format(member[0]['id']), data=data_res_subscription)
    except Exception as e:
        log.critical("data_res_subscription: {}".format(data_res_subscription))
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    if str(res_id_subscription) == '-1':
        return Response({'data returned': str(res_id_subscription)}, status=status.HTTP_409_CONFLICT)
    # Register new payment
    payment_account = 4
    payment_type = 'VIR'
    data_res_payment = {'date': arrow.now('Europe/Paris').timestamp, 'type': payment_type,
                        'label': serializer.data['label'], 'amount': serializer.data['amount']}
    model_res_payment = 'bankaccounts/{}/lines'.format(payment_account)
    try:
        res_id_payment = dolibarr.post(
            model=model_res_payment, data=data_res_payment)

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
        res_id_link_sub_payment = dolibarr.put(
            model=model_link_sub_payment, data=data_link_sub_payment)

        log.info("res_id_link_sub_payment: {}".format(res_id_link_sub_payment))
    except DolibarrAPIException as e:
        log.critical("model: {}".format(model_link_sub_payment))
        log.critical("data_link_sub_payment: {}".format(data_link_sub_payment))
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Link this payment with the related-member
    data_link_payment_member = {'label': '{} {}'.format(member[0]['firstname'], member[0]['lastname']),
                                'type': 'member', 'url_id': member[0]['id'],
                                'url': '{}/adherents/card.php?rowid={}'.format(
                                    settings.DOLIBARR_PUBLIC_URL, member[0]['id'])}
    model_link_payment_member = 'bankaccounts/{}/lines/{}/links'.format(payment_account, res_id_payment)
    try:
        res_id_link_payment_member = dolibarr.post(
            model=model_link_payment_member, data=data_link_payment_member)

        log.info("res_id_link_payment_member: {}".format(res_id_link_payment_member))
    except DolibarrAPIException as e:
        log.critical("model: {}".format(model_link_payment_member))
        log.critical("data_link_payment_member: {}".format(data_link_payment_member))
        log.critical(e)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    res = {'id_subscription': res_id_subscription,
           'id_payment': res_id_payment,
           'link_sub_payment': res_id_link_sub_payment,
           'id_link_payment_member': res_id_link_payment_member,
           'member': current_member}

    return Response(res, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def montant_don(request):
    """
    Retourne le montant du don 3% généré par l'utilisateur depuis le 1er juillet dernier.
    """
    log.debug("montant_don()")
    # Connexion à Cyclos.
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # On récupère tous les crédits du compte de l'utilisateur qui ont été faits depuis le 1er juillet dernier et qui
    # sont du type "Change numérique en ligne - Versement des eusko" (changes par prélèvement automatique ou virement)
    # et "Crédit du compte" (chargements de compte en BDC).
    accounts_summary_data = cyclos.post(method='account/getAccountsSummary', data=[cyclos.user_id, None])
    current_user_account = accounts_summary_data['result'][0]
    log.debug("current_user_account={}".format(current_user_account))
    today = date.today()
    begin_date = datetime(today.year if today.month >= 7 else today.year-1, 7, 1).isoformat()
    end_date = datetime.now().replace(microsecond=0).isoformat()
    log.debug("begin_date={}".format(begin_date))
    log.debug("end_date={}".format(end_date))
    payments = _search_account_history(
        cyclos=cyclos,
        account=current_user_account['id'],
        direction='CREDIT',
        begin_date=begin_date,
        end_date=end_date,
        payment_types=[
            str(settings.CYCLOS_CONSTANTS['payment_types']['change_numerique_en_ligne_versement_des_eusko']),
            str(settings.CYCLOS_CONSTANTS['payment_types']['credit_du_compte']),
        ]
    )

    montant_don = sum([float(payment['amount']) for payment in payments]) * 0.03

    response_data = {'montant_don': montant_don}
    log.debug("response_data = %s", response_data)
    return Response(response_data)


@api_view(['POST'])
def execute_prelevements(request):
    """
    Exécute la liste des prélèvements donnée en paramètre.
    """
    log.debug("prelevements()")

    log.debug("request.data={}".format(request.data))
    serializer = serializers.ExecutePrelevementSerializer(data=request.data, many=True)
    serializer.is_valid(raise_exception=True)
    log.debug("serializer.validated_data={}".format(serializer.validated_data))
    log.debug("serializer.errors={}".format(serializer.errors))
    prelevements = serializer.validated_data

    # Connexion à Cyclos avec l'utilisateur courant, pour faire les recherches d'utilisateur par numéro de compte.
    cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')

    # On récupère l'utilisateur créditeur à partir de son numéro de compte.
    numero_compte_crediteur = get_current_user_account_number(request)
    data = cyclos.post(method='user/search', data={'keywords': numero_compte_crediteur})
    crediteur = data['result']['pageItems'][0]

    # Connexion à Cyclos avec l'utilisateur Anonyme, pour exécuter les prélèvements.
    cyclos_anonyme = CyclosAPI(mode='login')
    cyclos_token_anonyme = cyclos_anonyme.login(
        auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                   settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))

    # Pour chaque prélèvement à faire, on recherche le mandat correspondant et on vérifie s'il est valide.
    # Si c'est le cas, on fait le prélèvement (le paiement est fait par l'utilisateur Anonyme).
    for prelevement in prelevements:
        try:
            # On récupère le débiteur à partir de son numéro de compte.
            try:
                data = cyclos.post(method='user/search', data={'keywords': prelevement['account']})
                debiteur = data['result']['pageItems'][0]
                prelevement['name'] = debiteur['display']
            except IndexError:
                prelevement['name'] = None
                raise Exception(_("Ce numéro de compte n'existe pas"))
            try:
                mandat = Mandat.objects.get(numero_compte_crediteur=numero_compte_crediteur,
                                            numero_compte_debiteur=prelevement['account'])
            except Mandat.DoesNotExist:
                raise Exception(_("Pas d'autorisation de prélèvement"))
            if mandat.statut == Mandat.EN_ATTENTE:
                raise Exception(_("Pas d'autorisation de prélèvement (autorisation en attente de validation)"))
            elif mandat.statut == Mandat.REFUSE:
                raise Exception(_("Pas d'autorisation de prélèvement (autorisation refusée)"))
            elif mandat.statut == Mandat.REVOQUE:
                raise Exception(_("Pas d'autorisation de prélèvement (autorisation révoquée)"))
            # On fait le paiement (on accepte les montants écrits avec un point ou une virgule).
            query_data = {
                'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_inter_adherent']),
                'amount': float(prelevement['amount'].replace(',', '.')),
                'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
                'from': debiteur['id'],
                'to': crediteur['id'],
                'description': prelevement['description'],
            }
            try:
                cyclos_anonyme.post(method='payment/perform', data=query_data, token=cyclos_token_anonyme)
            except CyclosAPIException as err:
                if str(err).find('INSUFFICIENT_BALANCE') != -1:
                    raise Exception(_("Solde insuffisant"))
                else:
                    raise err
            prelevement['status'] = 1
            prelevement['description'] = _("Prélèvement effectué")
        except Exception as e:
            prelevement['status'] = 0
            prelevement['description'] = str(e)

    return Response(prelevements)
