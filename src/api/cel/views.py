from base64 import b64encode
from datetime import date, datetime, timedelta
import logging
import mimetypes
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

                # On vérifie si cet adhérent a un compte numérique.
                cyclos = CyclosAPI(mode='login')
                cyclos_token = cyclos.login(
                    auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                               settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))
                data = cyclos.post(method='user/search',
                                   data={
                                       'keywords': request.data['login'],
                                       'groups': ['adherents_prestataires', 'adherents_prestataires_avec_paiement_smartphone', 'adherents_utilisateurs'],
                                       'userStatus': ['ACTIVE'],
                                   },
                                   token=cyclos_token)
                if data['result']['totalCount'] == 0:
                    return Response({'error': _("Cet adhérent ou cette adhérente n'a pas de compte eusko.")},
                                    status=status.HTTP_400_BAD_REQUEST)

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
                confirm_url = '{}/{}/valide-premiere-connexion?token={}'.format(
                    settings.CEL_PUBLIC_URL,
                    request.data['language'],
                    jwt_token.decode("utf-8"))

                # On active la langue choisie par l'utilisateur.
                activate(request.data['language'])

                # Translate subject & body for this email
                subject = _('Première connexion à votre compte en ligne Eusko')
                body = render_to_string('mails/first_connection.txt', {'token': confirm_url, 'user': member})

                sendmail_euskalmoneta(subject=subject, body=body, to_email=request.data['email'])
                return Response({'member': 'OK'})
            else:
                return Response({'error': _("Pas d'adhérent.e correspondant à ce numéro d'adhérent.e et cette adresse email.")},
                                status=status.HTTP_400_BAD_REQUEST)

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

        # 1) Créer la question/réponse de sécurité.
        create_security_qa(token_data['login'], serializer.data['question'], serializer.data['answer'])

        # 2) Dans Dolibarr, créer un utilisateur lié à l'adhérent.
        create_dolibarr_user_linked_to_member(dolibarr, token_data['login'])

        # 3) Dans Cyclos, initialiser le mot de passe de l'utilisateur.
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                       settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))
        cyclos_user_id = cyclos.get_member_id_from_login(member_login=token_data['login'], token=cyclos_token)
        change_cyclos_user_password(cyclos_token, cyclos_user_id, request.data['new_password'])

        return Response({'login': token_data['login']})

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
                confirm_url = '{}/{}/valide-passe-perdu?token={}'.format(
                    settings.CEL_PUBLIC_URL,
                    request.data['language'],
                    jwt_token.decode("utf-8"))

                # On active la langue choisie par l'utilisateur.
                activate(request.data['language'])

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

        # Dans Cyclos, reset le mot de passe de l'utilisateur
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                       settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))

        cyclos_user_id = cyclos.get_member_id_from_login(member_login=token_data['login'], token=cyclos_token)

        password_data = {
            'user': cyclos_user_id,  # ID de l'utilisateur
            'type': 'login',
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


def execute_virement(dolibarr, cyclos, virement):
    try:
        # On récupère le destinataire du virement à partir de son numéro de compte.
        try:
            data = cyclos.post(method='user/search', data={'keywords': virement['account']})
            destinataire_cyclos = data['result']['pageItems'][0]
            virement['name'] = destinataire_cyclos['display']
        except IndexError:
            virement['name'] = None
            raise Exception(_("Ce numéro de compte n'existe pas"))
        # On fait le paiement.
        query_data = {
            'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_inter_adherent']),
            'amount': virement['amount'],
            'currency': str(settings.CYCLOS_CONSTANTS['currencies']['eusko']),
            'from': cyclos.user_id,
            'to': destinataire_cyclos['id'],
            'description': virement['description'],
        }
        try:
            cyclos.post(method='payment/perform', data=query_data)
        except CyclosAPIException as err:
            if str(err).find('INSUFFICIENT_BALANCE') != -1:
                raise Exception(_("Solde insuffisant"))
            else:
                raise err
        # Le paiement dans Cyclos s'est exécuté sans erreur.
        # On récupère dans Dolibarr les informations sur le destinataire du virement, pour savoir s'il souhaite
        # recevoir une notification lorsqu'il reçoit un virement. Si c'est le cas, on lui envoie un email.
        destinataire_dolibarr = dolibarr.get(model='members',
                                             sqlfilters="login='{}'".format(destinataire_cyclos['shortDisplay']))[0]
        if destinataire_dolibarr['array_options']['options_notifications_virements']:
            # Activate user pre-selected language
            activate(destinataire_dolibarr['array_options']['options_langue'])
            # Translate subject & body for this email
            subject = _('Compte Eusko : virement reçu')
            body = render_to_string('mails/virement_recu.txt',
                                    {'user': destinataire_dolibarr,
                                     'emetteur': cyclos.user_profile['result']['display'],
                                     'montant': virement['amount']})
            sendmail_euskalmoneta(subject=subject, body=body, to_email=destinataire_dolibarr['email'])
        virement['status'] = 1
        virement['message'] = _("Virement effectué")
    except Exception as e:
        virement['status'] = 0
        virement['message'] = str(e)


