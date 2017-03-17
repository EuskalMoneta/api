import logging

from django.conf import settings
from rest_framework.exceptions import APIException
import requests

from auth_token.models import UserProfile

log = logging.getLogger(__name__)


class CyclosAPIException(APIException):
    status_code = 400
    default_detail = 'Cyclos API Exception'


class CyclosAPILoggedOutException(APIException):
    status_code = 403
    default_detail = 'Cyclos API LoggedOut Exception'


class CyclosAPI(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        try:
            self.url
        except AttributeError:
            self.url = settings.CYCLOS_URL

        try:
            if self.mode == 'login':
                pass
            elif self.mode == 'bdc':
                self._init_bdc()
            elif self.mode == 'cel':
                self._init_cel()
            elif self.mode == 'gi':
                self._init_gi()
            elif self.mode == 'gi_bdc' and self.login_bdc:
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
        self.user_bdc_id = self.get_bdc_id_from_operator_id(self.user_id)

    def _init_cel(self):
        try:
            self.user_profile = self.post(method='user/getCurrentUser', data=[])
            self.user_id = self.user_profile['result']['id']
        except CyclosAPIException:
            raise CyclosAPIException(detail='Unable to connect to Cyclos!')
        except KeyError:
            raise CyclosAPIException(detail='Unable to fetch Cyclos data! Maybe your credentials are invalid!?')

    def _init_gi(self):
        # getCurrentUser => get ID for current user
        try:
            self.user_profile = self.post(method='user/getCurrentUser', data=[])
            self.user_id = self.user_profile['result']['id']
        except CyclosAPIException:
            raise CyclosAPIException(detail='Unable to connect to Cyclos!')
        except KeyError:
            raise CyclosAPIException(detail='Unable to fetch Cyclos data! Maybe your credentials are invalid!?')

    def _init_gi_bdc(self):
        # get ID for login_bdc
        self.user_id = self.get_member_id_from_login(self.login_bdc)

        # user/load for this ID to get field BDC ID
        self.user_bdc_id = self.get_bdc_id_from_operator_id(self.user_id)

    def login(self, auth_string):
        """Login function to get Cyclos token."""
        r = requests.post('{}/login/login'.format(self.url),
                          headers=self._handle_auth_headers(auth_string=auth_string))

        json_response = r.json()

        if r.status_code == requests.codes.ok:
            try:
                token = json_response['result']['sessionToken']
            except KeyError:
                message = 'Cyclos API Exception: {}'.format(json_response)
                raise CyclosAPIException(status_code=r.status_code, detail=message)
        else:
            message = 'Cyclos API Exception: {}'.format(json_response)
            raise CyclosAPIException(status_code=r.status_code, detail=message)

        return token

    def refresh_token(self):
        """Refresh Cyclos token."""
        r = requests.post('{}/login/replaceSession'.format(self.url), headers=self._handle_auth_headers())

        json_response = r.json()

        if r.status_code == requests.codes.ok:
            try:
                cyclos_token = json_response['result']

                user_profile = UserProfile.objects.get(cyclos_token=self.token)
                user_profile.cyclos_token = cyclos_token
                user_profile.save()

                self._handle_token(cyclos_token)

            except KeyError:
                message = 'Cyclos API Exception: {}'.format(json_response)
                raise CyclosAPIException(status_code=r.status_code, detail=message)
        else:
            message = 'Cyclos API Exception: {}'.format(json_response)
            raise CyclosAPIException(status_code=r.status_code, detail=message)

        return cyclos_token

    def get_member_id_from_login(self, member_login, token=None):
        if token:
            self._handle_token(token)

        query_data = {
            'keywords': member_login,
            'userStatus': ['ACTIVE', 'BLOCKED', 'DISABLED']
        }
        try:
            member_login_search = self.post(method='user/search', data=query_data)
            member_login_data = [user
                                 for user in member_login_search['result']['pageItems']
                                 if user['shortDisplay'] == member_login]
            member_cyclos_id = member_login_data[0]['id']
        except CyclosAPIException:
            raise CyclosAPIException(detail='Unable to connect to Cyclos!')
        except (KeyError, IndexError):
            raise CyclosAPIException(detail='Unable to fetch Cyclos data! Maybe your credentials are invalid!?')

        return member_cyclos_id

    def get_bdc_id_from_operator_id(self, operator_id):
        """
        user/load for this ID to get field BDC ID
        """
        try:
            self.user_data = self.post(method='user/load', data=operator_id)
            return [item['linkedEntityValue']['id']
                    for item in self.user_data['result']['customValues']
                    if item['field']['id'] ==
                    str(settings.CYCLOS_CONSTANTS['user_custom_fields']['bdc'])][0]
        except CyclosAPIException:
            raise CyclosAPIException(detail='Unable to connect to Cyclos!')
        except (KeyError, IndexError):
            raise CyclosAPIException(detail='Unable to fetch Cyclos data! Maybe your credentials are invalid!?')

    def _handle_token(self, token):
        log.debug(token)
        self.token = token
        return token

    def _handle_auth_headers(self, headers=None, token=None, auth_string=None):
        headers = headers if isinstance(headers, dict) else {'Content-Type': 'application/json'}

        if auth_string:
            headers.update({'Authorization': 'Basic {}'.format(auth_string)})
        elif token:
            headers.update({'Session-Token': token})
        else:
            try:
                headers.update({'Session-Token': self.token})
            except AttributeError:
                raise CyclosAPIException(detail='Unable to read to Cyclos token!')

        return headers

    def _handle_api_response(self, api_response):
        """ In some cases, we have to deal with errors in the response from the cyclos api !
        """
        if api_response.status_code == requests.codes.ok:
            response_data = api_response.json()
        else:
            try:
                response_data = api_response.json()
                if response_data['errorCode'] == 'LOGGED_OUT':
                    raise CyclosAPILoggedOutException(response_data['errorCode'])
            except CyclosAPILoggedOutException:
                raise
            except:
                pass

            message = 'Cyclos API Exception in {} - {}: {} - {}'.format(
                api_response.request.method, api_response.url, api_response, api_response.text)
            log.critical(message)
            raise CyclosAPIException(detail=message)

        # We don't have errors in our response, we can go on... and handle the response in our view.
        log.info("response_data for {} - {}: {}".format(api_response.request.method, api_response.url, response_data))
        return response_data

    def get(self, method, id=None, token=None, **kwargs):
        if token:
            self._handle_token(token)

        if id:
            query = '{}/{}/{}'.format(self.url, method, id)
        else:
            query = '{}/{}'.format(self.url, method)

        for key, value in kwargs.items():
            query = "{}&{}={}".format(query, key, value)

        r = requests.get(query, headers=self._handle_auth_headers())

        return self._handle_api_response(r)

    def post(self, method, data, id=None, token=None):
        if token:
            self._handle_token(token)

        if id:
            query = '{}/{}/{}'.format(self.url, method, id)
        else:
            query = '{}/{}'.format(self.url, method)

        r = requests.post(query, json=data, headers=self._handle_auth_headers({}))

        return self._handle_api_response(r)

    def patch(self, method, data, id=None, token=None):
        if token:
            self._handle_token(token)

        if id:
            query = '{}/{}/{}'.format(self.url, method, id)
        else:
            query = '{}/{}'.format(self.url, method)

        r = requests.patch(query, json=data, headers=self._handle_auth_headers())

        return self._handle_api_response(r)

    def delete(self, method, id=None, token=None):
        if token:
            self._handle_token(token)

        if id:
            query = '{}/{}/{}'.format(self.url, method, id)
        else:
            query = '{}/{}'.format(self.url, method)

        r = requests.delete(query, headers=self._handle_auth_headers())

        return self._handle_api_response(r)
