import logging

import pytest
from rest_framework import status
import requests

log = logging.getLogger()


@pytest.fixture(scope="module")
def api():
    data = {"url": "http://localhost:8000",
            "model": "members",
            "headers": {"Accept": "application/json",
                        "Content-Type": "application/json",
                        "Authorization": ""},
            "api_token": "",
            "member_created_id": str()}

    query = '{}/{}/'.format(data['url'], 'api-token-auth')
    r = requests.post(query, headers=data['headers'],
                      json={'username': 'B003', 'password': 'B003'})
    data['api_token'] = r.json()['token']
    data['headers']['Authorization'] = 'Token {}'.format(data['api_token'])
    return data


class TestMembersAPI:

    def test_1_get_all(self, api):
        query = '{}/{}/'.format(api['url'], api['model'])
        log.info("query: {}".format(query))

        r = requests.get(query, headers=api['headers'])
        res = r.json()
        log.info("res: {}".format(res))

        assert r.status_code == status.HTTP_200_OK
        assert isinstance(res, dict)
        assert isinstance(res['count'], int)
        assert isinstance(res['previous'], str) or res['previous'] is None
        assert isinstance(res['next'], str) or res['next'] is None
        assert isinstance(res['results'], list)
        assert isinstance(res['results'][0]['id'], str)
        assert isinstance(res['results'][0]['town'], str)
        assert isinstance(res['results'][0]['lastname'], str)

    def test_2_post(self, api):
        data = {"login": "E12345", "civility_id": "MR",
                "lastname": "Lastname", "firstname": "Firstname",
                "address": "Full member Address",
                "phone": "0559520654", "email": "email@valid.net",
                "options_recevoir_actus": "0", "birth": "01/01/1980",
                "fk_asso": "809", "fk_asso2": "825",
                "country_id": "1", "zip": "64600", "town": "Angelu / Anglet"}
        # TODO: We also need a way to test the 'options_asso_saisie_libre' field...

        query = '{}/{}/'.format(api['url'], api['model'])
        log.info("query: {}".format(query))

        r = requests.post(query, json=data, headers=api['headers'])
        res = r.json()
        log.info("res: {}".format(res))

        assert r.status_code == status.HTTP_201_CREATED
        assert isinstance(res, int)
        log.info(api['member_created_id'])
        api['member_created_id'] = str(res)

    def test_3_get_id(self, api):
        log.info(api['member_created_id'])
        query = '{}/{}/{}/'.format(api['url'], api['model'], api['member_created_id'])
        log.info("query: {}".format(query))

        r = requests.get(query, headers=api['headers'])
        res = r.json()
        log.info("res: {}".format(res))

        assert r.status_code == status.HTTP_200_OK
        assert isinstance(res, dict)
        assert res['id'] == api['member_created_id']
        assert isinstance(res['town'], str)
        assert isinstance(res['lastname'], str)


class TestMembersSubscriptionsAPI:

    def test_1_register_subscription(self, api):
        query_get_member = '{}/{}/{}/'.format(api['url'], 'members', '910')
        log.info("query_get_member: {}".format(query_get_member))

        r_member = requests.get(query_get_member, headers=api['headers'])
        # I use this res_member to get datefin field, and verify that its been updated after we registered a sub
        res_member = r_member.json()
        log.info("res_member: {}".format(res_member))

        # I need to fetch different payment_modes from Cyclos to provide the cyclos_id_payment_mode parameter
        query_payment_modes = '{}/{}/'.format(api['url'], 'payment-modes')
        log.info("query_payment_modes: {}".format(query_payment_modes))

        r_payment_modes = requests.get(query_payment_modes, headers=api['headers'])
        res_payment_modes = r_payment_modes.json()
        log.info("res_payment_modes: {}".format(res_payment_modes))

        cyclos_id_payment_mode = [item for item in res_payment_modes
                                  if item['value'] == 'Euro-LIQ'][0]

        data = {'amount': '10', 'member_id': '910',
                'payment_mode': 'Euro-LIQ', 'cyclos_id_payment_mode': cyclos_id_payment_mode['cyclos_id']}
        query = '{}/{}/'.format(api['url'], 'members-subscriptions')
        log.info("data: {}".format(data))
        log.info("query: {}".format(query))

        r = requests.post(query, json=data, headers=api['headers'])
        res = r.json()
        log.info("res: {}".format(res))

        assert r.status_code == status.HTTP_201_CREATED
        assert isinstance(res, dict)
        assert isinstance(res['id_payment'], int)
        assert isinstance(res['id_link_payment_member'], int)
        assert isinstance(res['id_subscription'], int)
        assert isinstance(res['link_sub_payment'], dict)
        assert res['link_sub_payment']['amount'] == data['amount']
        assert res['link_sub_payment']['element'] == 'subscription'
        assert res['link_sub_payment']['fk_adherent'] == data['member_id']
        assert isinstance(res['member'], dict)
        assert res['member']['id'] == data['member_id']
        assert res['member']['last_subscription_amount'] == data['amount']
        assert res['member']['datefin'] > res_member['datefin']
        assert res['member']['element'] == 'member'