@api_view(['POST'])
def execute_virements(request):
    """
    Exécute la liste des virements donnée en paramètre.
    """
    log.debug("execute_virements()")

    log.debug("request.data={}".format(request.data))
    serializer = serializers.ExecuteVirementSerializer(data=request.data, many=True)
    serializer.is_valid(raise_exception=True)
    log.debug("serializer.validated_data={}".format(serializer.validated_data))
    log.debug("serializer.errors={}".format(serializer.errors))
    virements = serializer.validated_data

    # Connexion à Dolibarr et Cyclos avec l'utilisateur courant.
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    for virement in virements:
        execute_virement(dolibarr, cyclos, virement)

    return Response(virements)


@api_view(['POST'])
def execute_virement_asso_mlc(request):
    """
    Exécute un virement à destination de l'association porteuse de la MLC.
    """
    serializer = serializers.ExecuteVirementAssoMlcSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    virement = serializer.validated_data

    # Connexion à Dolibarr et Cyclos avec l'utilisateur courant.
    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # Au lieu du numéro de compte, on donne le numéro d'adhérent du
    # destinataire du virement (l'association porteuse de la MLC, qui
    # par convention a le numéro d'adhérent Z00001).
    virement['account'] = 'Z00001'
    execute_virement(dolibarr, cyclos, virement)
    return Response(virement)


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
                                        str(settings.CYCLOS_CONSTANTS['groups']['adherents_prestataires_avec_paiement_smartphone']),
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
                if p['type']['internalName'] == 'pin'][0]
    return Response(pin_code['status'])


