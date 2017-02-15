from base64 import b64encode
import logging

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import validate_email
from rest_framework.exceptions import AuthenticationFailed

from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException


log = logging.getLogger(__name__)


def authenticate(username, password):
    user = None

    # TODO faire une fonction get_username_from_username_or_email() ?
    # il me semble que ça rendrait le code plus lisible et compréhensible
    try:
        dolibarr = DolibarrAPI()

        try:
            # validate (or not) the fact that our "username" variable is an email
            validate_email(username)

            # we detected that our "username" variable is an email,
            # we try to find the user that has this email (there must be exactly one)
            dolibarr_anonymous_token = dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                                                      password=settings.APPS_ANONYMOUS_PASSWORD,
                                                      reset=True)
            user_results = dolibarr.get(model='users', email=username, api_key=dolibarr_anonymous_token)
            matching_users = [item
                              for item in user_results
                              if item['email'] == username]
            if not matching_users or len(matching_users) > 1:
                raise AuthenticationFailed()

            username = matching_users[0]['login']

        except forms.ValidationError:
            # we detected that our "username" variable is NOT an email
            # so it's really a username
            pass

        dolibarr_token = dolibarr.login(login=username, password=password, reset=True)

    except (DolibarrAPIException, KeyError, IndexError):
        raise AuthenticationFailed()

    try:
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(username, password), 'utf-8')).decode('ascii'))
    except CyclosAPIException:
        raise AuthenticationFailed()

    user_results = dolibarr.get(model='users', login=username, api_key=dolibarr_token)

    try:
        user_data = [item
                     for item in user_results
                     if item['login'] == username][0]
    except (KeyError, IndexError):
        raise AuthenticationFailed()

    user, created = User.objects.get_or_create(username=username)

    user_profile = user.profile
    user_profile.cyclos_token = cyclos_token
    user_profile.dolibarr_token = dolibarr_token

    # if there is a member linked to this user, load it in order to retrieve its company name
    user_profile.companyname = ''
    if user_data['fk_member']:
        try:
            member = dolibarr.get(model='members', id=user_data['fk_member'], api_key=dolibarr_token)
            if member['company']:
                user_profile.companyname = member['company']
        except DolibarrAPIException:
            pass

    try:
        user_profile.firstname = user_data['firstname']
        user_profile.lastname = user_data['lastname']
    except KeyError:
        raise AuthenticationFailed()

    user_profile.save()

    return user
