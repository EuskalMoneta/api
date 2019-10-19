from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import model_to_dict
from rest_framework import status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
import jwt

from cel import models, serializers


class PredefinedSecurityQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This viewset allows to retrieve all the predefined security questions.

    There is no need to be authenticated to the API to use it because the list of security questions must be
    accessible when a user is initializing its password.
    """
    serializer_class = serializers.PredefinedSecurityQuestionSerializer
    pagination_class = None
    permission_classes = (AllowAny, )

    def get_queryset(self):
        """
        Optionally restricts the returned questions to a given language,
        by filtering against a `language` query parameter in the URL.
        """
        queryset = models.PredefinedSecurityQuestion.objects.all()
        language = self.request.query_params.get('language', None)
        if language is not None:
            queryset = queryset.filter(language=language)
        return queryset


class SecurityQAViewSet(viewsets.ViewSet):

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'partial_update']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def list(self, request):
        """
        Get the SecurityAnswer of the user making the request.
        """
        queryset = models.SecurityAnswer.objects.filter(owner=self.request.user)
        serializer = serializers.SecurityAnswerSerializer(queryset, many=True)
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        """
        Update the SecurityAnswer of the user making the request.
        """
        if pk != 'me':
            return Response({'status': "Only PATCH securityqa/me/ is allowed."},
                            status=status.HTTP_400_BAD_REQUEST)
        serializer = serializers.SecurityAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        security_answer = models.SecurityAnswer.objects.filter(owner=self.request.user)[0]
        security_answer.question = serializer.data['question']
        security_answer.set_answer(raw_answer=serializer.data['answer'])
        security_answer.save()
        return Response({'status': 'OK'})

    def retrieve(self, request, pk=None):
        """
        This endpoint allow to retrieve the SecurityAnswer our connected user has chosen.

        To use it, you *DON'T NEED* to be authenticated with an API Token,
        as it is used to recover a lost password.
        """
        if pk != 'me':
            return Response({'status': "You can't get Security QA for this user."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            token = request.query_params.get('token', False)
            if not token:
                raise jwt.InvalidTokenError

            token_data = jwt.decode(token, settings.JWT_SECRET,
                                    issuer='lost-password', audience='guest')
            login = token_data['login']
        except jwt.InvalidTokenError:
            if request.user:
                login = str(request.user)
            else:
                return Response({'error': 'Unable to read token!'}, status=status.HTTP_400_BAD_REQUEST)

        answer = None
        try:
            answer = models.SecurityAnswer.objects.get(owner=login)
        except ObjectDoesNotExist:
            pass

        if answer:
            return Response({'question': model_to_dict(answer)})
        else:
            return Response({'error': 'Unable to read security question!'}, status=status.HTTP_400_BAD_REQUEST)
