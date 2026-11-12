"""Barva stavu zakázky (Nastavení → Stavy zakázek). Stávající stavy dostanou barvu, kterou měly dosud napevno v kódu.
Barvy jsou zde opsané (ne importované z core.models), aby migrace fungovala stejně i po budoucích změnách kódu."""
import core.models
from django.db import migrations, models

BARVY = {"Nová": "#6c757d", "Rozpracováno": "#0d6efd", "Čeká na schválení": "#ffc107", "Čeká na díl": "#ffc107", "Opraveno": "#198754",
         "Připraveno k vyzvednutí": "#198754", "Vydáno": "#212529", "Zrušeno": "#dc3545"}


def nastav_barvy(apps, schema_editor):
    S = apps.get_model("core", "StavZakazky")
    for nazev, barva in BARVY.items(): S.objects.filter(nazev=nazev).update(barva=barva)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_opravneni_a_vychozi_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="stavzakazky",
            name="barva",
            field=models.CharField(default="#0dcaf0", help_text="Barva štítku stavu v přehledech, kanbanu a na pracovní ploše zakázky.",
                                   max_length=7, validators=[core.models.validuj_barvu], verbose_name="barva"),
        ),
        migrations.RunPython(nastav_barvy, migrations.RunPython.noop),
    ]
