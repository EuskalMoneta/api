import re
from django import template


register = template.Library()


###################
# STRINGS         #
###################

@register.filter()
def suffixe_k(value):
    x = re.search('[aeiouy]$',value)
    if (x is None):
        return value + 'ek'
    else:
        return value + 'k'

@register.filter()
def suffixe_en(value):
    x = re.search('[aeiouy]$',value)
    if (x is None):
        return value + '-en'
    else:
        return value + '-ren'

