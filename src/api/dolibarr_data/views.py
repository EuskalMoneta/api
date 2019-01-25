import logging

from django import forms
from django.conf import settings
from django.core.validators import validate_email
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from dolibarr_api import DolibarrAPI, DolibarrAPIException
from dolibarr_data import serializers

log = logging.getLogger('console')


@api_view(['POST'])
@permission_classes((AllowAny, ))
def login(request):
    """
    User login from dolibarr
    """
    serializer = serializers.LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI()

        try:
            # validate (or not) the fact that our "username" variable is an email
            validate_email(request.data['username'])

            # we detected that our "username" variable is an email, we try to connect to dolibarr with it
            dolibarr_anonymous_token = dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                                                      password=settings.APPS_ANONYMOUS_PASSWORD)
            user_results = dolibarr.get(model='members', sqlfilters="email='{}'".format(request.data['username']),
                                        api_key=dolibarr_anonymous_token)
            user_data = [item
                         for item in user_results
                         if item['email'] == request.data['username']][0]
            if not user_data:
                raise AuthenticationFailed()

            login = user_data['login']

            token = dolibarr.login(login=user_data['login'], password=request.data['password'])
        except forms.ValidationError:
            # we detected that our "username" variable is NOT an email
            login = request.data['username']

            token = dolibarr.login(login=request.data['username'], password=request.data['password'])
    except (DolibarrAPIException, KeyError, IndexError):
        raise AuthenticationFailed()

    return Response({'auth_token': token, 'login': login})


@api_view(['GET'])
@permission_classes((AllowAny, ))
def verify_usergroup(request):
    """
    Verify that username is in a usergroup
    """
    serializer = serializers.VerifyUsergroupSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI(api_key=request.query_params['api_key'])
        try:
            # validate (or not) the fact that our "username" variable is an email
            validate_email(request.query_params['username'])

            user_results = dolibarr.get(model='members', sqlfilters="email='{}'".format(request.query_params['username']))
            user_data = [item
                         for item in user_results
                         if item['email'] == request.query_params['username']][0]
            if not user_data:
                return Response({'error': 'Unable to get user ID from your username!'},
                                status=status.HTTP_400_BAD_REQUEST)

            user_results = dolibarr.get(model='users', sqlfilters="login='{}'".format(user_data['login']))

            user_id = [item
                       for item in user_results
                       if item['email'] == request.query_params['username']][0]['id']
        except forms.ValidationError:
            user_results = dolibarr.get(model='users', sqlfilters="login='{}'".format(request.query_params['username']))

            user_id = [item
                       for item in user_results
                       if item['login'] == request.query_params['username']][0]['id']
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except (KeyError, IndexError):
        return Response({'error': 'Unable to get user ID from your username!'}, status=status.HTTP_400_BAD_REQUEST)

    usergroups_res = dolibarr.get(model='users/{}/groups'.format(user_id))
    usergroups_ids = [item['id']
                      for item in usergroups_res]
    try:
        group_constant_id = str(settings.DOLIBARR_CONSTANTS['groups'][request.query_params['usergroup']])
    except KeyError:
        return Response(status=status.HTTP_204_NO_CONTENT)

    if group_constant_id in usergroups_ids:
        return Response('OK')
    else:
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def get_usergroups(request):
    """
    Get usergroups for a username
    """
    serializer = serializers.GetUsergroupsSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        user_results = dolibarr.get(model='users', sqlfilters="login='{}'".format(request.query_params['username']))

        user_id = [item
                   for item in user_results
                   if item['login'] == request.query_params['username']][0]['id']
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except (KeyError, IndexError):
        return Response({'error': 'Unable to get user ID from your username!'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(dolibarr.get(model='users/{}/groups'.format(user_id)))


@api_view(['GET'])
def associations(request):
    """
    List all associations, and if you want, you can filter them.
    """
    dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    results = dolibarr.get(model='associations')
    approved = request.GET.get('approved', '')
    if approved:
        # We want to filter out the associations that doesn't have the required sponsorships
        filtered_results = [item
                            for item in results
                            if int(item['nb_parrains']) >= settings.MINIMUM_PARRAINAGES_3_POURCENTS]
        return Response(filtered_results)
    else:
        return Response(results)


@api_view(['GET'])
def towns_by_zipcode(request):
    """
    List all towns, filtered by a zipcode.
    """
    search = request.GET.get('zipcode', '')
    if not search:
        return Response({'error': 'Zipcode must not be empty'}, status=status.HTTP_400_BAD_REQUEST)

    dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    return Response(dolibarr.get(model='setup/dictionary/towns', zipcode=search))


@api_view(['GET'])
def countries(request):
    """
    Get the list of countries.
    """
    dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
    return Response(dolibarr.get(model='setup/dictionary/countries', lang='fr_FR'))


@api_view(['GET'])
def get_bdc_name(request):
    """
    Get the bdc name (lastname) for the current user.
    """
    return Response(request.user.profile.lastname)


@api_view(['GET'])
def get_username(request):
    """
    Get the username for the current user.
    """
    return Response(str(request.user))


@api_view(['GET'])
def get_member_name(request):
    """
    Get the member name (firstname + lastname or companyname) for the current user.
    """
    if request.user.profile.companyname:
        member_name = '{}'.format(request.user.profile.companyname)
    else:
        member_name = '{} {}'.format(request.user.profile.firstname, request.user.profile.lastname)
    return Response(member_name)


@api_view(['GET'])
def get_user_data(request):
    """
    Get user data for a user.
    """
    serializer = serializers.GetUserDataSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)  # log.critical(serializer.errors)

    try:
        username = serializer.data['username']
    except KeyError:
        username = str(request.user)

    try:
        dolibarr = DolibarrAPI(api_key=request.user.profile.dolibarr_token)
        user_results = dolibarr.get(model='users', sqlfilters="login='{}'".format(username))

        user_data = [item
                     for item in user_results
                     if item['login'] == username][0]
    except DolibarrAPIException:
        return Response({'error': 'Unable to connect to Dolibarr!'}, status=status.HTTP_400_BAD_REQUEST)
    except IndexError:
        return Response({'error': 'Unable to get user data from this user!'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(user_data)
