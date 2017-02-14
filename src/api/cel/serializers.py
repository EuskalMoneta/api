from rest_framework import serializers


class FirstConnectionSerializer(serializers.Serializer):

    login = serializers.CharField()
    email = serializers.EmailField()


class LostPasswordSerializer(serializers.Serializer):

    login = serializers.CharField()
    email = serializers.EmailField()


class HistorySerializer(serializers.Serializer):

    begin = serializers.DateTimeField(format=None)
    end = serializers.DateTimeField(format=None)
    description = serializers.CharField(required=False)


class ExportHistorySerializer(serializers.Serializer):

    begin = serializers.DateTimeField(format=None)
    end = serializers.DateTimeField(format=None)
    description = serializers.CharField(required=False)
    mode = serializers.CharField()


class ExportRIESerializer(serializers.Serializer):

    account = serializers.IntegerField()


class ValidTokenSerializer(serializers.Serializer):

    token = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()
