from django.forms.models import model_to_dict
from rest_framework import status, viewsets
from rest_framework.decorators import list_route
from rest_framework.response import Response

from cel import models, serializers
from cyclos_api import CyclosAPI, CyclosAPIException


class BeneficiaireViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'delete']
    serializer_class = serializers.BeneficiaireSerializer

    def get_queryset(self):
        return models.Beneficiaire.objects.filter(owner=self.request.user)

    @list_route(methods=['get'])
    def search(self, request, *args, **kwargs):
        query = request.query_params.get('number', False)
        if query and len(query) < 3:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
        except CyclosAPIException:
            return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)

        # user/search for group = 'Banques de dépot'
        data = cyclos.post(method='user/search', data={'keywords': str(request.query_params['number'])})
        res = [{'label': item['display'], 'value': item['id'], 'shortLabel': item['shortDisplay']}
               for item in data['result']['pageItems']]

        return res if res else Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            obj = models.Beneficiaire.objects.get(cyclos_id=serializer.data['cyclos_id'])
            obj.save()

            return Response(model_to_dict(obj), status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
