""" euskalmoneta API URL Configuration """

from django.conf.urls import url
from rest_framework import routers

from bureauxdechange.views import BDCAPIView
from members.views import MembersAPIView, MembersSubscriptionsAPIView

from auth_token import views as auth_token_views
import bdc_cyclos.views as bdc_cyclos_views
import dolibarr_data.views as dolibarr_data_views
import euskalmoneta_data.views as euskalmoneta_data_views
import gestioninterne.views as gi_views


router = routers.SimpleRouter()
router.register(r'bdc', BDCAPIView, base_name='bdc')
router.register(r'members', MembersAPIView, base_name='members')
router.register(r'members-subscriptions', MembersSubscriptionsAPIView, base_name='members-subscriptions')

urlpatterns = [
    # Auth token
    url(r'^api-token-auth/', auth_token_views.obtain_auth_token),

    # Dolibarr data, data we fetch from its API
    url(r'^login/$', dolibarr_data_views.login),
    url(r'^usergroups/$', dolibarr_data_views.get_usergroups),
    url(r'^verify-usergroup/$', dolibarr_data_views.verify_usergroup),
    url(r'^associations/$', dolibarr_data_views.associations),
    url(r'^countries/$', dolibarr_data_views.countries),
    url(r'^countries/(?P<id>[^/.]+)/$', dolibarr_data_views.country_by_id),
    url(r'^bdc-name/$', dolibarr_data_views.get_bdc_name),
    url(r'^user-data/$', dolibarr_data_views.get_user_data),
    url(r'^towns/$', dolibarr_data_views.towns_by_zipcode),

    # Euskal moneta data (hardcoded data we dont fetch from APIs)
    url(r'^payment-modes/$', euskalmoneta_data_views.payment_modes),
    url(r'^porteurs-eusko/$', euskalmoneta_data_views.porteurs_eusko),
    url(r'^deposit-banks/$', euskalmoneta_data_views.deposit_banks),

    # Cyclos data, data we fetch from/push to its API
    url(r'^accounts-summaries/(?P<login_bdc>[\w\-]+)?/?$', bdc_cyclos_views.accounts_summaries),
    url(r'^member-accounts-summaries/$', bdc_cyclos_views.member_account_summary),
    url(r'^accounts-history/$', bdc_cyclos_views.accounts_history),
    url(r'^payments-available-entree-stock/$', bdc_cyclos_views.payments_available_for_entree_stock),
    url(r'^entree-stock/$', bdc_cyclos_views.entree_stock),
    url(r'^sortie-stock/$', bdc_cyclos_views.sortie_stock),
    url(r'^change-euro-eusko/$', bdc_cyclos_views.change_euro_eusko),
    url(r'^reconversion/$', bdc_cyclos_views.reconversion),
    url(r'^bank-deposit/$', bdc_cyclos_views.bank_deposit),
    url(r'^cash-deposit/$', bdc_cyclos_views.cash_deposit),
    url(r'^sortie-caisse-eusko/$', bdc_cyclos_views.cash_deposit),
    url(r'^sortie-retour-eusko/$', bdc_cyclos_views.sortie_retour_eusko),
    url(r'^depot-eusko-numerique/$', bdc_cyclos_views.depot_eusko_numerique),
    url(r'^retrait-eusko-numerique/$', bdc_cyclos_views.retrait_eusko_numerique),
    url(r'^bdc-change-password/$', bdc_cyclos_views.bdc_change_password),

    # Endpoints for Gestion Interne
    url(r'^sortie-coffre/$', gi_views.sortie_coffre),
    url(r'^payments-available-entree-coffre/$', gi_views.payments_available_for_entree_coffre),
    url(r'^entree-coffre/$', gi_views.entree_coffre),
    url(r'^payments-available-entrees-euro/$', gi_views.payments_available_for_entrees_euro),
    url(r'^validate-entrees-euro/$', gi_views.validate_history),
    url(r'^payments-available-entrees-eusko/$', gi_views.payments_available_for_entrees_eusko),
    url(r'^validate-entrees-eusko/$', gi_views.validate_history),
    url(r'^payments-available-banques/$', gi_views.payments_available_for_banques),
    url(r'^validate-banques-rapprochement/$', gi_views.validate_history),
    url(r'^validate-banques-virement/$', gi_views.validate_banques_virement),
]

urlpatterns += router.urls
