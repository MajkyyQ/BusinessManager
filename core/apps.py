from django.apps import AppConfig
from django.db.models.signals import post_migrate
def seed(sender, **k):
    from .models import StavZakazky, SazbaDPH, NastaveniFirmy
    from .models import Opravneni
    for old, new in (("V opravě", "Rozpracováno"), ("Hotová", "Opraveno"), ("Připravena k vyzvednutí", "Připraveno k vyzvednutí"), ("Vydaná", "Vydáno"), ("Zrušená", "Zrušeno")):
        if StavZakazky.objects.filter(nazev=old).exists() and not StavZakazky.objects.filter(nazev=new).exists(): StavZakazky.objects.filter(nazev=old).update(nazev=new)  # převod starých výchozích názvů
    for i, n in enumerate(["Nová", "Rozpracováno", "Čeká na schválení", "Čeká na díl", "Opraveno", "Připraveno k vyzvednutí", "Vydáno", "Zrušeno"]):
        StavZakazky.objects.get_or_create(nazev=n, defaults={"poradi": i})
    Opravneni.objects.get_or_create(kod="zakazky.zmenit_stav", defaults={"nazev": "Ruční změna stavu zakázky"})
    if not SazbaDPH.objects.exists():
        for s in (21, 12, 0): SazbaDPH.objects.create(sazba=s)
    if not NastaveniFirmy.objects.exists(): NastaveniFirmy.objects.create(nazev_firmy="Moje firma", vychozi_dph=21)
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
        for s in nove:
            if s.format == "excel":
                try:
                    from .sablony.renderery import renderer
                    s.mapovani = renderer(s).analyzuj(s, t); s.save(update_fields=["mapovani"])
                except Exception:
                    pass


class CoreConfig(AppConfig):
    name = "core"; verbose_name = "BusinessManager"
    def ready(self): post_migrate.connect(seed, sender=self)