@api_view(['POST'])
def euskokart_update_pin(request):
    serializer = serializers.UpdatePinSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    # Connexion à Cyclos avec l'utilisateur courant pour avoir son identifiant.
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

    # Connexion à Cyclos avec l'utilisateur Anonyme pour modifier le code PIN de l'utilisateur courant.
    cyclos_anonyme = CyclosAPI(mode='login')
    cyclos_token_anonyme = cyclos_anonyme.login(
        auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                   settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))

    try:
        password_data = {
            'user': cyclos.user_id,
            'type': 'pin',
            'newPassword': serializer.validated_data['pin'],
            'confirmNewPassword': serializer.validated_data['pin']
        }
        cyclos_anonyme.post(method='password/change', data=password_data, token=cyclos_token_anonyme)
    except CyclosAPIException:
        return Response({'error': 'Unable to set your pin code!'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        member = dolibarr.get(model='members', sqlfilters="login='{}'".format(request.user))[0]

        # Activate user pre-selected language
        activate(member['array_options']['options_langue'])

        subject = _('Modification de votre code PIN')
        body = render_to_string('mails/euskokart_update_pin.txt', {'user': member})
        sendmail_euskalmoneta(subject=subject, body=body, to_email=member['email'])
    except DolibarrAPIException as e:
        return Response({'error': 'Unable to resolve user in dolibarr! error : {}'.format(e)},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': 'Unable to send mail! error : {}'.format(e)},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response(status=status.HTTP_200_OK)


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
    log.debug("execute_prelevements()")

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
            # On fait le paiement.
            query_data = {
                'type': str(settings.CYCLOS_CONSTANTS['payment_types']['virement_inter_adherent']),
                'amount': prelevement['amount'],
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
            prelevement['message'] = _("Prélèvement effectué")
        except Exception as e:
            prelevement['status'] = 0
            prelevement['message'] = str(e)

    return Response(prelevements)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def creer_compte_vee(request):
    """
    Crée un compte Vacances en eusko.
    """
    log.debug("creer_compte_vee()")

    log.debug("request.data={}".format(request.data))
    serializer = serializers.CreerCompteVeeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    log.debug("serializer.validated_data={}".format(serializer.validated_data))
    log.debug("serializer.errors={}".format(serializer.errors))

    lastname = serializer.validated_data['lastname']
    firstname = serializer.validated_data['firstname']

    try:
        # Connexion à Dolibarr et Cyclos avec l'utilisateur Anonyme.
        dolibarr = DolibarrAPI()
        dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                       password=settings.APPS_ANONYMOUS_PASSWORD)
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                       settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))
        # Générer un nouveau numéro d'adhérent.
        adherent = models.AdherentTouriste()
        adherent.save()
        num_adherent = 'T{:05d}'.format(adherent.id)
        log.debug("num_adherent={}".format(num_adherent))
        # Créer l'adhérent Dolibarr.
        dolibarr_member_rowid = create_dolibarr_member(
            dolibarr, num_adherent, '8', lastname, firstname, serializer.validated_data['email'],
            serializer.validated_data['address'], serializer.validated_data['zip'], serializer.validated_data['town'],
            serializer.validated_data['country_id'], serializer.validated_data['phone'],
            serializer.validated_data['birth'], compte_eusko=True)
        # Joindre la pièce d'identité à la fiche Adhérent dans Dolibarr.
        header, base64_encoded_data = serializer.validated_data['id_document'].split(",", 1)
        mime_type = header[len('data:'):-len(';base64')]
        # contournement du bug https://bugs.python.org/issue4963
        extension = mimetypes.guess_extension(mime_type).replace('.jpeg', '.jpg').replace('.jpe', '.jpg')
        add_attached_file_to_dolibarr_member(dolibarr, dolibarr_member_rowid,
                                             filename="{}-Pièce-d'identité{}".format(num_adherent, extension),
                                             filecontent=base64_encoded_data)
        # Joindre le rapport IDCheck à la fiche Adhérent dans Dolibarr.
        header, base64_encoded_data = serializer.validated_data['idcheck_report'].split(",", 1)
        mime_type = header[len('data:'):-len(';base64')]
        extension = mimetypes.guess_extension(mime_type)
        add_attached_file_to_dolibarr_member(dolibarr, dolibarr_member_rowid,
                                             filename="{}-Rapport-IDCheck{}".format(num_adherent, extension),
                                             filecontent=base64_encoded_data)
        # Créer l'utilisateur Dolibarr lié à cet adhérent.
        create_dolibarr_user_linked_to_member(dolibarr, num_adherent)
        # Créer l'utilisateur Cyclos.
        create_cyclos_user(cyclos_token, 'adherents_utilisateurs', '{} {}'.format(firstname, lastname), num_adherent,
                           serializer.validated_data['password'], serializer.validated_data['pin_code'])
        # Enregistrer la question/réponse de sécurité.
        create_security_qa(num_adherent, serializer.validated_data['question'], serializer.validated_data['answer'])
    except Exception as e:
        log.exception(e)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'login': num_adherent}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def creer_compte(request):
    """
    Crée un compte eusko.
    """
    log.debug("creer_compte()")

    log.debug("request.data={}".format(request.data))
    serializer = serializers.CreerCompteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    log.debug("serializer.validated_data={}".format(serializer.validated_data))
    log.debug("serializer.errors={}".format(serializer.errors))

    lastname = serializer.validated_data['lastname']
    firstname = serializer.validated_data['firstname']
    nouvel_adherent = 'login' not in serializer.validated_data

    try:
        # Connexion à Dolibarr et Cyclos avec l'utilisateur Anonyme.
        dolibarr = DolibarrAPI()
        dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                       password=settings.APPS_ANONYMOUS_PASSWORD)
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                       settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))
        if nouvel_adherent:
            # Générer un nouveau numéro d'adhérent.
            adherent = models.AdherentParticulier()
            adherent.save()
            num_adherent = 'E{:05d}'.format(adherent.id)
            log.debug("num_adherent={}".format(num_adherent))
            # Créer l'adhérent Dolibarr.
            dolibarr_member_rowid = create_dolibarr_member(
                dolibarr, num_adherent, '3', lastname, firstname, serializer.validated_data['email'],
                serializer.validated_data['address'], serializer.validated_data['zip'], serializer.validated_data['town'],
                serializer.validated_data['country_id'], serializer.validated_data['phone'],
                serializer.validated_data['birth'], compte_eusko=True, iban=serializer.validated_data['iban'],
                automatic_change_amount=serializer.validated_data['automatic_change_amount'],
                subscription_amount=serializer.validated_data['subscription_amount'],
                subscription_periodicity=serializer.validated_data['subscription_periodicity'],
                asso_id=serializer.validated_data['asso_id'],
                asso_saisie_libre=serializer.validated_data['asso_saisie_libre'])
        else:
            # Mettre à jour l'adhérent dans Dolibarr
            num_adherent = serializer.validated_data['login']
            data = serializer.validated_data
            data['recevoir_actus'] = True
            data['compte_eusko'] = True
            data['prelevement_auto_cotisation'] = False
            data['prelevement_auto_cotisation_eusko'] = True
            dolibarr_member_rowid = update_dolibarr_member(dolibarr, num_adherent, data)
        # Joindre la pièce d'identité à la fiche Adhérent dans Dolibarr.
        header, base64_encoded_data = serializer.validated_data['id_document'].split(",", 1)
        mime_type = header[len('data:'):-len(';base64')]
        # contournement du bug https://bugs.python.org/issue4963
        extension = mimetypes.guess_extension(mime_type).replace('.jpeg', '.jpg').replace('.jpe', '.jpg')
        add_attached_file_to_dolibarr_member(dolibarr, dolibarr_member_rowid,
                                             filename="{}-Pièce-d'identité{}".format(num_adherent, extension),
                                             filecontent=base64_encoded_data)
        # Joindre le rapport IDCheck à la fiche Adhérent dans Dolibarr.
        header, base64_encoded_data = serializer.validated_data['idcheck_report'].split(",", 1)
        mime_type = header[len('data:'):-len(';base64')]
        extension = mimetypes.guess_extension(mime_type)
        add_attached_file_to_dolibarr_member(dolibarr, dolibarr_member_rowid,
                                             filename="{}-Rapport-IDCheck{}".format(num_adherent, extension),
                                             filecontent=base64_encoded_data)
        # Joindre le mandat SEPA à la fiche Adhérent dans Dolibarr.
        add_attached_file_to_dolibarr_member(dolibarr, dolibarr_member_rowid,
                                             filename="{}-Mandat-SEPA.pdf".format(num_adherent),
                                             filecontent=serializer.validated_data['sepa_document'])
        # Créer l'utilisateur Dolibarr lié à cet adhérent.
        create_dolibarr_user_linked_to_member(dolibarr, num_adherent)
        # Créer l'utilisateur Cyclos.
        create_cyclos_user(cyclos_token, 'adherents_utilisateurs', '{} {}'.format(firstname, lastname), num_adherent,
                           serializer.validated_data['password'], serializer.validated_data['pin_code'])
        # Enregistrer la question/réponse de sécurité.
        create_security_qa(num_adherent, serializer.validated_data['question'], serializer.validated_data['answer'])
        # Envoi d'un mail de notification.
        dolibarr_member = dolibarr.get(model='members', sqlfilters="login='{}'".format(num_adherent))[0]
        activate('fr')
        texte = render_to_string('mails/ouverture_compte.txt',
                                 {'dolibarr_member': dolibarr_member}).strip('\n')
        sendmail_euskalmoneta(subject=texte, body=texte)
    except Exception as e:
        log.exception(e)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'login': num_adherent}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def adherer(request):
    """
    Enregistre une nouvelle adhésion.
    """
    log.debug("adherer()")

    log.debug("request.data={}".format(request.data))
    serializer = serializers.AdhererSerializer(data=request.data)
    serializer.is_valid(raise_exception=False)
    log.debug("serializer.validated_data={}".format(serializer.validated_data))
    log.debug("serializer.errors={}".format(serializer.errors))

    lastname = serializer.validated_data['lastname']
    firstname = serializer.validated_data['firstname']
    nouvel_adherent = 'login' not in serializer.validated_data

    try:
        # Connexion à Dolibarr et Cyclos avec l'utilisateur Anonyme.
        dolibarr = DolibarrAPI()
        dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                       password=settings.APPS_ANONYMOUS_PASSWORD)
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(settings.APPS_ANONYMOUS_LOGIN,
                                                       settings.APPS_ANONYMOUS_PASSWORD), 'utf-8')).decode('ascii'))
        if nouvel_adherent:
            # Générer un nouveau numéro d'adhérent.
            adherent = models.AdherentParticulier()
            adherent.save()
            num_adherent = 'E{:05d}'.format(adherent.id)
            log.debug("num_adherent={}".format(num_adherent))
            # Créer l'adhérent Dolibarr.
            dolibarr_member_rowid = create_dolibarr_member(
                dolibarr, num_adherent, '3', lastname, firstname, serializer.validated_data['email'],
                serializer.validated_data['address'], serializer.validated_data['zip'], serializer.validated_data['town'],
                serializer.validated_data['country_id'], serializer.validated_data['phone'],
                serializer.validated_data['birth'], compte_eusko=False, iban=serializer.validated_data['iban'],
                subscription_amount=serializer.validated_data['subscription_amount'],
                subscription_periodicity=serializer.validated_data['subscription_periodicity'],
                asso_id=serializer.validated_data['asso_id'],
                asso_saisie_libre=serializer.validated_data['asso_saisie_libre'])
        else:
            # Mettre à jour l'adhérent dans Dolibarr
            num_adherent = serializer.validated_data['login']
            data = serializer.validated_data
            data['recevoir_actus'] = True
            data['compte_eusko'] = False
            data['prelevement_auto_cotisation'] = True
            data['prelevement_auto_cotisation_eusko'] = False
            dolibarr_member_rowid = update_dolibarr_member(dolibarr, num_adherent, data)
        # Joindre le mandat SEPA à la fiche Adhérent dans Dolibarr.
        add_attached_file_to_dolibarr_member(dolibarr, dolibarr_member_rowid,
                                             filename="{}-Mandat-SEPA.pdf".format(num_adherent),
                                             filecontent=serializer.validated_data['sepa_document'])
        # Créer l'utilisateur Cyclos.
        create_cyclos_user(cyclos_token, 'adherents_sans_compte', '{} {}'.format(firstname, lastname), num_adherent)
        # Envoi d'un mail de notification.
        dolibarr_member = dolibarr.get(model='members', sqlfilters="login='{}'".format(num_adherent))[0]
        activate('fr')
        texte = render_to_string('mails/adhesion.txt',
                                 {'dolibarr_member': dolibarr_member}).strip('\n')
        sendmail_euskalmoneta(subject=texte, body=texte)
    except Exception as e:
        log.exception(e)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'login': num_adherent}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def enregistrer_mandat_cotisation(request):
    """
    Enregistre un mandat de prélèvement SEPA pour la cotisation.
    """
    log.debug("enregistrer_mandat_cotisation()")

    log.debug("request.data={}".format(request.data))
    serializer = serializers.EnregistrerMandatCotisationSerializer(data=request.data)
    serializer.is_valid(raise_exception=False)
    log.debug("serializer.validated_data={}".format(serializer.validated_data))
    log.debug("serializer.errors={}".format(serializer.errors))

    try:
        # Connexion à Dolibarr avec l'utilisateur Anonyme.
        dolibarr = DolibarrAPI()
        dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                       password=settings.APPS_ANONYMOUS_PASSWORD)
        # Mettre à jour l'adhérent dans Dolibarr
        num_adherent = serializer.validated_data['login']
        data = serializer.validated_data
        data['prelevement_auto_cotisation'] = True
        data['prelevement_auto_cotisation_eusko'] = False
        dolibarr_member_rowid = update_dolibarr_member(dolibarr, num_adherent, data)
        # Joindre le mandat SEPA à la fiche Adhérent dans Dolibarr.
        add_attached_file_to_dolibarr_member(dolibarr, dolibarr_member_rowid,
                                             filename="{}-Mandat-SEPA.pdf".format(num_adherent),
                                             filecontent=serializer.validated_data['sepa_document'])
        # Envoi d'un mail de notification.
        dolibarr_member = dolibarr.get(model='members', sqlfilters="login='{}'".format(num_adherent))[0]
        activate('fr')
        texte = render_to_string('mails/signature_mandat_cotisation.txt',
                                 {'dolibarr_member': dolibarr_member}).strip('\n')
        sendmail_euskalmoneta(subject=texte, body=texte)
    except Exception as e:
        log.exception(e)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(status=status.HTTP_200_OK)


