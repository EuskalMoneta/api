import logging

from django.core import mail

log = logging.getLogger()


class EuskalMonetaAPIException(Exception):
    pass


def sendmail_euskalmoneta(subject, body, to_email, from_email=None):
    if from_email is None:
        from_email = 'contact@euskalmoneta.org'

    with mail.get_connection() as connection:
        mail.EmailMessage(subject, body, from_email, [to_email], connection=connection).send()
