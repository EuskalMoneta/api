from rest_framework import serializers

from cel import models


class FirstConnectionSerializer(serializers.Serializer):

    login = serializers.CharField()
    email = serializers.EmailField()
    language = serializers.CharField(max_length=2)

    def validate_language(self, value):
        if value not in ('eu', 'fr'):
            raise serializers.ValidationError("language must be 'eu' or 'fr'")
        return value


class LostPasswordSerializer(serializers.Serializer):

    login = serializers.CharField()
    email = serializers.EmailField()
    language = serializers.CharField(max_length=2)

    def validate_language(self, value):
        if value not in ('eu', 'fr'):
            raise serializers.ValidationError("language must be 'eu' or 'fr'")
        return value


class HistorySerializer(serializers.Serializer):

    begin = serializers.DateTimeField(format=None)
    end = serializers.DateTimeField(format=None)
    description = serializers.CharField(required=False)
    account = serializers.IntegerField(required=False)


class ExportHistorySerializer(serializers.Serializer):
    begin = serializers.DateField(format=None)
    end = serializers.DateField(format=None)


class ExportRIESerializer(serializers.Serializer):

    account = serializers.IntegerField()


class ValidFirstConnectionSerializer(serializers.Serializer):

    token = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()
    question = serializers.CharField()
    answer = serializers.CharField()


class ValidLostPasswordSerializer(serializers.Serializer):

    token = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()
    answer = serializers.CharField()


class SecurityAnswerSerializer(serializers.Serializer):

    question = serializers.CharField()
    answer = serializers.CharField()


class BeneficiaireSerializer(serializers.ModelSerializer):

    class Meta:
        """
        Pour créer un bénéficiaire, le seul champ nécessaire est 'cyclos_account_number'. Tous les autres champs sont en
        lecture seule et servent uniquement lors de la récupération d'un ou plusieurs bénéficiaires.
        """
        model = models.Beneficiaire
        fields = ['id', 'owner', 'cyclos_id', 'cyclos_name', 'cyclos_account_number']
        read_only_fields = ['owner', 'cyclos_id', 'cyclos_name']


class MandatSerializer(serializers.ModelSerializer):

    class Meta:
        """
        Pour créer un mandat, le seul champ nécessaire est 'numero_compte_debiteur'. Tous les autres champs sont en
        lecture seule et servent uniquement lors de la récupération d'un ou plusieurs mandats.
        """
        model = models.Mandat
        fields = ['id', 'numero_compte_debiteur', 'nom_debiteur', 'numero_compte_crediteur', 'nom_crediteur', 'statut',
                  'date_derniere_modif']
        read_only_fields = ['nom_debiteur', 'numero_compte_crediteur', 'nom_crediteur', 'statut', 'date_derniere_modif']


class PredefinedSecurityQuestionSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.PredefinedSecurityQuestion
        fields = ('id', 'question', 'language')


class ExecuteVirementSerializer(serializers.Serializer):
    account = serializers.CharField()
    amount = serializers.FloatField()
    description = serializers.CharField()


class ExecuteVirementAssoMlcSerializer(serializers.Serializer):
    amount = serializers.FloatField()
    description = serializers.CharField()


class ReconvertEuskoSerializer(serializers.Serializer):

    amount = serializers.FloatField()
    description = serializers.CharField()


class UpdatePinSerializer(serializers.Serializer):

    # PINs are integers, but IntegerField() can't starts with 0, thus we needed to use CharField()
    pin = serializers.CharField(max_length=4)


class ExecutePrelevementSerializer(serializers.Serializer):
    account = serializers.CharField()
    amount = serializers.FloatField()
    description = serializers.CharField()


class CreerCompteVeeSerializer(serializers.Serializer):
    lastname = serializers.CharField()
    firstname = serializers.CharField()
    email = serializers.EmailField()
    address = serializers.CharField()
    zip = serializers.CharField()
    town = serializers.CharField()
    country_id = serializers.IntegerField()
    phone = serializers.CharField()
    id_document = serializers.CharField()
    idcheck_report = serializers.CharField()
    birth = serializers.DateField()
    password = serializers.CharField()
    question = serializers.CharField()
    answer = serializers.CharField()
    pin_code = serializers.CharField()


class CreerCompteSerializer(CreerCompteVeeSerializer):
    iban = serializers.CharField()
    automatic_change_amount = serializers.IntegerField()
    sepa_document = serializers.CharField()
    subscription_amount = serializers.IntegerField()
    subscription_periodicity = serializers.IntegerField()
    asso_id = serializers.IntegerField(allow_null=True)
    asso_saisie_libre = serializers.CharField(allow_null=True)
    login = serializers.CharField(required=False)


class AdhererSerializer(serializers.Serializer):
    firstname = serializers.CharField()
    lastname = serializers.CharField()
    birth = serializers.DateField()
    email = serializers.EmailField()
    address = serializers.CharField()
    zip = serializers.CharField()
    town = serializers.CharField()
    country_id = serializers.IntegerField()
    phone = serializers.CharField()
    subscription_amount = serializers.IntegerField()
    subscription_periodicity = serializers.IntegerField()
    iban = serializers.CharField()
    sepa_document = serializers.CharField()
    asso_id = serializers.IntegerField(allow_null=True)
    asso_saisie_libre = serializers.CharField(allow_null=True)
    login = serializers.CharField(required=False)
