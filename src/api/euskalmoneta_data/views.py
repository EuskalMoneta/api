from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def payment_modes(request):
    """
    List all payment modes.
    """
    return Response([{'value': 'Euro-LIQ', 'label': 'Espèces (€)'},
                     {'value': 'Euro-CHQ', 'label': 'Chèque (€)'},
                     {'value': 'Eusko-LIQ', 'label': 'Eusko'}
                     ])
