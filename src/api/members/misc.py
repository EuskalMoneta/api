import copy
import datetime
import logging
import time

import arrow
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import activate, gettext as _

from misc import sendmail_euskalmoneta

log = logging.getLogger()


class Member:

    @staticmethod
    def validate_num_adherent(data):
        if (data.startswith("E") or data.startswith("Z")) and len(data) == 6:
            return True
        else:
            return False

    @staticmethod
    def validate_data(data, mode='create', base_options=None):
        """
        1. Dolibarr.llx_adherent.fk_adherent_type : typeid in the Dolibarr API = "3" (particulier)
        2. Dolibarr.llx_adherent.morphy = "phy" (personne physique)
        3. Dolibarr.llx_adherent.statut = "1" (1 = actif, 0 = brouillon, -1 = résilié)
        4. Dolibarr.llx_adherent.public = "0" (données privées)
        """
        if mode == 'create':
            data['typeid'] = "3"
            data['morphy'] = "phy"
            data['statut'] = "1"
            data['public'] = "0"

        try:
            data['birth'] = Member.validate_birthdate(data['birth'])
        except KeyError:
            pass

        if base_options:
            data = Member.validate_options(data, base_options)
        else:
            data = Member.validate_options(data)

        data = Member.validate_phones(data)

        return data

    @staticmethod
    def validate_birthdate(birthdate):
        """
        We need to validate the birthdate format.
        """
        datetime_birthdate = {}
        try:
            datetime_birthdate = datetime.datetime.strptime(birthdate, '%d/%m/%Y')
        except ValueError:
            raise ValueError("Incorrect data format, should be DD/MM/YYYY")

        res = int(time.mktime(datetime_birthdate.timetuple()))
        return res

    @staticmethod
    def send_mail_newsletter(login, profile, new_status, lang):
        """
        Envoi mail à Euskal Moneta lorsque l'option "Je souhaite être informé..." à été modifiée.
        """
        # Activate user pre-selected language
        activate(lang)

        # Translate subject & body for this email
        subject = _("Changement d'option pour l'abonnement aux actualités")
        body = render_to_string('mails/send_mail_newsletter.txt',
                                {'login': login,
                                 'profile_firstname': str(profile.firstname),
                                 'profile_lastname': str(profile.lastname),
                                 'profile_companyname': str(profile.companyname),
                                 'new_status': new_status})

        sendmail_euskalmoneta(subject=subject, body=body)

    @staticmethod
    def send_mail_change_auto(login, profile, mode, new_amount, comment, lang):
        """
        Envoi mail à Euskal Moneta lorsque le montant du change automatique à été modifié.
        """
        # Activate user pre-selected language
        activate(lang)

        if mode == 'delete':
            subject = _('Arrêt du change mensuel automatique')
        else:
            subject = _('Modification du montant du change mensuel automatique')

        body = render_to_string('mails/send_mail_change_auto.txt',
                                {'login': login, 'mode': mode,
                                 'profile_firstname': str(profile.firstname),
                                 'profile_lastname': str(profile.lastname),
                                 'profile_companyname': str(profile.companyname),
                                 'new_amount': new_amount, 'comment': comment})

        sendmail_euskalmoneta(subject=subject, body=body)

    @staticmethod
    def validate_options(data, source=None):
        """
        We don't want to create sub-objects on the front-side, thus our API have to deal with them.
        """
        try:
            data['array_options']
        except KeyError:
            data['array_options'] = copy.deepcopy(source) if source else {}

        try:
            # Subscribe newsletter field
            data['array_options'].update({'options_recevoir_actus': data['options_recevoir_actus']})
            del data['options_recevoir_actus']
        except KeyError:
            pass

        try:
            # If we are in "saisie libre"-mode: we use the options_asso_saisie_libre field,
            # if not we use the fk_asso field
            data['array_options'].update({'options_asso_saisie_libre': data['options_asso_saisie_libre']})
            del data['options_asso_saisie_libre']
        except KeyError:
            pass

        try:
            # If we are in "saisie libre"-mode: we use the options_asso_saisie_libre field,
            # if not we use the fk_asso field
            data['array_options'].update({'options_langue': data['options_langue']})
            del data['options_langue']
        except KeyError:
            pass

        try:
            data['array_options'].update({
                'options_prelevement_cotisation_montant': data['options_prelevement_cotisation_montant']})
            del data['options_prelevement_cotisation_montant']
        except KeyError:
            pass

        try:
            data['array_options'].update({
                'options_prelevement_cotisation_periodicite': data['options_prelevement_cotisation_periodicite']})
            del data['options_prelevement_cotisation_periodicite']
        except KeyError:
            pass

        try:
            data['array_options'].update({
                'options_prelevement_auto_cotisation_eusko': data['options_prelevement_auto_cotisation_eusko']})
            del data['options_prelevement_auto_cotisation_eusko']
        except KeyError:
            pass

        try:
            # Change automatique amount field
            data['array_options'].update(
                {'options_prelevement_change_montant': data['options_prelevement_change_montant']})
            del data['options_prelevement_change_montant']
        except KeyError:
            pass

        try:
            # Change automatique periodicite field
            data['array_options'].update(
                {'options_prelevement_change_periodicite': data['options_prelevement_change_periodicite']})
            del data['options_prelevement_change_periodicite']
        except KeyError:
            pass

        return data

    @staticmethod
    def validate_phones(data):
        """
        In Dolibarr, they are 3 fields for phonenumbers... We want to deal with them.
        1. 'phone' named "Téléphone pro"
        2. 'phone_mobile' named "Téléphone mobile"
        3. 'phone_perso' named "Téléphone personnel"
        """
        try:
            if data['phone']:
                if data['phone'].startswith(('06', '07')):
                    data['phone_mobile'] = data['phone']
                else:
                    data['phone_perso'] = data['phone']

                del data['phone']
        except KeyError:
            pass

        return data


