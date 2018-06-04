from rest_framework import serializers


class SortieCoffreSerializer(serializers.Serializer):

    amount = serializers.CharField()
    porteur = serializers.CharField()
    bdc_dest = serializers.CharField()
    description = serializers.CharField()


class GenericHistoryValidationSerializer(serializers.Serializer):

    selected_payments = serializers.ListField()


class PaymentsAvailableBanqueSerializer(serializers.Serializer):

    bank_name = serializers.CharField()
    mode = serializers.CharField()


class ValidateBanquesVirementsSerializer(serializers.Serializer):

    bank_name = serializers.CharField()
    montant_total_cotisations = serializers.CharField()
    montant_total_ventes = serializers.CharField()
    montant_total_billet = serializers.CharField()
    montant_total_numerique = serializers.CharField()
    selected_payments = serializers.ListField()


class ValidateDepotsRetraitsSerializer(serializers.Serializer):

    selected_payments = serializers.ListField()
    montant_total_depots = serializers.CharField()
    montant_total_retraits = serializers.CharField()


class ValidateReconversionsSerializer(serializers.Serializer):

    selected_payments = serializers.ListField()
    montant_total_billets = serializers.CharField()
    montant_total_numerique = serializers.CharField()


class Calculate3PercentSerializer(serializers.Serializer):

    # Setting format=None indicates that Python date objects should be
    # returned by to_representation (instead of strings).
    # http://www.django-rest-framework.org/api-guide/fields/#datefield
    begin = serializers.DateField(format=None)
    end = serializers.DateField(format=None)


class ExportVersOdooSerializer(serializers.Serializer):
    begin = serializers.DateField(format=None)
    end = serializers.DateField(format=None)


class ChangeParVirementSerializer(serializers.Serializer):
    member_login = serializers.CharField()
    bank_transfer_reference = serializers.CharField()
    amount = serializers.FloatField()


class PaiementCotisationEuskoNumeriqueSerializer(serializers.Serializer):
    member_login = serializers.CharField()
    start_date = serializers.DateTimeField(format=None)
    end_date = serializers.DateTimeField(format=None)
    amount = serializers.FloatField()
    label = serializers.CharField()
