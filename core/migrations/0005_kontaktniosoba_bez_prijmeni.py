# Pole "prijmeni" u kontaktní osoby už není potřeba (data jsou spojená v "jmeno" migrací 0004).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_kontaktniosoba_spojeni_jmena"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="kontaktniosoba",
            name="prijmeni",
        ),
    ]
