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