def create_dolibarr_member(dolibarr, login, type, lastname, firstname, email, address, zip, town, country_id, phone,
                           birth, compte_eusko, iban=None, automatic_change_amount=None, subscription_amount=None,
                           subscription_periodicity=None, asso_id=None, asso_saisie_libre=None):
    """
    Crée un adhérent dans Dolibarr.
    :param dolibarr: connexion à Dolibarr (instance de DolibarrAPI)
    :param login: numéro d'adhérent
    :param type:
    :param lastname:
    :param firstname:
    :param email:
    :param address:
    :param zip:
    :param town:
    :param country_id:
    :param phone:
    :param birth:
    :param compte_eusko: indique si l'adhérent ouvre un compte eusko ou pas
    :param iban:
    :param automatic_change_amount:
    :param subscription_amount:
    :param subscription_periodicity:
    :param asso_id:
    :param asso_saisie_libre:
    :return: rowid de l'adhérent créé
    """
    dolibarr_member_rowid = dolibarr.post(model='members', data={
        'login': login,
        'typeid': type,
        'morphy': 'phy',
        'lastname': lastname,
        'firstname': firstname,
        'email': email,
        'address': address,
        'zip': zip,
        'town': town,
        'country_id': country_id,
        'phone_mobile': phone,
        'birth': datetime(birth.year, birth.month, birth.day).timestamp(),
        'public': '0',
        'statut': '1',
        'fk_asso': asso_id,
        'array_options': {
            'options_recevoir_actus': True,
            'options_accepte_cgu_eusko_numerique': compte_eusko,
            'options_documents_pour_ouverture_du_compte_valides': compte_eusko,
            'options_accord_pour_ouverture_de_compte': 'oui' if compte_eusko else None,
            'options_prelevement_change_montant': automatic_change_amount,
            'options_prelevement_change_periodicite': 1 if automatic_change_amount else None,
            'options_iban': iban,
            'options_prelevement_auto_cotisation': True if subscription_amount and not compte_eusko else None,
            'options_prelevement_auto_cotisation_eusko': True if subscription_amount and compte_eusko else None,
            'options_prelevement_cotisation_montant': subscription_amount,
            'options_prelevement_cotisation_periodicite': subscription_periodicity,
            'options_asso_saisie_libre': asso_saisie_libre,
            'options_notifications_validation_mandat_prelevement': compte_eusko,
            'options_notifications_refus_ou_annulation_mandat_prelevement': compte_eusko,
            'options_notifications_prelevements': compte_eusko,
            'options_notifications_virements': compte_eusko,
            'options_recevoir_bons_plans': compte_eusko,
        }
    })
    return dolibarr_member_rowid


