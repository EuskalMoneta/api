import logging

from django.conf import settings
from django.core import mail

log = logging.getLogger()


class EuskalMonetaAPIException(Exception):
    pass


def sendmail_euskalmoneta(subject, body, to_email=None, from_email=None):
    if to_email is None:
        to_email = settings.EMAIL_NOTIFICATION_GESTION
    if from_email is None:
        from_email = settings.EMAIL_HOST_USER

    with mail.get_connection() as connection:
        mail.EmailMessage(subject, body, from_email, [to_email], connection=connection).send()
