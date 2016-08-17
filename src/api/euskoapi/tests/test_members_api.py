import logging

import pytest
from rest_framework import status
import requests

log = logging.getLogger('sentry')


class TestMembersAPI:

    @pytest.fixture(scope="session")
    def api(self):
        return {"url": "http://localhost:8000",
                "model": "members",
                "headers": {"Accept": "application/json", "Content-Type": "application/json"},
                "member_created_id": str()}

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
                "country_id": "1", "zip": "64600", "town": "Angelu / Anglet"}

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

    # def test_4_delete(self, api):
    #     query = '{}/{}/{}/'.format(api['url'], api['model'], api['member_created_id'])
    #     log.info("query: {}".format(query))
    #     r = requests.delete(query, headers=api['headers'])
    #     res = r.json()

    #     log.info("res: {}".format(res))
    #     assert r.status_code == status.HTTP_200_OK
    #     # {'success': {'message': , 'code': 200}}
    #     assert isinstance(res, dict)
    #     assert isinstance(res['success'], dict)
    #     assert res['success']['message'] == 'member deleted'
    #     assert res['success']['code'] == 200

    # def test_patch(self):
    #     query = '{}/{}/{}/'.format(api['url'], api['model'], api['member_created_id'])
    #     log.info("query: {}".format(query))
    #     r = requests.patch(query, headers=api['headers'])
    #     res = r.json()
    #     log.info("res: {}".format(res))

    #     assert r.status_code == status.HTTP_200_OK
    #     assert isinstance(res, dict)
    #     assert res['id'] == str(id)
    #     assert isinstance(res['town'], str)
    #     assert isinstance(res['lastname'], str)
