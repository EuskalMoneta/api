import logging

from rest_framework import viewsets
from rest_framework.response import Response
from odoo_api import OdooAPI
from cyclos_api import CyclosAPI
from dolibarr_api import DolibarrAPI
from members.serializers import MemberSerializer
from pagination import CustomPagination

log = logging.getLogger()


class BaseAPIView(viewsets.ViewSet):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.cyclos = CyclosAPI()

        try:
            if self.model:
                self.dolibarr = DolibarrAPI(model=self.model)
                self.odoo = OdooAPI()
        except AttributeError:
            self.dolibarr = DolibarrAPI()

    def list(self, request, *args, **kwargs):
        objects = self.dolibarr.get(model=self.model, api_key=request.user.profile.dolibarr_token)
        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(objects, request)

        serializer = MemberSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request, pk=None):
        response = self.odoo.get(model='res.partner',domain=[[('is_main_profile', '=', True),('id', '=', pk)]])
        element = []
        for i in range (len(response)):
            element.append(
                {
                    "login": response[i]['ref'],
                    "societe": 'null',
                    "company": 'null',
                    "address": response[i]['street'],
                    "zip": response[i]['zip'],
                    "town": response[i]['town'],
                    "email": response[i]['email'],
                    "phone": response[i]['phone'],
                    "morphy": if response[i]['is_company']: 'mor' else 'phy',
                    "public": "0",
                    "statut": "1",
                    "note_public": 'null',
                    "note_private": 'null',
                    "typeid": "3",
                    "type": "Particulier",
                    "datefin": 1609369200,
                    "first_subscription_date": 1372502436,
                    "first_subscription_amount": "10.00000000",
                    "last_subscription_date": 1582279409,
                    "last_subscription_date_start": 1609369200,
                    "last_subscription_date_end": 1609369200,
                    "last_subscription_amount": "5.00000000",
                    "entity": "1",
                    "array_options": {
                        "options_recevoir_actus": "1",
                        "options_cotisation_offerte": 'null',
                        "options_notifications_validation_mandat_prelevement": "1",
                        "options_notifications_refus_ou_annulation_mandat_prelevement": "1",
                        "options_notifications_prelevements": "1",
                        "options_notifications_virements": "1",
                        "options_recevoir_bons_plans": "1",
                    },
                    "country": "France",
                    "country_id": "1",
                    "country_code": "FR",
                    "region_code": 'null',
                    "note": 'null',
                    "name": 'null',
                    "lastname": "Aureau",
                    "firstname": "Ana-Mari",
                    "civility_id": "MME",
                })
        return Response(element[0])


    def create(self, request):
        pass

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        pass

    def destroy(self, request, pk):
        return Response(self.dolibarr.delete(model=self.model, id=pk, api_key=request.user.profile.dolibarr_token))