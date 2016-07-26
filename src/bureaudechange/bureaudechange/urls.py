"""bureaudechange URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include, url, i18n
from django.contrib import admin
from django.contrib.auth.views import login, logout
from django.core.urlresolvers import reverse_lazy

from members import views as members_views
from base import views as base_views

urlpatterns = [
    # built-in Django i18n
    url(r'^i18n/', include(i18n)),

    # home
    url(r'^$', base_views.home, name='home'),
    # login
    url(r'^login/?$', login, {'template_name': 'login.html'}),
    # logout
    url(r'^logout/?$', logout, {'next_page': reverse_lazy('home')}),

    # our bureau de change Django apps
    url(r'^members/?$', members_views.index),
    url(r'^members/list$', members_views.index),
    url(r'^members/add$', members_views.add),

    url(r'^admin/', admin.site.urls),
]
