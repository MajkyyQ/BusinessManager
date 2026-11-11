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


@register.filter
def zmena(h):
    """Záznam historie: „Nová → Rozpracováno“, „— → Barunka Placková“ (i u starších záznamů s QuerySetem)."""
    from ..historie import zmena as _z
    return _z(h)


@register.filter
def pole_nazev(h):
    """Záznam historie: název pole česky, jako ve formuláři."""
    from ..historie import pole_nazev as _p
    return _p(h)
