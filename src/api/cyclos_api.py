import logging

from django.conf import settings
from rest_framework.exceptions import APIException
import requests

log = logging.getLogger()


class CyclosAPIException(APIException):
    status_code = 400
    default_detail = 'Cyclos API Exception'


class CyclosAPI(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        try:
            self.url
        except AttributeError:
            self.url = settings.CYCLOS_URL

        try:
            if self.mode == 'bdc':
                self._init_bdc()
            elif self.mode == 'gi_bdc' and self.bdc_login:
                self._init_gi_bdc()
        except AttributeError:
            pass

    def _init_bdc(self):
        # getCurrentUser => get ID for current user
        try:
            self.user_profile = self.post(method='user/getCurrentUser', data=[])
            self.user_id = self.user_profile['result']['id']
        except CyclosAPIException:
            raise CyclosAPIException(detail='Unable to connect to Cyclos!')
        except KeyError:
            raise CyclosAPIException(detail='Unable to fetch Cyclos data! Maybe your credentials are invalid!?')

        # user/load for this ID to get field BDC ID
        try:
            self.user_data = self.post(method='user/load', data=self.user_id)
            self.user_bdc_id = [item['linkedEntityValue']['id']
                                for item in self.user_data['result']['customValues']
                                if item['field']['id'] ==
                                str(settings.CYCLOS_CONSTANTS['user_custom_fields']['bdc'])][0]
        except CyclosAPIException:
            raise CyclosAPIException(detail='Unable to connect to Cyclos!')
        except (KeyError, IndexError):
            raise CyclosAPIException(detail='Unable to fetch Cyclos data! Maybe your credentials are invalid!?')

    def _init_gi_bdc(self):
        self.user_id = self.get_member_id_from_login(self.bdc_login)
        self.user_bdc_id = self.user_id

    def get_member_id_from_login(self, member_login, auth_string=None):
        if auth_string:
            self._handle_auth_string(auth_string)

        query_data = {
            'keywords': member_login,
            'userStatus': ['ACTIVE', 'BLOCKED', 'DISABLED']
        }
        try:
            member_login_data = self.post(method='user/search', data=query_data)
            member_cyclos_id = member_login_data['result']['pageItems'][0]['id']
        except CyclosAPIException:
            raise CyclosAPIException(detail='Unable to connect to Cyclos!')
        except (KeyError, IndexError):
            raise CyclosAPIException(detail='Unable to fetch Cyclos data! Maybe your credentials are invalid!?')

        return member_cyclos_id

    def _handle_auth_string(self, auth_string):
        log.debug(auth_string)
        self.auth_string = auth_string
        return auth_string

    def _handle_auth_headers(self, headers):
        headers.update({'Authorization': 'Basic {}'.format(self.auth_string)})
        return headers

    def _handle_api_response(self, api_response):
        """ In some cases, we have to deal with errors in the response from the cyclos api !
        """
        if api_response.status_code == requests.codes.ok:
            response_data = api_response.json()
        else:
            message = 'Cyclos API Exception in {} - {}: {} - {}'.format(
                api_response.request.method, api_response.url, api_response, api_response.text)
            log.critical(message)
            raise CyclosAPIException(detail=message)

        # We don't have errors in our response, we can go on... and handle the response in our view.
        log.info("response_data for {} - {}: {}".format(api_response.request.method, api_response.url, response_data))
        return response_data

    def get(self, method, id=None, auth_string=None, **kwargs):
        if auth_string:
            self._handle_auth_string(auth_string)

        if id:
            query = '{}/{}/{}'.format(self.url, method, id)
        else:
            query = '{}/{}'.format(self.url, method)

        for key, value in kwargs.items():
            query = "{}&{}={}".format(query, key, value)

        r = requests.get(query, headers=self._handle_auth_headers({'content-type': 'application/json'}))

        return self._handle_api_response(r)

    def post(self, method, data, id=None, auth_string=None):
        if auth_string:
            self._handle_auth_string(auth_string)

        if id:
            query = '{}/{}/{}'.format(self.url, method, id)
        else:
            query = '{}/{}'.format(self.url, method)

        r = requests.post(query, json=data, headers=self._handle_auth_headers({'content-type': 'application/json'}))

        return self._handle_api_response(r)

    def patch(self, method, data, id=None, auth_string=None):
        if auth_string:
            self._handle_auth_string(auth_string)

        if id:
            query = '{}/{}/{}'.format(self.url, method, id)
        else:
            query = '{}/{}'.format(self.url, method)

        r = requests.patch(query, json=data, headers=self._handle_auth_headers({'content-type': 'application/json'}))

        return self._handle_api_response(r)

    def delete(self, method, id=None, auth_string=None):
        if auth_string:
            self._handle_auth_string(auth_string)

        if id:
            query = '{}/{}/{}'.format(self.url, method, id)
        else:
            query = '{}/{}'.format(self.url, method)

        r = requests.delete(query, headers=self._handle_auth_headers({'content-type': 'application/json'}))

        return self._handle_api_response(r)
