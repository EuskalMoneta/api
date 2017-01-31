import logging

# from django.conf import settings

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_pdf.renderer import PDFRenderer
from wkhtmltopdf import views as wkhtmltopdf_views

from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException
from dolibarr_data import serializers


log = logging.getLogger()


@api_view(['POST'])
@permission_classes((AllowAny, ))
def first_connection(request):
    """
    User login from dolibarr
    """
    serializer = serializers.FirstConnectionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI()
        # request.data['login']
        # request.data['email']
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except (KeyError, IndexError):
        return Response({'error': 'Unable to get user ID from your username!'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes((AllowAny, ))
def lost_password(request):
    """
    User login from dolibarr
    """
    serializer = serializers.LostPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI()
        # request.data['login']
        # request.data['email']
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except (KeyError, IndexError):
        return Response({'error': 'Unable to get user ID from your username!'}, status=status.HTTP_400_BAD_REQUEST)


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
    return Response(accounts_history_res)


@api_view(['GET'])
@renderer_classes((PDFRenderer, ))
def export_history_adherent_pdf(request):
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
