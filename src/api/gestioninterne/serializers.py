from rest_framework import serializers


class SortieCoffreSerializer(serializers.Serializer):
    amount = serializers.CharField()
    porteur = serializers.CharField()
    bdc_dest = serializers.CharField()
    description = serializers.CharField()


class GenericHistoryValidationSerializer(serializers.Serializer):
    selected_payments = serializers.ListField()
