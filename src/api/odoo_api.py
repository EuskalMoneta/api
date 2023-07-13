import logging
import urllib
from xmlrpc import client as xmlrpclib
from django.conf import settings
from rest_framework.exceptions import APIException



import xmlrpc.client

log = logging.getLogger()
class DolibarrAPIException(APIException):
    status_code = 400
    default_detail = 'Dolibarr API Exception'

class OdooAPI(object):

    def __init__(self, **kwargs):
        self.password = None
        self.uid = None
        self.__dict__.update(kwargs)
        try:
            self.url
        except AttributeError:
            self.url = settings.ODOO_URL


    def login(self, login=None, password=None, reset=None):
        """ Login function for Dolibarr API users.
        """
        common = xmlrpclib.ServerProxy('{}/xmlrpc/2/common'.format(settings.ODOO_URL))
        settings.UID = common.authenticate(settings.ODOO_DB,login, password,{})
        settings.PASS = password
        return settings.UID

    def get(self, model,domain=None,fields=False):
        """common = xmlrpclib.ServerProxy('{}/xmlrpc/2/common'.format(settings.ODOO_URL))
        uid = common.authenticate(settings.ODOO_DB, self.login, self.password, {})"""
        models = xmlrpclib.ServerProxy('{}/xmlrpc/2/object'.format(settings.ODOO_URL))
        res = models.execute_kw(settings.ODOO_DB,settings.UID ,settings.PASS, model, 'search_read', domain, fields)
        return res
