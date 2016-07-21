from django import forms
from django.utils.translation import ugettext as _


class MemberForm(forms.Form):
    """ See also MemberSerializer(forms.Serializer) in api/members/serializers.py.
    """

    login = forms.CharField(label=_('Login'), widget=forms.TextInput(attrs={'data-eusko-input': 'login'}))
    civility_id = forms.ChoiceField(
        widget=forms.RadioSelect,
        choices=[('MR', _('Monsieur')), ('MME', _('Madame'))]
    )
    lastname = forms.CharField(label=_('Nom'))
    firstname = forms.CharField(label=_('Prénom'))
    birth = forms.CharField(label=_('Date de naissance'))
    address = forms.CharField(label=_('Adresse'))
    zip = forms.CharField(label=_('Code postal'))
    town = forms.CharField(label=_('Ville'))
    state_id = forms.CharField(label=_('Département'))
    country_id = forms.CharField(label=_('Pays'))
    phone_perso = forms.CharField(label=_('Téléphone'), required=False)
    phone_mobile = forms.CharField(label=_('Téléphone mobile'), required=False)
    email = forms.EmailField(label=_('Email'), required=False)
    # array_options = ArrayOptionsSerializer()  # contient le champ "newsletter": (recevoir_actus)
    #     options_recevoir_actus = forms.BooleanField()
