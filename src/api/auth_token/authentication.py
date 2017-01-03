from base64 import b64encode
import logging

from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed

from dolibarr_api import DolibarrAPI, DolibarrAPIException


log = logging.getLogger()


def authenticate(username, password):
    user = None
    try:
        dolibarr = DolibarrAPI()
        token = dolibarr.login(login=username, password=password)
    except DolibarrAPIException:
        raise AuthenticationFailed()

    cyclos_auth_string = b64encode(bytes('{}:{}'.format(username, password), "utf-8"))

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
        user_profile.dolibarr_token = token
        user_profile.cyclos_auth_string = cyclos_auth_string

        try:
            user_profile.firstname = user_data['firstname']
            user_profile.lastname = user_data['lastname']
        except KeyError:
            raise AuthenticationFailed()

        user_profile.save()

    return user
