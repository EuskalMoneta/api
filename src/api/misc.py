import logging

from django.conf import settings
from django.core import mail
from smtplib import SMTPException

from django.template.loader import render_to_string
from django.utils.html import strip_tags

log = logging.getLogger()


class EuskalMonetaAPIException(Exception):
    pass


def sendmail_euskalmoneta(subject, body, to_email=None, from_email=None):
    if to_email is None:
        to_email = settings.EMAIL_NOTIFICATION_GESTION
    if from_email is None:
        from_email = settings.EMAIL_HOST_USER

    log.debug("sendmail:\nFrom: {}\nTo: {}\nSubject: {}\n{}".format(
        from_email, to_email, subject, body))
    with mail.get_connection() as connection:
        mail.EmailMessage(subject, body, from_email, [to_email], connection=connection).send()


def sendmailHTML_euskalmoneta(subject, html_message, to_email=None, from_email=None):
    if to_email is None:
        to_email = settings.EMAIL_NOTIFICATION_GESTION
    if from_email is None:
        from_email = settings.EMAIL_HOST_USER

    log.debug("sendmail:\nFrom: {}\nTo: {}\nSubject: {}\n{}".format(
        from_email, to_email, subject))

    plain_message = strip_tags(html_message)
    try:
        mail.send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)
    except SMTPException as e:
        sendmail_euskalmoneta('Erreur envoi mail : '+from_email, strip_tags(html_message) )

