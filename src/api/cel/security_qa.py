from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import model_to_dict
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import jwt

from cel import models, serializers


class SecurityQAViewSet(viewsets.ViewSet):

    permission_classes = (AllowAny, )

    def list(self, request):
        """
        This endpoint allow to retrieve all predefined SecurityQuestions.

        To use it, you *NEED* to be authenticated with an API Token.
        """
        # TODO Authentification
        queryset = models.SecurityQuestion.objects.filter(predefined=True)
        return Response([model_to_dict(item) for item in queryset])

    def retrieve(self, request, pk):
        """
        This endpoint allow to retrieve the SecurityQuestion our connected user as chosen.

        To use it, you *DON'T NEED* to be authenticated with an API Token,
        as its used to recover a lost password.
        """
        if pk != 'me':
            return Response({'status': "You can't get Security QA for this user."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = serializers.GetSecurityQuestionSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            token_data = jwt.decode(request.query_params['token'], settings.JWT_SECRET,
                                    issuer='lost-password', audience='guest')
        except jwt.InvalidTokenError:
            return Response({'error': 'Unable to read token!'}, status=status.HTTP_400_BAD_REQUEST)

        question = None
        try:
            answer = models.SecurityAnswer.objects.get(owner=token_data['login'])
            question = answer.question
        except ObjectDoesNotExist:
            pass

        if question:
            return Response({'question': model_to_dict(question)})
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request):
        """
        This endpoint allow to answer a SecurityQuestion (aka create a SecurityAnswer).

        To use it, you *NEED* to be authenticated with an API Token.
        """
        # TODO Authentification
        serializer = serializers.SecurityAnswerSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if serializer.data.get('question_id', False):
            # We got a question_id
            q = models.SecurityQuestion.objects.get(question_id=serializer.data['question_id'])

        elif serializer.data.get('question_text', False):
            # We didn't got a question_id, but a question_text: we need to create a new SecurityQuestion object
            q = models.SecurityQuestion.objects.create(question=serializer.data['question_text'])

        else:
            return Response({'status': ('Error: You need to provide at least one thse two fields: '
                                        'question_id or question_text')}, status=status.HTTP_400_BAD_REQUEST)

        res = models.SecurityAnswer.objects.create(owner=request.user, question=q)
        res.set_answer(raw_answer=serializer.data['answer'])
        res.save()

        return Response({'status': 'OK'}) if res else Response(status=status.HTTP_400_BAD_REQUEST)
