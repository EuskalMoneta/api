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
    username = username_or_email


    return username
