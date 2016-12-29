import logging

# from django.conf import settings

log = logging.getLogger()


class BDC:

    @staticmethod
    def validate_login(data):
        if data.startswith("B") and len(data) == 4:
            return True
        else:
            return False
