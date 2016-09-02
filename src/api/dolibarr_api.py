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

    def _handle_api_key(self, api_key):
        log.debug(api_key)
        self.api_key = api_key
        return api_key

    def _handle_api_response(self, api_response):
        """ In some cases, we have to deal with errors in the response from the dolibarr api !
        """
        if api_response.status_code == requests.codes.ok:
            response_data = api_response.json()
        else:
            message = 'Dolibarr API Exception in {} - {}: {} - {}'.format(
                api_response.request.method, api_response.url, api_response, api_response.text)
            log.critical(message)
            raise DolibarrAPIException(detail=message)

        # We don't have errors in our response, we can go on... and handle the response in our view.
        log.info("response_data for {} - {}: {}".format(api_response.request.method, api_response.url, response_data))
        return response_data

    def login(self, login=None, password=None):
        """ Login function for Dolibarr API users. """
        r = requests.get('{}/login?login={}&password={}'.format(self.url, login, password),
                         headers={'content-type': 'application/json'})

        json_response = r.json()
        if r.status_code == requests.codes.ok:
            try:
                api_key = json_response['success']['token']
            except KeyError:
                try:
                    message = 'Dolibarr API Exception: {}'.format(json_response['errors']['message'])
                    raise DolibarrAPIException(status_code=json_response['errors']['code'], detail=message)
                except KeyError:
                    raise DolibarrAPIException()
        else:
            try:
                message = 'Dolibarr API Exception: {}'.format(json_response['errors']['message'])
                raise DolibarrAPIException(status_code=json_response['errors']['code'], detail=message)
            except KeyError:
                raise DolibarrAPIException()

        return self._handle_api_key(api_key)

    def get(self, model, id=None, api_key=None, **kwargs):
        if api_key:
            self._handle_api_key(api_key)

        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        for key, value in kwargs.items():
            query = "{}&{}={}".format(query, key, value)

        r = requests.get(query, headers={'content-type': 'application/json'})

        return self._handle_api_response(r)

    def post(self, model, data, id=None, api_key=None):
        if api_key:
            self._handle_api_key(api_key)

        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.post(query, json=data, headers={'content-type': 'application/json'})

        return self._handle_api_response(r)

    def patch(self, model, data, id=None, api_key=None):
        if api_key:
            self._handle_api_key(api_key)

        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.patch(query, json=data, headers={'content-type': 'application/json'})

        return self._handle_api_response(r)

    def delete(self, model, id=None, api_key=None):
        if api_key:
            self._handle_api_key(api_key)

        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.delete(query, headers={'content-type': 'application/json'})

        return self._handle_api_response(r)
