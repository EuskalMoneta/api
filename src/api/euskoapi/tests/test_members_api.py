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

    def test_get_all(self):
        query = '{}/{}/'.format(self.url, self.model)
        r = requests.get(query)
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
        data = {'email': 'florian@lefrioux.fr',
                'town': 'Anglet', 'morphy': 'phy',
                'state_id': 'Pyrénées-Atlantiques',
                'phone_mobile': '0623151353',
                'array_options': {'options_recevoir_actus': '0'},
                'zip': '64600', 'address': '8 Allée Sagardi',
                'public': '0', 'statut': '1', 'country_id': 'France',
                'birth': '18/03/1988', 'lastname': 'Le Frioux',
                'civility_id': 'MR', 'firstname': 'Florian',
                'typeid': '3', 'login': 'E13337'}

        query = '{}/{}/'.format(self.url, self.model)
        r = requests.post(query, json=data)
        res = r.json()

        self.assertEqual(r.status_code, status.HTTP_200_OK,
                         "expecting {}, got {} for value {}".format(status.HTTP_200_OK, r.status_code, res))

        self.assertIsInstance(res, int)

    def test_get_id(self, id=None):
        if id is None:
            id = 310
        query = '{}/{}/{}/'.format(self.url, self.model, id)
        r = requests.get(query)
        res = r.json()

        self.assertEqual(r.status_code, status.HTTP_200_OK,
                         "expecting {}, got {} for value {}".format(status.HTTP_200_OK, r.status_code, res))

        self.assertIsInstance(res, dict)
        self.assertEqual(res['id'], str(310))
        self.assertIsInstance(res['town'], str)
        self.assertIsInstance(res['lastname'], str)

    # def test_patch(self):
    #     query = '{}/{}/{}/'.format(self.url, self.model, 310)
    #     r = requests.patch(query)
    #     res = r.json()

    #     self.assertEqual(r.status_code, status.HTTP_200_OK,
    #                      "expecting {}, got {} for value {}".format(status.HTTP_200_OK, r.status_code, res))

    #     self.assertIsInstance(res, dict)
    #     self.assertEqual(res['id'], str(id))
    #     self.assertIsInstance(res['town'], str)
    #     self.assertIsInstance(res['lastname'], str)

    # def test_delete(self):
    #     query = '{}/{}/{}/'.format(self.url, self.model, 310)
    #     r = requests.delete(query)
    #     res = r.json()

    #     self.assertEqual(r.status_code, status.HTTP_200_OK,
    #                      "expecting {}, got {} for value {}".format(status.HTTP_200_OK, r.status_code, res))

    #     self.assertIsInstance(res, dict)
    #     self.assertEqual(res['id'], str(id))
    #     self.assertIsInstance(res['town'], str)
    #     self.assertIsInstance(res['lastname'], str)
