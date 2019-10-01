from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from cel.models import Mandat
from cel.serializers import MandatSerializer
from cyclos_api import CyclosAPI, CyclosAPIException


def get_current_user_account_number(request):
    """
    Renvoie le numéro de compte de l'utilisateur courant (i.e. l'utilisateur qui a fait la requête).
    """
    try:
        cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
    except CyclosAPIException:
        return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)
    accounts_summaries_data = cyclos.post(method='account/getAccountsSummary', data=[cyclos.user_id, None])
    return accounts_summaries_data['result'][0]['number']


class MandatViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les mandats.

    list() et retrieve() sont fournis par ModelViewSet et utilisent serializer_class et get_queryset().
    On utilise http_method_names pour limiter les méthodes disponibles (interdire PATCH, PUT, DELETE).
    """
    serializer_class = MandatSerializer
    http_method_names = ['get', 'post']

    def get_queryset(self):
        queryset = Mandat.objects.all()
        type = self.request.query_params.get('type', None)
        if type == 'debiteur':
            queryset = queryset.filter(numero_compte_debiteur=get_current_user_account_number(self.request))
        elif type == 'crediteur':
            queryset = queryset.filter(numero_compte_crediteur=get_current_user_account_number(self.request))
        return queryset

    def create(self, request):
        """
        Créer un mandat.

        C'est le créditeur qui crée le mandat, en donnant le numéro de compte du débiteur.
        """
        serializer = MandatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Pour avoir le nom du débiteur, on fait une recherche dans Cyclos par son numéro de compte.
        try:
            cyclos = CyclosAPI(token=request.user.profile.cyclos_token, mode='cel')
        except CyclosAPIException:
            return Response({'error': 'Unable to connect to Cyclos!'}, status=status.HTTP_400_BAD_REQUEST)
        data = cyclos.post(method='user/search', data={'keywords': serializer.validated_data['numero_compte_debiteur']})
        debiteur = data['result']['pageItems'][0]

        # Enregistrement du mandat en base de données.
        # Le créditeur est l'utilisateur courant. On récupère son numéro de compte dans Cyclos.
        mandat = serializer.save(
            nom_debiteur=debiteur['display'],
            numero_compte_crediteur=get_current_user_account_number(request),
            nom_crediteur=cyclos.user_profile['result']['display']
        )

        # TODO: notification par email au débiteur

        # Le mandat créé est envoyé dans la réponse.
        serializer = MandatSerializer(mandat)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """
        Valider un mandat.

        Un mandat ne peut être validé que s'il est en attente de validation, et uniquement par son débiteur.
        """
        mandat = self.get_object()
        if mandat.statut == Mandat.EN_ATTENTE and get_current_user_account_number(
                self.request) == mandat.numero_compte_debiteur:
            mandat.statut = Mandat.VALIDE
            mandat.save()
            # TODO: notification par email au créditeur
            serializer = MandatSerializer(mandat)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """
        Refuser un mandat.

        Un mandat ne peut être refusé que s'il est en attente de validation, et uniquement par son débiteur.
        """
        mandat = self.get_object()
        """
        Valider un mandat.
        """
        if mandat.statut == Mandat.EN_ATTENTE and get_current_user_account_number(
                self.request) == mandat.numero_compte_debiteur:
            mandat.statut = Mandat.REFUSE
            mandat.save()
            # TODO: notification par email au créditeur
            serializer = MandatSerializer(mandat)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'])
    def revoquer(self, request, pk=None):
        """
        Révoquer un mandat.

        Un mandat ne peut être révoqué que s'il est valide, et uniquement par son débiteur.
        """
        mandat = self.get_object()
        if mandat.statut == Mandat.VALIDE and get_current_user_account_number(
                self.request) == mandat.numero_compte_debiteur:
            mandat.statut = Mandat.REVOQUE
            mandat.save()
            # TODO: notification par email au créditeur
            serializer = MandatSerializer(mandat)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)
