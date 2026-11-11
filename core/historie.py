"""Historie změn: čitelný zápis hodnot a jejich zobrazení (pole česky, „— → Barunka Placková“ místo QuerySetu)."""
import re
from datetime import date, datetime
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils import timezone
from django.utils.text import capfirst

PRAZDNE = "—"


def hodnota_text(v, pole=None):
    """Hodnota pole formuláře jako text pro historii. pole = pole formuláře (u výběru záznamu se z čísla dohledá název)."""
    if v is None or v == "": return ""
    if isinstance(v, bool): return "Ano" if v else "Ne"
    if isinstance(v, FieldFile): return v.name or ""
    if isinstance(v, datetime): return (timezone.localtime(v) if timezone.is_aware(v) else v).strftime("%d.%m.%Y %H:%M")
    if isinstance(v, date): return v.strftime("%d.%m.%Y")
    vyber = getattr(pole, "queryset", None)
    if isinstance(v, (models.QuerySet, list, tuple, set)):  # víc vybraných záznamů (zaměstnanci, zařízení…)
        return ", ".join(t for t in (hodnota_text(x, pole) for x in v) if t)
    if not isinstance(v, models.Model) and vyber is not None:  # výchozí hodnota výběru je jen číslo záznamu
        v = vyber.model._default_manager.filter(pk=v).first() or v
    elif getattr(pole, "choices", None) and not isinstance(v, models.Model):
        v = dict((str(k), l) for k, l in pole.choices if not isinstance(l, (list, tuple))).get(str(v), v)
    return str(v)


# Starší záznamy uložené jako text Pythonu: "[]", "<QuerySet [<Zamestnanec: Barunka Placková>]>", "[<Zarizeni: Motor>]"
_SEZNAM = re.compile(r"^(<QuerySet )?\[(.*)\]>?$", re.S)
_OBJEKT = re.compile(r"<\w+: (.*?)>(?=, <|$)", re.S)


def _cisty(s):
    s = (s or "").strip()
    m = _SEZNAM.match(s)
    if m and (m.group(1) or not m.group(2) or m.group(2).startswith("<")):
        s = ", ".join(_OBJEKT.findall(m.group(2).strip()))
    return {"None": "", "True": "Ano", "False": "Ne"}.get(s, s)


def zmena(h):
    """Text sloupce změny: „původní → nová“; prázdná strana jako pomlčka, u záznamu bez hodnot nic."""
    a, b = _cisty(h.puvodni_hodnota), _cisty(h.nova_hodnota)
    if not a and not b: return ""
    return f"{a or PRAZDNE} → {b or PRAZDNE}"


def pole_nazev(h):
    """Název pole tak, jak ho uživatel zná z formuláře (identifikacni_cislo → Identifikační číslo)."""
    n = h.pole or ""
    if not n: return ""
    from .views import POPISKY  # české popisky polí bez verbose_name (stejné jako ve formulářích)
    try: vn = str(apps.get_model("core", h.typ_objektu)._meta.get_field(n).verbose_name)
    except (LookupError, FieldDoesNotExist, ValueError): vn = n.replace("_", " ")
    if vn == n.replace("_", " ") and n in POPISKY: return POPISKY[n]
    return capfirst(vn)