def update_dolibarr_member(dolibarr, login, data):
    """
    Met à jour un adhérent dans Dolibarr.
    :param dolibarr: connexion à Dolibarr (instance de DolibarrAPI)
    :param login: numéro d'adhérent
    :return: rowid de l'adhérent mis à jour
    """
    member = dolibarr.get(model='members', sqlfilters="login='{}'".format(login))[0]
    dolibarr_member_rowid = member['id']
    dolibarr_data = {}
    for key in ('lastname', 'firstname', 'email', 'address', 'zip', 'town', 'country_id'):
        if key in data:
            dolibarr_data[key] = data[key]
    if 'phone' in data:
        dolibarr_data['phone_mobile'] = data['phone']
    if 'birth' in data:
        birth = data['birth']
        dolibarr_data['birth'] = datetime(birth.year, birth.month, birth.day).timestamp()
    if 'asso_id' in data:
        dolibarr_data['fk_asso'] = data['asso_id']
    # Dans le PUT il faut renvoyer tous les attributs supplémentaires
    # sinon leurs valeurs seront perdues (c'est le fonctionnement de
    # Dolibarr qui veut ça).
    array_options = member['array_options']
    if 'recevoir_actus' in data:
        array_options['options_recevoir_actus'] = data['recevoir_actus']
    if 'compte_eusko' in data:
        compte_eusko = data['compte_eusko']
        array_options['options_accepte_cgu_eusko_numerique'] = compte_eusko
        array_options['options_documents_pour_ouverture_du_compte_valides'] = compte_eusko
        array_options['options_accord_pour_ouverture_de_compte'] = 'oui' if compte_eusko else None
        array_options['options_notifications_validation_mandat_prelevement'] = compte_eusko
        array_options['options_notifications_refus_ou_annulation_mandat_prelevement'] = compte_eusko
        array_options['options_notifications_prelevements'] = compte_eusko
        array_options['options_notifications_virements'] = compte_eusko
        array_options['options_recevoir_bons_plans'] = compte_eusko
    if 'automatic_change_amount' in data:
        automatic_change_amount = data['automatic_change_amount']
        array_options['options_prelevement_change_montant'] = automatic_change_amount
        # S'il y a change automatique, il est toujours mensuel.
        array_options['options_prelevement_change_periodicite'] = 1 if automatic_change_amount else None
    if 'iban' in data:
        array_options['options_iban'] = data['iban']
    if 'prelevement_auto_cotisation' in data:
        array_options['options_prelevement_auto_cotisation'] = data['prelevement_auto_cotisation']
    if 'prelevement_auto_cotisation_eusko' in data:
        array_options['options_prelevement_auto_cotisation_eusko'] = data['prelevement_auto_cotisation_eusko']
    if 'subscription_amount' in data:
        array_options['options_prelevement_cotisation_montant'] = data['subscription_amount']
    if 'subscription_periodicity' in data:
        array_options['options_prelevement_cotisation_periodicite'] = data['subscription_periodicity']
    if 'asso_saisie_libre' in data:
        array_options['options_asso_saisie_libre'] = data['asso_saisie_libre']
    dolibarr_data['array_options'] = array_options

    dolibarr.put(model='members', id=dolibarr_member_rowid, data=dolibarr_data)
    return dolibarr_member_rowid


