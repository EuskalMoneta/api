from base.tests import BaseTestCase


class TestMembers(BaseTestCase):
    """ TestMembers
    """

    def setUp(self):
        super(TestMembers, self).setUp()

    def test_1(self):
        self.webdriver.get("http://localhost:8001/members/add")
        self.fill_input("login", "robin")
