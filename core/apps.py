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
class CoreConfig(AppConfig):
    name = "core"; verbose_name = "BusinessManager"
    def ready(self): post_migrate.connect(seed, sender=self)
