from rest_framework import serializers


class IOStockBDCSerializer(serializers.Serializer):

    amount = serializers.CharField()
    porteur = serializers.CharField()
    description = serializers.CharField()


class ChangeEuroEuskoSerializer(serializers.Serializer):

    amount = serializers.CharField()
    payment_mode = serializers.CharField()
    member_login = serializers.CharField()


class ReconversionSerializer(serializers.Serializer):

    amount = serializers.CharField()
    facture = serializers.CharField()
    member_login = serializers.CharField()
