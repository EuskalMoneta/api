""" euskalmoneta API URL Configuration """

from django.conf.urls import url
from rest_framework import routers

from auth_token import views as auth_token_views
import cyclos_data.views as cyclos_data_views
import dolibarr_data.views as dolibarr_data_views
import euskalmoneta_data.views as euskalmoneta_data_views
from members.views import MembersAPIView, MembersSubscriptionsAPIView

router = routers.SimpleRouter()
router.register(r'members', MembersAPIView, base_name='members')
router.register(r'members-subscriptions', MembersSubscriptionsAPIView, base_name='members-subscriptions')

urlpatterns = [
    # Auth token
    url(r'^api-token-auth/', auth_token_views.obtain_auth_token),

    # Dolibarr data, data we fetch from its API
    url(r'^associations/$', dolibarr_data_views.associations),
    url(r'^countries/$', dolibarr_data_views.countries),
    url(r'^countries/(?P<id>[^/.]+)/$', dolibarr_data_views.country_by_id),
    url(r'^towns/$', dolibarr_data_views.towns_by_zipcode),

    # Euskal moneta data (hardcoded data we dont fetch from APIs)
    url(r'^payment-modes/$', euskalmoneta_data_views.payment_modes),

    # Cyclos data, data we fetch from its API
    url(r'^accounts-summaries/$', cyclos_data_views.accounts_summaries),
]

urlpatterns += router.urls
