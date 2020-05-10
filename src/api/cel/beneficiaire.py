from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import model_to_dict
from rest_framework import exceptions, serializers as drf_serializers, status, viewsets
from rest_framework.decorators import list_route
from rest_framework.response import Response

from cel.models import Beneficiaire
from cel.serializers import BeneficiaireSerializer
from cyclos_api import CyclosAPI, CyclosAPIException


class BeneficiaireViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les mandats.

    list(), retrieve() et destroy() sont fournis par ModelViewSet et utilisent serializer_class et get_queryset().
    On utilise http_method_names pour limiter les méthodes disponibles (interdire PATCH, PUT, DELETE).
    """
    serializer_class = BeneficiaireSerializer
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        return Beneficiaire.objects.filter(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Créer un bénéficiaire en donnant son numéro de compte.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cyclos_account_number = serializer.validated_data['cyclos_account_number']

        # Si ce bénéficiaire existe déjà, on renvoie simplement OK.
        try:
            beneficiaire = Beneficiaire.objects.get(owner=self.request.user,
                                                    cyclos_account_number=cyclos_account_number)
            if beneficiaire:
                serializer = self.get_serializer(beneficiaire)
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Beneficiaire.DoesNotExist:
            pass

        # Le bénéficiaire n'existe pas, on va le créer.
        # On cherche dans Cyclos l'utilisateur correspondant au numéro de compte du bénéficiaire à créer.
        try:
            cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
        except CyclosAPIException:
            return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)
        data = cyclos.post(method='user/search', data={'keywords': cyclos_account_number})
        if data['result']['totalCount'] == 0:
            return Response({'error': "Ce numéro de compte n'existe pas."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        cyclos_user = data['result']['pageItems'][0]

        # Enregistrement du bénéficiaire en base de données.
        beneficiaire = serializer.save(
            owner=str(request.user),
            cyclos_id=cyclos_user['id'],
            cyclos_name=cyclos_user['display']
        )

        # Le bénéficiaire créé est envoyé dans la réponse.
        serializer = self.get_serializer(beneficiaire)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
