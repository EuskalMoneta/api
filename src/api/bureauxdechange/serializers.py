from rest_framework import serializers


class BDCSerializer(serializers.Serializer):
    login = serializers.CharField()
    name = serializers.CharField()
