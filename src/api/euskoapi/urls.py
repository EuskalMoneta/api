""" euskalmoneta API URL Configuration """

from django.conf.urls import url
from rest_framework import routers

from members.views import MembersAPIView, MembersSubscriptionsAPIView
from dolibarr_data.views import towns_by_zipcode, countries, country_by_id


router = routers.SimpleRouter()
router.register(r'members', MembersAPIView, base_name='members')
router.register(r'members-subscriptions', MembersSubscriptionsAPIView, base_name='members-subscriptions')

urlpatterns = [
    url(r'^towns/$', towns_by_zipcode),
    url(r'^countries/$', countries),
    url(r'^countries/(?P<id>[^/.]+)/$', country_by_id),
]

urlpatterns += router.urls
