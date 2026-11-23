"""Výchozí barvy stavů zakázek podle vzhledu Copper & Forest. Mění se jen stavy, které mají pořád původní výchozí barvu
z migrace 0019, takže barvy upravené v Nastavení → Stavy zakázek zůstanou. Barvy jsou opsané, ne importované z core.models."""
from django.db import migrations

PUVODNI = {"Nová": "#6c757d", "Rozpracováno": "#0d6efd", "Čeká na schválení": "#ffc107", "Čeká na díl": "#ffc107", "Opraveno": "#198754",
           "Připraveno k vyzvednutí": "#198754", "Vydáno": "#212529", "Zrušeno": "#dc3545"}
NOVE = {"Nová": "#6b7770", "Rozpracováno": "#b45309", "Čeká na schválení": "#eab308", "Čeká na díl": "#1e3a8a", "Opraveno": "#15803d",
        "Připraveno k vyzvednutí": "#0f766e", "Vydáno": "#1c241e", "Zrušeno": "#c5221f"}


def zmen(z, na):
    def f(apps, schema_editor):
        S = apps.get_model("core", "StavZakazky")
        for nazev, barva in na.items(): S.objects.filter(nazev=nazev, barva__iexact=z[nazev]).update(barva=barva)
    return f


class Migration(migrations.Migration):
    dependencies = [("core", "0023_platba_na_miste")]
    operations = [migrations.RunPython(zmen(PUVODNI, NOVE), zmen(NOVE, PUVODNI))]
