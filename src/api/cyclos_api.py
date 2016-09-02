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

    def get(self, model, id=None, auth_string=None, **kwargs):
        if auth_string:
            self._handle_auth_string(auth_string)

        if id:
            query = '{}/{}/{}'.format(self.url, model, id)
        else:
            query = '{}/{}'.format(self.url, model)

        for key, value in kwargs.items():
            query = "{}&{}={}".format(query, key, value)

        r = requests.get(query, headers=self._handle_auth_headers({'content-type': 'application/json'}))

        return self._handle_api_response(r)

    def post(self, model, data, id=None, auth_string=None):
        if auth_string:
            self._handle_auth_string(auth_string)

        if id:
            query = '{}/{}/{}'.format(self.url, model, id)
        else:
            query = '{}/{}'.format(self.url, model)

        r = requests.post(query, json=data, headers=self._handle_auth_headers({'content-type': 'application/json'}))

        return self._handle_api_response(r)

    def patch(self, model, data, id=None, auth_string=None):
        if auth_string:
            self._handle_auth_string(auth_string)

        if id:
            query = '{}/{}/{}'.format(self.url, model, id)
        else:
            query = '{}/{}'.format(self.url, model)

        r = requests.patch(query, json=data, headers=self._handle_auth_headers({'content-type': 'application/json'}))

        return self._handle_api_response(r)

    def delete(self, model, id=None, auth_string=None):
        if auth_string:
            self._handle_auth_string(auth_string)

        if id:
            query = '{}/{}/{}'.format(self.url, model, id)
        else:
            query = '{}/{}'.format(self.url, model)

        r = requests.delete(query, headers=self._handle_auth_headers({'content-type': 'application/json'}))

        return self._handle_api_response(r)
