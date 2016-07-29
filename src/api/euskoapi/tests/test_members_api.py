import logging
import unittest

from rest_framework import status
import requests


class TestMembersAPI(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestMembersAPI, self).__init__(*args, **kwargs)

        self.log = logging.getLogger(__name__)
        self.url = 'http://localhost:8000'
        self.model = 'members'
        self.headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        self.member_created_id = int()

    def test_get_all(self):
        query = '{}/{}/'.format(self.url, self.model)
        r = requests.get(query, headers=self.headers)
        res = r.json()

        self.assertEqual(r.status_code, status.HTTP_200_OK,
                         "expecting {}, got {} for value {}".format(status.HTTP_200_OK, r.status_code, res))

        self.assertIsInstance(res, dict)
        self.assertIsInstance(res['count'], int)
        self.assertTrue(isinstance(res['previous'], str) or res['previous'] is None)
        self.assertTrue(isinstance(res['next'], str) or res['next'] is None)
        self.assertIsInstance(res['results'], list)
        self.assertIsInstance(res['results'][0]['id'], str)
        self.assertIsInstance(res['results'][0]['town'], str)
        self.assertIsInstance(res['results'][0]['lastname'], str)

    def test_post(self):
        data = {"address": "8 Allée Sagardi",
                "birth": "18/03/1988", "civility_id": "MR",
                "country_id": "France", "email": "florian@lefrioux.fr",
                "firstname": "Florian", "lastname": "Le Frioux",
                "login": "E13337", "options_recevoir_actus": "0",
                "phone": "0623151353", "state_id": "Pyrénées-Atlantiques",
                "town": "Anglet", "zip": "64600"}

        query = '{}/{}/'.format(self.url, self.model)
        r = requests.post(query, json=data, headers=self.headers)
        res = r.json()

        self.assertEqual(r.status_code, status.HTTP_201_CREATED,
                         "expecting {}, got {} for value {}".format(status.HTTP_201_CREATED, r.status_code, res))

        self.assertIsInstance(res, int)
        self.member_created_id = res

    def test_get_id(self, id=None):
        if id is None:
            id = 310
        query = '{}/{}/{}/'.format(self.url, self.model, id)
        r = requests.get(query, headers=self.headers)
        res = r.json()

        self.assertEqual(r.status_code, status.HTTP_200_OK,
                         "expecting {}, got {} for value {}".format(status.HTTP_200_OK, r.status_code, res))

        self.assertIsInstance(res, dict)
        self.assertEqual(res['id'], str(id))
        self.assertIsInstance(res['town'], str)
        self.assertIsInstance(res['lastname'], str)

    def test_delete(self):
        query = '{}/{}/{}/'.format(self.url, self.model, self.member_created_id)
        r = requests.delete(query, headers=self.headers)
        res = r.json()

        self.assertEqual(r.status_code, status.HTTP_200_OK,
                         "expecting {}, got {} for value {}".format(status.HTTP_200_OK, r.status_code, res))

        # {'success': {'message': , 'code': 200}}
        self.assertIsInstance(res, dict)
        self.assertIsInstance(res['success'], dict)
        self.assertEqual(res['success']['message'], 'member deleted')
        self.assertEqual(res['success']['code'], 200)

    # def test_patch(self):
    #     query = '{}/{}/{}/'.format(self.url, self.model, 310)
    #     r = requests.patch(query, headers=self.headers)
    #     res = r.json()

    #     self.assertEqual(r.status_code, status.HTTP_200_OK,
    #                      "expecting {}, got {} for value {}".format(status.HTTP_200_OK, r.status_code, res))

    #     self.assertIsInstance(res, dict)
    #     self.assertEqual(res['id'], str(id))
    #     self.assertIsInstance(res['town'], str)
    #     self.assertIsInstance(res['lastname'], str)