def add_attached_file_to_dolibarr_member(dolibarr, dolibarr_member_rowid, filename, filecontent):
    """
    Ajouter une pièce jointe à un adhérent dans Dolibarr.
    :param dolibarr: connexion à Dolibarr (instance de DolibarrAPI)
    :param dolibarr_member_rowid: rowid de l'adhérent
    :param filename: nom du fichier
    :param filecontent: contenu du fichier encodé en base64
    :return:
    """
    dolibarr.post(model='documents/upload', data={
        "filename": filename,
        "modulepart": "adherent",
        "ref": dolibarr_member_rowid,
        "subdir": "",
        "filecontent": filecontent,
        "fileencoding": "base64",
        "overwriteifexists": 0
    })


def create_cyclos_user(cyclos_token, group, name, login, password=None, pin_code=None):
    """
    Crée un utilisateur dans Cyclos.
    :param cyclos_token: token de connexion à Cyclos
    :param group:
    :param name:
    :param login: numéro d'adhérent
    :param password: mot de passe de l'utilisateur (optionnel)
    :param pin_code: code PIN de l'utilisateur (optionnel)
    :return: id de l'utilisateur créé
    """
    cyclos = CyclosAPI()
    # On vérifie si un utilisateur avec ce login existe. Si c'est le cas, on le met à jour, sinon on en crée un nouveau.
    data = {
        'keywords': login,
        'userStatus': ['ACTIVE', 'BLOCKED', 'DISABLED']
    }
    res = cyclos.post(method='user/search', data=data, token=cyclos_token)
    if res['result']['totalCount']==1 and res['result']['pageItems'][0]['shortDisplay'] == login:
        cyclos_user_id = res['result']['pageItems'][0]['id']
        res = cyclos.post(method='user/load', data=cyclos_user_id)
        # Si l'utilisateur existant est dans un groupe différent de celui voulu, on le change de groupe.
        if res['result']['group']['internalName'] != group:
            data = {
                'user': cyclos_user_id,
                'group': str(settings.CYCLOS_CONSTANTS['groups'][group]),
            }
            cyclos.post(method='userGroup/changeGroup', data=data)
    else:
        data = {
            'group': str(settings.CYCLOS_CONSTANTS['groups'][group]),
            'name': name,
            'username': login,
            'skipActivationEmail': True,
        }
        res = cyclos.post(method='user/register', data=data, token=cyclos_token)
        cyclos_user_id = res['result']['user']['id']
    # S'il s'agit d'un groupe dans lequel les utilisateurs ont un QR code, il faut générer celui-ci.
    if group in ('adherents_utilisateurs', 'adherents_prestataires', 'adherents_prestataires_avec_paiement_smartphone'):
        generate_qr_code_for_cyclos_user(cyclos_token, cyclos_user_id, login)
    # Si un mot de passe est fourni, cela signifie que cet utilisateur doit pouvoir se connecter donc il faut l'activer.
    if password:
        activate_cyclos_user(cyclos_token, cyclos_user_id)
        change_cyclos_user_password(cyclos_token, cyclos_user_id, password)
    if pin_code:
        change_cyclos_user_pincode(cyclos_token, cyclos_user_id, pin_code)
    return cyclos_user_id