class Subscription:

    @staticmethod
    def calculate_start_date(end_date, now=None):
        """
        Compute start_date for this subcription.
        To do this, we need the end date for the current sub of this *member* (if any).
        """
        res = ''
        if not now:
            now = arrow.now('Europe/Paris')

        # If this is a resub:
        if end_date:
            # We need to know which is the greater between those two years:
            # current year which is the var `now`
            # OR
            # (current subcrition ending year + 1 year)
            current_sub_ending_plus_one_year = arrow.get(end_date).to('Europe/Paris').replace(years=+1)

            if now.year > current_sub_ending_plus_one_year.year:
                res = now.replace(month=1, day=1, hour=0, minute=0, second=0).timestamp
            else:
                res = current_sub_ending_plus_one_year.replace(month=1, day=1, hour=0, minute=0, second=0).timestamp
        # This a new member:
        else:
            # We just need to take the current datetime
            res = now.timestamp

        return res

    @staticmethod
    def calculate_end_date(start_date, now=None):
        """
        Compute end_date for this subcription.
        To do this, we need the start date for this *sub*,
        which was calculated by _calculate_start_date() just before this method was called.
        """
        res = ''
        if not now:
            now = arrow.now('Europe/Paris')
        start_date_arrow = arrow.get(start_date).to('Europe/Paris')

        if start_date_arrow.year > now.year:
            res = start_date_arrow.replace(month=12, day=31, hour=23, minute=59, second=59).timestamp
        else:
            date_anticipated_sub = arrow.get("{}/{}".format(
                settings.DATE_COTISATION_ANTICIPEE, now.year), ['DD/MM/YYYY']).to('Europe/Paris')
            if now < date_anticipated_sub:
                res = now.replace(month=12, day=31, hour=23, minute=59, second=59).timestamp
            else:
                # note the years=+1, this does a relative addition like this: "now.year + 1"
                res = now.replace(years=+1, month=12, day=31, hour=23, minute=59, second=59).timestamp

        return res

    @staticmethod
    def calculate_label(end_date):
        """
        Compute end_date for this subcription.
        To do this, we need the end date for this *sub*,
        which was calculated by _calculate_end_date() just before this method was called.
        """
        return 'Adhésion/cotisation {}'.format(arrow.get(end_date).to('Europe/Paris').year)

    @staticmethod
    def account_and_type_from_payment_mode(payment_mode):
        """
        Simply match account, type and label for this payment mode.
        """
        accounts = {'Euro-LIQ': 2, 'Euro-CHQ': 2, 'Eusko-LIQ': 3}
        types = {'Euro-LIQ': 'LIQ', 'Euro-CHQ': 'CHQ', 'Eusko-LIQ': 'LIQ'}
        label = {'Euro-LIQ': 'Espèces', 'Euro-CHQ': 'Chèque', 'Eusko-LIQ': 'Espèces'}

        return accounts.get(payment_mode, ''), types.get(payment_mode, ''), label.get(payment_mode, '')
