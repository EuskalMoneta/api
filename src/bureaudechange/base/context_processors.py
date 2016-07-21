# coding: utf-8

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

log = logging.getLogger(__name__)


def get_django_settings(request):
    """
    Récupère les settings précisés dans la liste settings.TEMPLATE_VISIBLE_SETTINGS,
    et les passent au template
    """
    django_settings = {}
    for attr in getattr(settings, "TEMPLATE_VISIBLE_SETTINGS", ()):
        try:
            django_settings[attr] = getattr(settings, attr)
        except AttributeError:
            raise ImproperlyConfigured("TEMPLATE_VISIBLE_SETTINGS: '{0}' does not exist".format(attr))

    return {'django_settings': django_settings} if django_settings else {}
