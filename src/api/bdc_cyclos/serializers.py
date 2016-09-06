from rest_framework import serializers


class EntreeStockBDCSerializer(serializers.Serializer):

    amount = serializers.CharField()
    porteur = serializers.CharField()