def activate_cyclos_user(cyclos_token, cyclos_user_id):
    """
    Activer un utilisateur Cyclos.
    :param cyclos_token: token de connexion à Cyclos
    :param user_id: id de l'utilisateur Cyclos
    :return:
    """
    data = {
        'user': cyclos_user_id,
        'status': 'ACTIVE',
    }
    cyclos = CyclosAPI()
    cyclos.post(method='userStatus/changeStatus', data=data, token=cyclos_token)


def change_cyclos_user_password(cyclos_token, cyclos_user_id, password):
    """
    Change le mot de passe d'un utilisateur Cyclos.
    :param cyclos_token: token de connexion à Cyclos
    :param user_id: id de l'utilisateur Cyclos
    :param password: nouveau mot de passe de l'utilisateur
    :return:
    """
    data = {
        'user': cyclos_user_id,
        'type': 'login',
        'newPassword': password,
        'confirmNewPassword': password,
    }
    cyclos = CyclosAPI()
    cyclos.post(method='password/change', data=data, token=cyclos_token)


def change_cyclos_user_pincode(cyclos_token, cyclos_user_id, pin_code):
    """
    Change le code PIN d'un utilisateur Cyclos.
    :param cyclos_token: token de connexion à Cyclos
    :param user_id: id de l'utilisateur Cyclos
    :param pin_code: nouveau code PIN de l'utilisateur
    :return:
    """
    data = {
        'user': cyclos_user_id,
        'type': 'pin',
        'newPassword': pin_code,
        'confirmNewPassword': pin_code,
    }
    cyclos = CyclosAPI()
    cyclos.post(method='password/change', data=data, token=cyclos_token)


