import logging

import pytest
from rest_framework import status
import requests

log = logging.getLogger('sentry')


@pytest.fixture(scope="module")
def api():
    return {"url": "http://localhost:8000",
            "model": "members",
            "headers": {"Accept": "application/json", "Content-Type": "application/json"},
            "member_created_id": str()}


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
                "lastname": "Le Frioux", "firstname": "Florian",
                "address": "8 Allée Sagardi Les Vergers Del Hogar",
                "phone": "0623151353", "email": "florian@lefrioux.fr",
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

        data = {'amount': '10', 'payment_mode': 'Euro-LIQ', 'member_id': '910'}
        query = '{}/{}/'.format(api['url'], 'members-subscriptions')
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
