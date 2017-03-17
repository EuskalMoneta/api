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

    username = get_username_from_username_or_email(username)
    if not username:
        raise AuthenticationFailed()

    try:
        dolibarr = DolibarrAPI()
        dolibarr_token = dolibarr.login(login=username, password=password, reset=True)
    except (DolibarrAPIException):
        raise AuthenticationFailed()

    try:
        cyclos = CyclosAPI(mode='login')
        cyclos_token = cyclos.login(
            auth_string=b64encode(bytes('{}:{}'.format(username, password), 'utf-8')).decode('ascii'))
    except CyclosAPIException:
        raise AuthenticationFailed()

    try:
        user_results = dolibarr.get(model='users', login=username, api_key=dolibarr_token)
        dolibarr_user = [item
                         for item in user_results
                         if item['login'] == username][0]
    except (DolibarrAPIException, KeyError, IndexError):
        raise AuthenticationFailed()

    user, created = User.objects.get_or_create(username=username)

    user_profile = user.profile
    user_profile.cyclos_token = cyclos_token
    user_profile.dolibarr_token = dolibarr_token

    # if there is a member linked to this user, load it in order to retrieve its company name
    user_profile.companyname = ''
    if dolibarr_user['fk_member']:
        try:
            member = dolibarr.get(model='members', id=dolibarr_user['fk_member'], api_key=dolibarr_token)
            if member['company']:
                user_profile.companyname = member['company']
        except DolibarrAPIException:
            pass

    try:
        user_profile.firstname = dolibarr_user['firstname']
        user_profile.lastname = dolibarr_user['lastname']
    except KeyError:
        raise AuthenticationFailed()

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
                                        email=username_or_email,
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
