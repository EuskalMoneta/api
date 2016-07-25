import unittest

from selenium import webdriver


class BaseTestCase(unittest.TestCase):
    """ BaseTestCase
    """

    def __init__(self, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)

    def setUp(self):
        self.webdriver = webdriver.Chrome()

    def tearDown(self):
        self.webdriver.close()

    def fill_input(self, input_name, input_value):
        field = self.webdriver.find_element_by_xpath("//input[@data-eusko-input='{}']".format(input_name))
        field.send_keys(input_value)
