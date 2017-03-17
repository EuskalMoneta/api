from django.utils.translation import ugettext as _
from rest_framework import serializers


class ArrayOptionsSerializer(serializers.Serializer):

    options_recevoir_actus = serializers.CharField(read_only=True)
    options_asso_saisie_libre = serializers.CharField(read_only=True)


class MemberSerializer(serializers.Serializer):

    id = serializers.CharField(read_only=True)
    login = serializers.CharField()
    civility_id = serializers.ChoiceField(
        [('MR', _('Monsieur')), ('MME', _('Madame'))]
    )
    lastname = serializers.CharField()
    firstname = serializers.CharField()
    birth = serializers.CharField()
    address = serializers.CharField()
    zip = serializers.CharField()
    town = serializers.CharField()
    state = serializers.CharField(read_only=True)
    state_id = serializers.CharField(read_only=True)
    country = serializers.CharField(read_only=True)
    country_id = serializers.CharField()
    phone = serializers.CharField(allow_blank=True, required=False)
    phone_perso = serializers.CharField(allow_blank=True, read_only=True, required=False)
    phone_mobile = serializers.CharField(allow_blank=True, read_only=True, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    array_options = ArrayOptionsSerializer(read_only=True)  # contient le champ "newsletter": (recevoir_actus)
    options_recevoir_actus = serializers.CharField(write_only=True)
    # Ajouter association parainée
    options_asso_saisie_libre = serializers.CharField(write_only=True, required=False)
    fk_asso = serializers.CharField(required=False)
    fk_asso2 = serializers.CharField(required=False)

    # Donées fixes lors de l'ajout d'un adhérent:
    # Mis en read_only car données gérées par l'API elle même (en dur)
    typeid = serializers.CharField(read_only=True)  # adherent_type = 3: particulier
    type = serializers.CharField(read_only=True)  # type adherent sous forme de string
    morphy = serializers.CharField(read_only=True)
    statut = serializers.CharField(read_only=True)
    public = serializers.CharField(read_only=True)


class MemberPartialSerializer(serializers.Serializer):

    login = serializers.CharField(allow_blank=True, required=False)
    lastname = serializers.CharField(allow_blank=True, required=False)
    firstname = serializers.CharField(allow_blank=True, required=False)
    birth = serializers.CharField(allow_blank=True, required=False)
    address = serializers.CharField(allow_blank=True, required=False)
    zip = serializers.CharField(allow_blank=True, required=False)
    town = serializers.CharField(allow_blank=True, required=False)
    state = serializers.CharField(read_only=True, allow_blank=True, required=False)
    state_id = serializers.CharField(read_only=True, allow_blank=True, required=False)
    country = serializers.CharField(read_only=True, allow_blank=True, required=False)
    country_id = serializers.CharField(allow_blank=True, required=False)
    phone = serializers.CharField(allow_blank=True, required=False)
    phone_perso = serializers.CharField(allow_blank=True, read_only=True, required=False)
    phone_mobile = serializers.CharField(allow_blank=True, read_only=True, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    array_options = ArrayOptionsSerializer(read_only=True)  # contient le champ "newsletter": (recevoir_actus)
    options_recevoir_actus = serializers.CharField(write_only=True, allow_blank=True, required=False)
    # Ajouter association parainée
    options_asso_saisie_libre = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Langue
    options_langue = serializers.CharField(write_only=True, required=False, allow_blank=True)
    fk_asso = serializers.CharField(required=False, allow_blank=True)
    fk_asso2 = serializers.CharField(required=False, allow_blank=True)

    # Donées fixes lors de l'ajout d'un adhérent:
    # Mis en read_only car données gérées par l'API elle même (en dur)
    typeid = serializers.CharField(read_only=True)  # adherent_type = 3: particulier
    type = serializers.CharField(read_only=True)  # type adherent sous forme de string
    morphy = serializers.CharField(read_only=True)
    statut = serializers.CharField(read_only=True)
    public = serializers.CharField(read_only=True)


class MembersSubscriptionsSerializer(serializers.Serializer):
    start_date = serializers.CharField(read_only=True)
    end_date = serializers.CharField(read_only=True)
    amount = serializers.IntegerField()
    payment_mode = serializers.CharField(write_only=True)
    label = serializers.CharField(read_only=True)
    cyclos_id_payment_mode = serializers.CharField(write_only=True)
