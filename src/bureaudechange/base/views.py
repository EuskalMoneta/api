from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import LANGUAGE_SESSION_KEY, check_for_language


@login_required
def home(request):
    # homepage for bureauchange app
    return render(request, 'home.html')


def config_js(request):
    # JavaScript config for this Django/React app
    return render(request, 'config.js')


def setlang_custom(request):
    """
    In this React app, I'm using fetch API to do AJAX requests, and in this particular case
    I have to use a custom i18n function because:
    - For some reason I can't make 'request.POST.get(LANGUAGE_QUERY_PARAMETER)' work with fetch
    - I need to set the 'django_language' cookie, even if I have a session.

    This code is based on set_language():
    https://github.com/django/django/blob/stable/1.10.x/django/views/i18n.py#L28
    """
    lang_code = request.META.get('HTTP_ACCEPT_LANGUAGE', settings.LANGUAGE_CODE)
    response = HttpResponse()
    if request.method == 'POST':
        if check_for_language(lang_code):
            # I need both session...
            request.session[LANGUAGE_SESSION_KEY] = lang_code
            # AND cookies !
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME,
                                lang_code,
                                max_age=settings.LANGUAGE_COOKIE_AGE,
                                path=settings.LANGUAGE_COOKIE_PATH,
                                domain=settings.LANGUAGE_COOKIE_DOMAIN)

    return response
