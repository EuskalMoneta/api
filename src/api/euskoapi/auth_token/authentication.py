from django.contrib.auth.models import User

from dolibarr_api import DolibarrAPI, DolibarrAPIException

import logging

log = logging.getLogger('sentry')


def authenticate(username, password):
    user = None
    try:
        dolibarr = DolibarrAPI()
        log.critical(dolibarr)
        token = dolibarr.login(login=username, password=password)
        log.critical(token)
    except DolibarrAPIException:
        # TODO: Do something
        log.critical(dolibarr)
        log.critical(token)
        pass

    if token:
        user, created = User.objects.get_or_create(username=username, password=password)
        user_profile = user.profile
        user_profile.dolibarr_token = token
        user_profile.save()

    return user
