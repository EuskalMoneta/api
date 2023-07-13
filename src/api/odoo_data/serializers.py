from rest_framework import serializers


class LoginSerializer(serializers.Serializer):

    username = serializers.CharField()
    password = serializers.CharField()


class GetUsergroupsSerializer(serializers.Serializer):

    username = serializers.CharField()


class GetUserDataSerializer(serializers.Serializer):

    username = serializers.CharField(required=False)


class VerifyUsergroupSerializer(serializers.Serializer):

    username = serializers.CharField()
    usergroup = serializers.CharField()
    api_key = serializers.CharField()