def generate_qr_code_for_cyclos_user(cyclos_token, cyclos_user_id, login):
    """
    Génère un QR code pour un utilisateur Cyclos et active ce QR code.
    :param cyclos_token: token de connexion à Cyclos
    :param user_id: id de l'utilisateur Cyclos
    :param login: numéro d'adhérent
    :return:
    """
    cyclos = CyclosAPI()
    data = {
        'type': 'qr_code',
        'user': cyclos_user_id,
        'value': login,
    }
    res = cyclos.post(method='token/save', data=data, token=cyclos_token)
    qr_code_id = res['result']
    cyclos.post(method='token/activatePending', data=[qr_code_id], token=cyclos_token)


def create_security_qa(login, question, answer):
    """
    Crée une question/réponse de sécurité pour le numéro d'adhérent donné.
    Si une question était déjà enregistrée pour cet adhérent, elle est mise à jour.
    :param login: numéro d'adhérent
    :param question:
    :param answer:
    :return:
    """
    sa, created = models.SecurityAnswer.objects.get_or_create(owner=login)
    sa.question=question
    sa.set_answer(raw_answer=answer)
    sa.save()


def create_dolibarr_user_linked_to_member(dolibarr, login):
    """
    Crée un utilisateur Dolibarr lié à l'adhérent donné en paramètre et ajoute cet utilisateur dans le groupe Adhérents.
    :param dolibarr:
    :param login: numéro d'adhérent
    :return:
    """
    member = dolibarr.get(model='members', sqlfilters="login='{}'".format(login))[0]
    dolibarr_user_id = dolibarr.post(model='users', data={
        'login': login,
        'admin': 0,
        'employee': 0,
        'lastname': member['lastname'],
        'firstname': member['firstname'],
        'fk_member': member['id'],
    })
    res = dolibarr.get(model='users/{}/setGroup/{}'.format(dolibarr_user_id,
                                                           settings.DOLIBARR_CONSTANTS['groups']['adherents']))
    if res != 1:
        raise Exception('Unable to set group.')
