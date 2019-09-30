from rest_framework import status, viewsets
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


class MandatViewSet(viewsets.ViewSet):

    def list(self, request):
        """
        Récupérer la liste des mandats de l'utilisateur courant, soit comme débiteur soit comme créditeur.
        """
        type = self.request.query_params.get('type', None)
        if type is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if type == 'debiteur':
            queryset = Mandat.objects.filter(numero_compte_debiteur=get_current_user_account_number(request))
        elif type == 'crediteur':
            queryset = Mandat.objects.filter(numero_compte_crediteur=get_current_user_account_number(request))
        serializer = MandatSerializer(queryset, many=True)
        return Response(serializer.data)

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
