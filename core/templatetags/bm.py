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


@register.simple_tag
def barvy_stavu():
    """Styly štítků stavů zakázek (.bg-stav-<pk>) podle barev z Nastavení → Stavy zakázek; text černý nebo bílý podle kontrastu."""
    from django.utils.html import format_html_join
    from django.utils.safestring import mark_safe
    from ..models import StavZakazky
    pravidla = format_html_join("", ".bg-stav-{0}{{background-color:{1}!important;color:{2}!important}}",
                                ((s.pk, s.barva, s.barva_textu) for s in StavZakazky.objects.only("pk", "barva") if s.barva and s.barva[0] == "#"))
    return mark_safe(f"<style>{pravidla}</style>")
