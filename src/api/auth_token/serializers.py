import logging

from rest_framework import serializers

from auth_token.authentication import authenticate


log = logging.getLogger(__name__)


class AuthTokenSerializer(serializers.Serializer):
    username = serializers.CharField(label="Username")
    password = serializers.CharField(label="Password")

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            log.debug('user:{} password:{}'.format(username, password))
            user = authenticate(username, password)
            log.debug('USER {}'.format(user))
            if user:
                if not user.is_active:
                    msg = 'User account is disabled.'
                    raise serializers.ValidationError(msg)
            else:
                msg = 'Unable to log in with provided credentials.'
                raise serializers.ValidationError(msg)
        else:
            msg = 'Must include "username" and "password".'
            raise serializers.ValidationError(msg)

        attrs['user'] = user
        return attrs
