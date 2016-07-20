import logging
import unittest

from rest_framework import status
import requests


class GenericTestSuite(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(GenericTestSuite, self).__init__(*args, **kwargs)

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
        self.assertIsInstance(res['results'][0]['company'], str)
        self.assertIsInstance(res['results'][0]['lastname'], str)

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
        self.assertIsInstance(res['company'], str)
        self.assertIsInstance(res['lastname'], str)
