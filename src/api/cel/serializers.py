from rest_framework import serializers

from cel import models


class FirstConnectionSerializer(serializers.Serializer):

    login = serializers.CharField()
    email = serializers.EmailField()
    langue = serializers.CharField(max_length=2)

    def validate_langue(self, value):
        if value not in ('eu', 'fr'):
            raise serializers.ValidationError("langue must be 'eu' or 'fr'")
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

    begin = serializers.DateTimeField(format=None)
    end = serializers.DateTimeField(format=None)
    description = serializers.CharField(required=False)
    mode = serializers.CharField()


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


class PredefinedSecurityQuestionSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.PredefinedSecurityQuestion
        fields = ('id', 'question', 'language')


class OneTimeTransferSerializer(serializers.Serializer):

    debit = serializers.IntegerField()
    beneficiaire = serializers.IntegerField()
    amount = serializers.FloatField()
    description = serializers.CharField()


class ReconvertEuskoSerializer(serializers.Serializer):

    debit = serializers.IntegerField()
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
