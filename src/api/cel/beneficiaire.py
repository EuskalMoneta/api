from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import model_to_dict
from rest_framework import exceptions, status, viewsets
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
        res = None
        if not query or len(query) != 9:
            return exceptions.ParseError()

        try:
            cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')

            # user/search by account number only
            data = cyclos.post(method='user/search', data={'keywords': str(request.query_params['number'])})

            res = [{'label': item['display'], 'id': item['id']}
                   for item in data['result']['pageItems']][0]
        except (KeyError, IndexError, CyclosAPIException):
            Response(status=status.HTTP_204_NO_CONTENT)

        return Response(res) if res else Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            obj = models.Beneficiaire.objects.get(cyclos_id=serializer.data['cyclos_id'])
            obj.save()

            return Response(model_to_dict(obj), status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk, *args, **kwargs):
        try:
            models.Beneficiaire.objects.get(id=pk).delete()
        except ObjectDoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(status=status.HTTP_204_NO_CONTENT)
