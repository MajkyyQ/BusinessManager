# Kontaktní osoba: jméno a příjmení se spojí do jednoho pole "jmeno" (stejně jako u zákazníka).
from django.db import migrations, models


def spoj_jmena(apps, schema_editor):
    KontaktniOsoba = apps.get_model("core", "KontaktniOsoba")
    for k in KontaktniOsoba.objects.all():
        cele = " ".join(x for x in ((k.jmeno or "").strip(), (k.prijmeni or "").strip()) if x)
        if cele != k.jmeno:
            k.jmeno = cele[:150]
            k.save(update_fields=["jmeno"])


def rozdel_jmena(apps, schema_editor):
    # Zpětný krok: první slovo zůstane ve "jmeno", zbytek se vrátí do "prijmeni".
    KontaktniOsoba = apps.get_model("core", "KontaktniOsoba")
    for k in KontaktniOsoba.objects.all():
        casti = (k.jmeno or "").split(" ", 1)
        if len(casti) == 2:
            k.jmeno, k.prijmeni = casti[0][:100], casti[1][:100]
            k.save(update_fields=["jmeno", "prijmeni"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_delky_poli_a_validace"),
    ]

    operations = [
        migrations.AlterField(
            model_name="kontaktniosoba",
            name="jmeno",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.RunPython(spoj_jmena, rozdel_jmena),
    ]
