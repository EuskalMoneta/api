import pytest
from rest_framework import status
import requests


class TestMembersAPI:

    @pytest.fixture(scope="session")
    def api(self):
        return {"url": "http://localhost:8000",
                "model": "members",
                "headers": {"Accept": "application/json", "Content-Type": "application/json"},
                "member_created_id": str()}

    def test_1_get_all(self, api):
        query = '{}/{}/'.format(api['url'], api['model'])
        print(query)
        r = requests.get(query, headers=api['headers'])
        res = r.json()

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
        data = {"address": "8 Allée Sagardi",
                "birth": "18/03/1988", "civility_id": "MR",
                "country_id": "France", "email": "florian@lefrioux.fr",
                "firstname": "Florian", "lastname": "Le Frioux",
                "login": "E13337", "options_recevoir_actus": "0",
                "phone": "0623151353", "state_id": "Pyrénées-Atlantiques",
                "town": "Anglet", "zip": "64600"}

        query = '{}/{}/'.format(api['url'], api['model'])
        print(query)
        r = requests.post(query, json=data, headers=api['headers'])
        res = r.json()

        print(res)
        assert r.status_code == status.HTTP_201_CREATED

        assert isinstance(res, int)
        print(api['member_created_id'])
        api['member_created_id'] = str(res)

    def test_3_get_id(self, api):
        print(api['member_created_id'])
        query = '{}/{}/{}/'.format(api['url'], api['model'], api['member_created_id'])
        print(query)
        r = requests.get(query, headers=api['headers'])
        res = r.json()

        print(res)
        assert r.status_code == status.HTTP_200_OK
        assert isinstance(res, dict)
        assert res['id'] == api['member_created_id']
        assert isinstance(res['town'], str)
        assert isinstance(res['lastname'], str)

    def test_4_delete(self, api):
        query = '{}/{}/{}/'.format(api['url'], api['model'], api['member_created_id'])
        print(query)
        r = requests.delete(query, headers=api['headers'])
        res = r.json()

        print(res)
        assert r.status_code == status.HTTP_200_OK
        # {'success': {'message': , 'code': 200}}
        assert isinstance(res, dict)
        assert isinstance(res['success'], dict)
        assert res['success']['message'] == 'member deleted'
        assert res['success']['code'] == 200

    # def test_patch(self):
    #     query = '{}/{}/{}/'.format(api['url'], api['model'], api['member_created_id'])
    #     r = requests.patch(query, headers=api['headers'])
    #     res = r.json()

    #     assert r.status_code == status.HTTP_200_OK

    #     assert isinstance(res, dict)
    #     assert res['id'] == str(id)
    #     assert isinstance(res['town'], str)
    #     assert isinstance(res['lastname'], str)
