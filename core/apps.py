from django.apps import AppConfig
from django.db.models.signals import post_migrate
def seed(sender, **k):
    from .models import StavZakazky, SazbaDPH
    from .models import Opravneni
    for old, new in (("V opravě", "Rozpracováno"), ("Hotová", "Opraveno"), ("Připravena k vyzvednutí", "Připraveno k vyzvednutí"), ("Vydaná", "Vydáno"), ("Zrušená", "Zrušeno")):
        if StavZakazky.objects.filter(nazev=old).exists() and not StavZakazky.objects.filter(nazev=new).exists(): StavZakazky.objects.filter(nazev=old).update(nazev=new)  # převod starých výchozích názvů
    for i, n in enumerate(["Nová", "Rozpracováno", "Čeká na schválení", "Čeká na díl", "Opraveno", "Připraveno k vyzvednutí", "Vydáno", "Zrušeno"]):
        StavZakazky.objects.get_or_create(nazev=n, defaults={"poradi": i})
    from .prava import PRAVA
    for kod, nazev, popis in PRAVA:  # oprávnění, která aplikace kontroluje (core/prava.py); výchozí role zakládá migrace 0018
        Opravneni.objects.get_or_create(kod=kod, defaults={"nazev": nazev, "popis": popis})
    if not SazbaDPH.objects.exists():
        for s in (21, 12, 0): SazbaDPH.objects.create(sazba=s)
    # údaje o firmě se nezakládají automaticky, vyplní je administrátor v průvodci prvním spuštěním (core/pruvodce.py)
    vestavene_sablony()


def vestavene_sablony():
    """Vestavěné šablony (Excel „standardní“ a HTML „jednoduchá“) pro každý typ dokumentu. Smazané/deaktivované se znovu nevytvářejí."""
    from .models import SablonaDokumentu as S
    from .sablony import typy
    from .sablony.prevod import soffice
    lo = bool(soffice())
    for kod, t in typy.REGISTR.items():
        nove = []
        for soubor, nazev, fmt in ((f"{kod}_firemni.xlsx", "firemní", "excel"), (f"{kod}_standardni.xlsx", "standardní", "excel"), ("jednoducha.html", "jednoduchá", "html")):
            if not S.objects.filter(typ_dokumentu=kod, vestavena=soubor).exists():
                nove.append(S.objects.create(typ_dokumentu=kod, vestavena=soubor, format=fmt, nazev=f"{t.nazev} – {nazev}"))
        if nove and not S.objects.filter(typ_dokumentu=kod, vychozi=True).exists():
            v = next((x for x in nove if x.format == ("excel" if lo else "html")), nove[0]); v.vychozi = True; v.save()  # první Excel = firemní
        # vestavěné Excely bez vlastního souboru znovu rozebrat (vzor se mohl aktualizací aplikace změnit)
        stare = list(S.objects.filter(typ_dokumentu=kod, format="excel", soubor="").exclude(vestavena="").exclude(pk__in=[x.pk for x in nove]))
        for s in nove + stare:
            if s.format == "excel":
                try:
                    from .sablony.renderery import renderer
                    s.mapovani = renderer(s).analyzuj(s, t); s.save(update_fields=["mapovani"])
                except Exception:
                    pass


CHYBA_EMAIL = "Zadejte platný e-mail, např. jan.novak@firma.cz."


class CoreConfig(AppConfig):
    name = "core"; verbose_name = "BusinessManager"
    def ready(self):
        post_migrate.connect(seed, sender=self)
        # Jednotná česká hláška pro špatný e-mail ve všech formulářích (zákazník, zaměstnanec, průvodce, firma, admin…)
        from django import forms
        forms.EmailField.default_error_messages = {**forms.EmailField.default_error_messages, "invalid": CHYBA_EMAIL}
