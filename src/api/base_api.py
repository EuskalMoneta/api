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
            if response[i]['is_company']:
                morphy = 'mor'
            else :
                morphy ='phy'

            element.append(
                {
                    "login": response[i]['ref'],
                    "societe": 'null',
                    "company": response[i]['name'],
                    "address": response[i]['street'],
                    "zip": response[i]['zip'],
                    "town": response[i]['city'],
                    "email": response[i]['email'],
                    "phone": response[i]['phone'],
                    "morphy": morphy,
                    "public": "0",
                    "statut": "1",
                    "id":response[i]['id'],
                    "note_public": 'null',
                    "note_private": 'null',
                    "typeid": response[i]['member_type_id'][0] if response[i]['member_type_id'] else 'null',
                    "type": response[i]['member_type_id'][1] if response[i]['member_type_id'] else 'null',
                    "datefin": 1609369200,
                    "first_subscription_date": 1372502436,
                    "first_subscription_amount": "10.00000000",
                    "last_subscription_date": 1582279409,
                    "last_subscription_date_start": 1609369200,
                    "last_subscription_date_end": 1609369200,
                    "last_subscription_amount": "5.00000000",
                    "entity": "1",
                    "array_options": {
                        "options_accepte_cgu_eusko_numerique": response[i]['accept_cgu_numerical_eusko'],
                        "options_documents_pour_ouverture_du_compte_valides": response[i]['numeric_wallet_document_valid'],
                        "options_accord_pour_ouverture_de_compte": 'oui' if response[i]['refuse_numeric_wallet_creation'] else 'non',
                    },
                    "country": response[i]['country_id'][1] if response[i]['country_id'] else 'null',
                    "country_id": "1",
                    "country_code": "FR",
                    "region_code": 'null',
                    "note": 'null',
                    "name": response[i]['name'],
                    "lastname": response[i]['lastname'],
                    "firstname": response[i]['firstname'],
                    "civility_id": response[i]['title'][1] if response[i]['title'] else 'null',
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