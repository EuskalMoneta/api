import logging

import arrow

from ..members.misc import Subscription

log = logging.getLogger('console')

"""
Différents cas de tests à effectuer:

Nouvelle adhésion le 10 août 2016:
date de début = 10/08/2016
date de fin = 31/12/2016

Nouvelle adhésion le 15 novembre 2016:
date de début = 15/11/2016
date de fin = 31/12/2017

Un adhérent à jour jusqu'au 31/12/2015 renouvelle sa cotisation le 10 août 2016:
date de début = 01/01/2016
date de fin = 31/12/2016

Un adhérent à jour jusqu'au 31/12/2015 renouvelle sa cotisation le 15 novembre 2016:
date de début = 01/01/2016
date de fin = 31/12/2017

Un adhérent à jour jusqu'au 31/12/2014 renouvelle sa cotisation le 10 août 2016:
date de début = 01/01/2016
date de fin = 31/12/2016

Un adhérent à jour jusqu'au 31/12/2014 renouvelle sa cotisation le 15 novembre 2016:
date de début = 01/01/2016
date de fin = 31/12/2017

Un adhérent à jour jusqu'au 31/12/2016 renouvelle sa cotisation le 10 août 2016:
date de début = 01/01/2017
date de fin = 31/12/2017

Un adhérent à jour jusqu'au 31/12/2016 renouvelle sa cotisation le 15 novembre 2016:
date de début = 01/01/2017
date de fin = 31/12/2017
"""


def test_calculate_start_date_end_date():
    data = [('', arrow.get(2016, 8, 10).to('Europe/Paris'), '10/08/2016', '31/12/2016'),
            ('', arrow.get(2016, 11, 15).to('Europe/Paris'), '15/11/2016', '31/12/2017'),
            ('1451520000', arrow.get(2016, 8, 10).to('Europe/Paris'), '01/01/2016', '31/12/2016'),
            ('1451520000', arrow.get(2016, 11, 15).to('Europe/Paris'), '01/01/2016', '31/12/2017'),
            ('1419984000', arrow.get(2016, 8, 10).to('Europe/Paris'), '01/01/2016', '31/12/2016'),
            ('1419984000', arrow.get(2016, 11, 15).to('Europe/Paris'), '01/01/2016', '31/12/2017'),
            ('1483142400', arrow.get(2016, 8, 10).to('Europe/Paris'), '01/01/2017', '31/12/2017'),
            ('1483142400', arrow.get(2016, 11, 15).to('Europe/Paris'), '01/01/2017', '31/12/2017'),
            ]
    for item in data:
        _calculate_start_date_end_date(item)


def _calculate_start_date_end_date(item):
    start_date = Subscription.calculate_start_date(end_date=item[0], now=item[1])
    # print("start_date: {}".format(arrow.get(start_date).format('DD/MM/YYYY')))

    assert isinstance(start_date, int)
    assert arrow.get(start_date).to('Europe/Paris').format('DD/MM/YYYY') == item[2]

    end_date = Subscription.calculate_end_date(start_date=start_date, now=item[1])
    # print("end_date: {}".format(arrow.get(end_date).format('DD/MM/YYYY')))

    assert isinstance(end_date, int)
    assert arrow.get(end_date).to('Europe/Paris').format('DD/MM/YYYY') == item[3]
