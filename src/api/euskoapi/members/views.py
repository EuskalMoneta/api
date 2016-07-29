import datetime
import logging

from rest_framework import status
from rest_framework.response import Response

from base_api import BaseAPIView
from members.serializers import MemberSerializer

log = logging.getLogger()


class MembersAPIView(BaseAPIView):

    def __init__(self, **kwargs):
        super(MembersAPIView, self).__init__(model='members')

    def create(self, request):
        data = request.data
        serializer = MemberSerializer(data=data)
        if serializer.is_valid():  # raise_exception=True ?
            data = self._validate_data(data)
        else:
            log.critical(serializer.errors)

        response_obj = self.dolibarr.post(model=self.model, data=data)
        log.info(response_obj)
        return Response(response_obj, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        return Response(self.dolibarr.patch(model=self.model))

    def partial_update(self, request, pk=None):
        return Response(self.dolibarr.patch(model=self.model))

    def _validate_data(self, data):
        """
        1. Dolibarr.llx_adherent.fk_adherent_type : typeid in the Dolibarr API = "3" (particulier)
        2. Dolibarr.llx_adherent.morphy = "phy" (personne physique)
        3. Dolibarr.llx_adherent.statut = "1" (1 = actif, 0 = brouillon, -1 = résilié)
        4. Dolibarr.llx_adherent.public = "0" (données privées)
        """
        data['typeid'] = "3"
        data['morphy'] = "phy"
        data['statut'] = "1"
        data['public'] = "0"
        data['birth'] = self._validate_birthdate(data['birth'])
        data = self._validate_options(data)
        data = self._validate_phones(data)

        return data

    def _validate_birthdate(self, birthdate):
        """
        We need to validate the birthdate format.
        """
        # validate format dateformat
        try:
            datetime.datetime.strptime(birthdate, '%d/%m/%Y')
        except ValueError:
            raise ValueError("Incorrect data format, should be DD-MM-YYYY")

        res = "{} 00:00:00".format(birthdate)

        try:
            datetime.datetime.strptime(res, '%d/%m/%Y %H:%M:%S')
        except ValueError:
            raise ValueError("Incorrect data format, should be DD-MM-YYYY HH:MM:SS")

        return res

    def _validate_options(self, data):
        """
        We don't want to create sub-objects on the front-side, thus our API have to deal with them.
        """
        data['array_options'] = {'options_recevoir_actus': data['options_recevoir_actus']}
        del data['options_recevoir_actus']

        return data

    def _validate_phones(self, data):
        """
        In Dolibarr, they are 3 field for phonenumbers... We want to deal with them.
        1. 'phone' named "Téléphone pro"
        2. 'phone_mobile' named "Téléphone mobile"
        3. 'phone_perso' named "Téléphone personnel"
        """
        if data['phone'] and data['phone'].startswith(('06', '07')):
            data['phone_mobile'] = data['phone']
            del data['phone']

        return data
