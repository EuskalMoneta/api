""" euskalmoneta API URL Configuration """

from django.conf.urls import url
from rest_framework import routers

from bureauxdechange.views import BDCAPIView
from members.views import MembersAPIView, MembersSubscriptionsAPIView
from cel.beneficiaire import BeneficiaireViewSet
from cel.security_qa import SecurityQAViewSet

from auth_token import views as auth_token_views
import bdc_cyclos.views as bdc_cyclos_views
import cel.views as cel_views
import dolibarr_data.views as dolibarr_data_views
import euskalmoneta_data.views as euskalmoneta_data_views
import gestioninterne.views as gi_views
import gestioninterne.credits_comptes_prelevements_auto as credits_views


router = routers.SimpleRouter()
router.register(r'bdc', BDCAPIView, base_name='bdc')
router.register(r'members', MembersAPIView, base_name='members')
router.register(r'members-subscriptions', MembersSubscriptionsAPIView, base_name='members-subscriptions')
router.register(r'beneficiaires', BeneficiaireViewSet, base_name='beneficiaires')
router.register(r'securityqa', SecurityQAViewSet, base_name='securityqa')

urlpatterns = [
    # Auth token
    url(r'^api-token-auth/', auth_token_views.obtain_auth_token),

    # Dolibarr data, data we fetch from its API
    url(r'^login/$', dolibarr_data_views.login),
    url(r'^usergroups/$', dolibarr_data_views.get_usergroups),
    url(r'^verify-usergroup/$', dolibarr_data_views.verify_usergroup),
    url(r'^associations/$', dolibarr_data_views.associations),
    url(r'^countries/$', dolibarr_data_views.countries),
    url(r'^bdc-name/$', dolibarr_data_views.get_bdc_name),
    url(r'^member-name/$', dolibarr_data_views.get_member_name),
    url(r'^user-data/$', dolibarr_data_views.get_user_data),
    url(r'^username/$', dolibarr_data_views.get_username),
    url(r'^towns/$', dolibarr_data_views.towns_by_zipcode),

    # Euskal moneta data (hardcoded data we dont fetch from APIs)
    url(r'^payment-modes/$', euskalmoneta_data_views.payment_modes),
    url(r'^porteurs-eusko/$', euskalmoneta_data_views.porteurs_eusko),
    url(r'^deposit-banks/$', euskalmoneta_data_views.deposit_banks),

    # Cyclos data, data we fetch from/push to its API
    url(r'^accounts-summaries/(?P<login_bdc>[\w\-]+)?/?$', bdc_cyclos_views.accounts_summaries),
    url(r'^system-accounts-summaries/$', bdc_cyclos_views.system_accounts_summaries),
    url(r'^dedicated-accounts-summaries/$', bdc_cyclos_views.dedicated_accounts_summaries),
    url(r'^deposit-banks-summaries/$', bdc_cyclos_views.deposit_banks_summaries),
    url(r'^accounts-history/$', bdc_cyclos_views.accounts_history),
    url(r'^payments-available-entree-stock/$', bdc_cyclos_views.payments_available_for_entree_stock),
    url(r'^entree-stock/$', bdc_cyclos_views.entree_stock),
    url(r'^sortie-stock/$', bdc_cyclos_views.sortie_stock),
    url(r'^change-euro-eusko/$', bdc_cyclos_views.change_euro_eusko),
    url(r'^change-euro-eusko-numeriques/$', bdc_cyclos_views.change_euro_eusko_numeriques),
    url(r'^reconversion/$', bdc_cyclos_views.reconversion),
    url(r'^bank-deposit/$', bdc_cyclos_views.bank_deposit),
    url(r'^cash-deposit/$', bdc_cyclos_views.cash_deposit),
    url(r'^sortie-caisse-eusko/$', bdc_cyclos_views.cash_deposit),
    url(r'^sortie-retour-eusko/$', bdc_cyclos_views.sortie_retour_eusko),
    url(r'^depot-eusko-numerique/$', bdc_cyclos_views.depot_eusko_numerique),
    url(r'^retrait-eusko-numerique/$', bdc_cyclos_views.retrait_eusko_numerique),
    url(r'^change-password/$', bdc_cyclos_views.change_password),

    # Endpoints for Gestion Interne
    url(r'^banks-history/$', gi_views.payments_available_for_banques),
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
    url(r'^payments-available-depots-retraits/$', gi_views.payments_available_depots_retraits),
    url(r'^validate-depots-retraits/$', gi_views.validate_depots_retraits),
    url(r'^payments-available-reconversions/$', gi_views.payments_available_for_reconversions),
    url(r'^validate-reconversions/$', gi_views.validate_reconversions),
    url(r'^calculate-3-percent/$', gi_views.calculate_3_percent),
    url(r'^export-vers-odoo/$', gi_views.export_vers_odoo),
    url(r'^change-par-virement/$', gi_views.change_par_virement),
    url(r'^paiement-cotisation-eusko-numerique/$', gi_views.paiement_cotisation_eusko_numerique),

    # Crédit des comptes Eusko par prélèvement automatique
    url(r'^credits-comptes-prelevement-auto/import/(?P<filename>[^/]+)$', credits_views.import_csv),
    url(r'^credits-comptes-prelevement-auto/perform/$', credits_views.perform),
    url(r'^credits-comptes-prelevement-auto/delete/$', credits_views.delete),
    url(r'^credits-comptes-prelevement-auto/list/(?P<mode>[^/]+)$', credits_views.list),

    # Endpoints for Compte en Ligne
    url(r'^first-connection/$', cel_views.first_connection),
    url(r'^validate-first-connection/$', cel_views.validate_first_connection),
    url(r'^lost-password/$', cel_views.lost_password),
    url(r'^validate-lost-password/$', cel_views.validate_lost_password),

    url(r'^payments-available-history-adherent/$', cel_views.payments_available_for_adherents),
    url(r'^account-summary-adherents/$', cel_views.account_summary_for_adherents),
    url(r'^export-history-adherent/$', cel_views.export_history_adherent),
    url(r'^export-rie-adherent/$', cel_views.export_rie_adherent),
    url(r'^has-account/$', cel_views.has_account),
    url(r'^one-time-transfer/$', cel_views.one_time_transfer),
    url(r'^reconvert-eusko/$', cel_views.reconvert_eusko),
    url(r'^user-rights/$', cel_views.user_rights),
    url(r'^accept-cgu/$', cel_views.accept_cgu),
    url(r'^refuse-cgu/$', cel_views.refuse_cgu),

    # euskokart
    url(r'^euskokart/$', cel_views.euskokart_list),
    url(r'^euskokart-block/$', cel_views.euskokart_block),
    url(r'^euskokart-unblock/$', cel_views.euskokart_unblock),
    url(r'^euskokart-pin/$', cel_views.euskokart_pin),
    url(r'^euskokart-upd-pin/$', cel_views.euskokart_update_pin),
    url(r'^member-cel-subscription/$', cel_views.members_cel_subscription),

]

urlpatterns += router.urls
