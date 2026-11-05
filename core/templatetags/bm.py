from django import template
from ..models import formatuj_telefon

register = template.Library()


@register.filter
def telefon(v):
    """Telefon vždy ve stejném tvaru: 604 851 237, +420 604 851 237."""
    return formatuj_telefon(v)
