from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed

from dolibarr_api import DolibarrAPI, DolibarrAPIException

import logging

log = logging.getLogger('sentry')


def authenticate(username, password):
    user = None
    try:
        dolibarr = DolibarrAPI()
        token = dolibarr.login(login=username, password=password)
    except DolibarrAPIException:
        raise AuthenticationFailed()

    if token:
        user, created = User.objects.get_or_create(username=username, password=password)
        user_profile = user.profile
        user_profile.dolibarr_token = token
        user_profile.save()

    return user
