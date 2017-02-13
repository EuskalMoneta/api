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
    try:
        dolibarr = DolibarrAPI()

        try:
            # validate (or not) the fact that our "username" variable is an email
            validate_email(username)

            # we detected that our "username" variable is an email, we try to connect to dolibarr with it
            dolibarr_anonymous_token = dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                                                      password=settings.APPS_ANONYMOUS_PASSWORD,
                                                      reset=True)
            member_results = dolibarr.get(model='members', email=username, api_key=dolibarr_anonymous_token)
            member_data = [item
                           for item in member_results
                           if item['email'] == username][0]
            if not member_data:
                raise AuthenticationFailed()

            token = dolibarr.login(login=member_data['login'], password=password, reset=True)

            # Cyclos needs the real 'username', we save it for later
            username = member_data['login']
        except forms.ValidationError:
            # we detected that our "username" variable is NOT an email
            token = dolibarr.login(login=username, password=password, reset=True)
    except (DolibarrAPIException, KeyError, IndexError):
        raise AuthenticationFailed()

    try:
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(username, password), 'utf-8')).decode('ascii'))
    except CyclosAPIException:
        raise AuthenticationFailed()

    if token:
        user_results = dolibarr.get(model='users', login=username, api_key=token)

        try:
            user_data = [item
                         for item in user_results
                         if item['login'] == username][0]
        except (KeyError, IndexError):
            raise AuthenticationFailed()

        user, created = User.objects.get_or_create(username=username)

        user_profile = user.profile
        user_profile.cyclos_token = cyclos_token
        user_profile.dolibarr_token = token

        try:
            if member_data['company']:
                user_profile.companyname = member_data['company']
            else:
                user_profile.companyname = ''
        except KeyError:
            user_profile.companyname = ''

        try:
            user_profile.firstname = user_data['firstname']
            user_profile.lastname = user_data['lastname']
        except KeyError:
            raise AuthenticationFailed()

        user_profile.save()

    return user
