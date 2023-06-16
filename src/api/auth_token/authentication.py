from base64 import b64encode
import logging

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import validate_email
from rest_framework.exceptions import AuthenticationFailed

from cyclos_api import CyclosAPI, CyclosAPIException
from dolibarr_api import DolibarrAPI, DolibarrAPIException
from odoo_api import OdooAPI, DolibarrAPIException

log = logging.getLogger(__name__)


def authenticate(username, password):
    user = None
    try:
        dolibarr = OdooAPI()
        dolibarr_token = dolibarr.login(login=username, password=password, reset=True)
    except (DolibarrAPIException):
        raise AuthenticationFailed()

    try:
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(username, password), 'utf-8')).decode('ascii'))
    except CyclosAPIException:
        raise AuthenticationFailed()

    user, created = User.objects.get_or_create(username=username)

    user_profile = user.profile
    user_profile.cyclos_token = cyclos_token
    user_profile.dolibarr_token = dolibarr_token

    # if there is a member linked to this user, load it in order to retrieve its company name
    user_profile.companyname = ''
    user_profile.save()

    return user


def get_username_from_username_or_email(username_or_email):
    username = ''

    try:
        # validate (or not) the fact that our "username_or_email" variable is an email
        validate_email(username_or_email)

        # we detected that our "username_or_email" variable is an email,
        # we try to find the user that has this email (there must be exactly one)
        try:
            dolibarr = DolibarrAPI()
            dolibarr_anonymous_token = dolibarr.login(login=settings.APPS_ANONYMOUS_LOGIN,
                                                      password=settings.APPS_ANONYMOUS_PASSWORD,
                                                      reset=True)
            user_results = dolibarr.get(model='users',
                                        sqlfilters="email='{}'".format(username_or_email),
                                        api_key=dolibarr_anonymous_token)
            matching_users = [item
                              for item in user_results
                              if item['email'] == username_or_email]
            if matching_users and len(matching_users) == 1:
                username = matching_users[0]['login']

        except (DolibarrAPIException, KeyError, IndexError):
            pass

    except forms.ValidationError:
        # we detected that our "username_or_email" variable is NOT an email so it's a username
        username = username_or_email

    log.debug('get_username_from_username_or_email({}) -> {}'.format(username_or_email, username))

    return username
