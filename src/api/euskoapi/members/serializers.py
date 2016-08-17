from django.utils.translation import ugettext as _
from rest_framework import serializers


class ArrayOptionsSerializer(serializers.Serializer):

    options_recevoir_actus = serializers.CharField(read_only=True)


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
    phone = serializers.CharField(allow_null=True)
    phone_perso = serializers.CharField(allow_null=True, read_only=True)
    phone_mobile = serializers.CharField(allow_null=True, read_only=True)
    email = serializers.EmailField(allow_blank=True)
    array_options = ArrayOptionsSerializer(read_only=True)  # contient le champ "newsletter": (recevoir_actus)
    options_recevoir_actus = serializers.CharField(write_only=True)
    # TODO Ajouter association parainée
    # fk_asso = serializers.CharField()

    # Donées fixes lors de l'ajout d'un adhérent:
    # Mis en read_only car données gérées par l'API elle même (en dur)
    typeid = serializers.CharField(read_only=True)  # adherent_type = 3: particulier
    type = serializers.CharField(read_only=True)  # type adherent sous forme de string
    morphy = serializers.CharField(read_only=True)
    statut = serializers.CharField(read_only=True)
    public = serializers.CharField(read_only=True)

    # DateTimeField example 2016-01-01 00:00:00
    # first_subscription_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    # first_subscription_amount = serializers.CharField()
    # last_subscription_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    # last_subscription_date_start = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    # last_subscription_date_end = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    # last_subscription_amount = serializers.CharField()


class MembersSubscriptionsSerializer(serializers.Serializer):
    start_date = serializers.CharField(read_only=True)
    end_date = serializers.CharField(read_only=True)
    amount = serializers.IntegerField()
    payment_mode = serializers.CharField(write_only=True)
    label = serializers.CharField()
