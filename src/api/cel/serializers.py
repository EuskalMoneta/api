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


class EuskokartLockSerializer(serializers.Serializer):

    id = serializers.CharField()


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
        model = models.Beneficiaire
        fields = ('id', 'owner', 'cyclos_id', 'cyclos_name', 'cyclos_account_number')


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


class OneTimeTransferSerializer(serializers.Serializer):

    beneficiaire = serializers.IntegerField()
    amount = serializers.FloatField()
    description = serializers.CharField()


class ReconvertEuskoSerializer(serializers.Serializer):

    amount = serializers.FloatField()
    description = serializers.CharField()


class UpdatePinSerializer(serializers.Serializer):

    # PINs are integers, but IntegerField() can't starts with 0, thus we needed to use CharField()
    pin1 = serializers.CharField()
    pin2 = serializers.CharField()
    ex_pin = serializers.CharField(required=False)


class MembersSubscriptionSerializer(serializers.Serializer):
    start_date = serializers.DateTimeField(format=None)
    end_date = serializers.DateTimeField(format=None)
    amount = serializers.IntegerField()
    label = serializers.CharField()


class ExecutePrelevementSerializer(serializers.Serializer):
    account = serializers.CharField()
    amount = serializers.CharField()
    description = serializers.CharField()
