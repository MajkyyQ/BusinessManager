from django.db import migrations


def zaloz_platby(apps, schema_editor):
    """Každá vystavená faktura má platbu: dosavadní faktury bez platby dostanou platbu „Čeká na zaplacení“."""
    Faktura = apps.get_model("core", "Faktura"); Platba = apps.get_model("core", "Platba")
    for f in Faktura.objects.filter(platba__isnull=True):
        Platba.objects.create(faktura=f, zakazka=f.zakazky.first(), stav="Čeká na zaplacení", castka=f.cena_s_dph)


class Migration(migrations.Migration):
    dependencies = [("core", "0015_vlastni_udalost")]
    operations = [migrations.RunPython(zaloz_platby, migrations.RunPython.noop)]
