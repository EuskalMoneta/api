from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import model_to_dict
from rest_framework import status, viewsets
from rest_framework.response import Response

from cel import models, serializers


class SecurityQAViewSet(viewsets.ViewSet):
    """
    A simple ViewSet for listing or retrieving Security QA for our users.
    """

    def list(self, request):
        queryset = models.SecurityQuestion.objects.filter(predefined=False)
        return Response([model_to_dict(item) for item in queryset])

    def retrieve(self, request, pk):
        if pk != 'me':
            return Response({'status': "You can't get Security QA for this user."},
                            status=status.HTTP_400_BAD_REQUEST)

        res = None
        try:
            res = models.SecurityAnswer.objects.get(owner=request.user)
        except ObjectDoesNotExist:
            pass

        return Response({'status': 'OK'}) if res else Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request):
        serializer = serializers.SecurityAnswerSerializer(data=request.data)

        if serializer.is_valid():
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

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
