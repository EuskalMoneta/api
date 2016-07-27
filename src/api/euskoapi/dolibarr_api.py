# -*- coding: utf-8 -*-

import logging

from django.conf import settings
import requests

log = logging.getLogger(__name__)


class DolibarrAPI(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        try:
            self.url
        except AttributeError:
            self.url = settings.DOLIBARR_URL

        self.api_key = self.login()

    def get(self, model, id=None, **kwargs):
        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)
            for key, value in kwargs.items():
                query = "{}&{}={}".format(query, key, value)

        r = requests.get(query, headers={'content-type': 'application/json'})

        return r.json()

    def post(self, model, data, id=None):
        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.post(query, json=data, headers={'content-type': 'application/json'})
        return r.json()

    def patch(self, model, data, id=None):
        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.patch(query, json=data, headers={'content-type': 'application/json'})
        return r.json()

    def delete(self, model, id=None):
        if id:
            query = '{}/{}/{}?api_key={}'.format(self.url, model, id, self.api_key)
        else:
            query = '{}/{}?api_key={}'.format(self.url, model, self.api_key)

        r = requests.delete(query, headers={'content-type': 'application/json'})
        return r.json()

    def login(self, login=None, password=None):
        """ Login function for Dolibarr API users. """
        if not login or not password:
            login = 'florian'
            password = 'florian'

        r = requests.get('{}/login?login={}&password={}'.format(self.url, login, password),
                         headers={'content-type': 'application/json'})

        if r.status_code == requests.codes.ok:
            return r.json()['success']['token']
        else:
            log.critical("Unable to login to dolibarr!")
            return False
