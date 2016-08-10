# -*- coding: utf-8 -*-

import logging

from django.conf import settings
from rest_framework.exceptions import APIException
import requests

log = logging.getLogger()


class DolibarrAPIException(APIException):
    status_code = 400
    default_detail = 'Dolibarr API Exception'


class DolibarrAPI(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        try:
            self.url
        except AttributeError:
            self.url = settings.DOLIBARR_URL

        login_data = self._login()
        try:
            self.api_key = login_data['success']['token']
        except KeyError:
            log.critical(login_data)
            try:
                message = 'Dolibarr API Exception: {}'.format(login_data['errors']['message'])
            except KeyError:
                message = 'Dolibarr API Exception'
                raise DolibarrAPIException(detail=message)

    def _handle_api_response(self, api_response):
        """ In some cases, we have to deal with errors in the api_response from the dolibarr api !
        """
        if api_response.status_code == requests.codes.ok:
            response_data = api_response.json()
        else:
            log.critical('Dolibarr API Exception: {} - {}'.format(api_response, api_response.text))
            raise DolibarrAPIException(detail='Dolibarr API Exception')

        # We don't have errors in our response, we can go on... and handle the response in our view.
        log.info(response_data)
        return response_data

    def _login(self, login=None, password=None):
        """ Login function for Dolibarr API users. """
        if not login or not password:
            login = 'admin'
            password = 'admin'

        r = requests.get('{}/login?login={}&password={}'.format(self.url, login, password),
                         headers={'content-type': 'application/json'})

        return self._handle_api_response(r)

    def get(self, model, id=None, **kwargs):
        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        for key, value in kwargs.items():
            query = "{}&{}={}".format(query, key, value)

        r = requests.get(query, headers={'content-type': 'application/json'})

        return self._handle_api_response(r)

    def post(self, model, data, id=None):
        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.post(query, json=data, headers={'content-type': 'application/json'})

        return self._handle_api_response(r)

    def patch(self, model, data, id=None):
        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.patch(query, json=data, headers={'content-type': 'application/json'})

        return self._handle_api_response(r)

    def delete(self, model, id=None):
        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.delete(query, headers={'content-type': 'application/json'})

        return self._handle_api_response(r)
