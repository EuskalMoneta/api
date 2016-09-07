""" euskalmoneta API URL Configuration """

from django.conf.urls import url
from rest_framework import routers

from auth_token import views as auth_token_views
import bdc_cyclos.views as bdc_cyclos_views
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
    url(r'^login/$', dolibarr_data_views.login),
    url(r'^associations/$', dolibarr_data_views.associations),
    url(r'^countries/$', dolibarr_data_views.countries),
    url(r'^countries/(?P<id>[^/.]+)/$', dolibarr_data_views.country_by_id),
    url(r'^towns/$', dolibarr_data_views.towns_by_zipcode),

    # Euskal moneta data (hardcoded data we dont fetch from APIs)
    url(r'^payment-modes/$', euskalmoneta_data_views.payment_modes),
    url(r'^porteurs-eusko/$', euskalmoneta_data_views.porteurs_eusko),

    # Cyclos data, data we fetch from/push to its API
    url(r'^accounts-summaries/$', bdc_cyclos_views.accounts_summaries),
    url(r'^entree-stock/$', bdc_cyclos_views.entree_stock),
    url(r'^change-euro-eusko/$', bdc_cyclos_views.change_euro_eusko),
]

urlpatterns += router.urls
