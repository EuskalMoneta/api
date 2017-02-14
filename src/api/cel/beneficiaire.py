from django.forms.models import model_to_dict
from rest_framework import status, viewsets
from rest_framework.decorators import list_route
from rest_framework.response import Response

from cel import models, serializers


class BeneficiaireViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'delete']
    serializer_class = serializers.BeneficiaireSerializer

    def get_queryset(self):
        return models.Beneficiaire.objects.filter(owner=self.request.user)

    @list_route(methods=['get'])
    def search(self, request, *args, **kwargs):
        # Cyclos search
        res = models.Beneficiaire.objects.get(number=request.query_params['number'])
        assert res, False
        if res:
            return res
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            obj = models.Beneficiaire.objects.get(cyclos_id=serializer.data['cyclos_id'])
            obj.save()

            return Response(model_to_dict(obj), status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
