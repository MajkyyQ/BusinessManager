from django import template
from ..models import formatuj_telefon

register = template.Library()


@register.filter
def telefon(v):
    """Telefon vždy ve stejném tvaru: 604 851 237, +420 604 851 237."""
    return formatuj_telefon(v)


@register.filter
def smi(url, user):
    """{% url 'edit' slug o.pk as u %}{% if u|smi:request.user %}…: tlačítko se ukáže jen tomu, kdo na akci má oprávnění."""
    from ..prava import smi as _smi
    return _smi(user, url)
