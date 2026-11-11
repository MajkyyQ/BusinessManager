"""Oprávnění aplikace a výchozí role (Zaměstnanec, Technik, Administrativa, Administrátor).

Stávající zaměstnanci dostanou roli Zaměstnanec (základní přístup), aby po aktualizaci nikdo nepřišel o přístup do aplikace.
Seznam je zde opsaný (ne importovaný z core.prava), aby migrace fungovala stejně i po budoucích změnách kódu."""
from django.db import migrations

PRAVA = [
    ("aplikace.pristup", "Základní přístup", "Pracovní plocha, prohlížení zakázek, zákazníků a zařízení. Zakládání a úprava zakázek, zápis práce, materiálu, fotek "
                                             "a příloh, založení nového zákazníka, kontaktu nebo zařízení a vytváření událostí v kalendáři."),
    ("zakazky.zmenit_stav", "Ruční změna stavu zakázky", "Přepnutí zakázky do libovolného stavu mimo běžný postup (Zahájit práci, Dokončit opravu…)."),
    ("zakaznici.upravit", "Úprava zákazníků a zařízení", "Úprava už založených zákazníků, kontaktních osob a zařízení."),
    ("kalendar.upravit", "Úprava kalendáře", "Úprava a mazání událostí v kalendáři, i těch, které vytvořil někdo jiný. Svoje události může upravit každý."),
    ("nabidky.spravovat", "Nabídky a objednávky", "Vytváření a úprava nabídek a přijatých objednávek. Zpřístupní i sekci Dokumenty a ceny v dokladech."),
    ("faktury.spravovat", "Faktury a platby", "Vystavení faktury, označení zaplacení, platby a přijaté faktury. Zpřístupní i sekci Dokumenty a ceny v dokladech."),
    ("zaznamy.mazat", "Mazání a deaktivace", "Mazání a deaktivace záznamů (zakázky, zákazníci, zařízení, doklady…). Smazat vlastní řádek práce, materiálu nebo fotku u zakázky smí každý."),
    ("nastaveni.spravovat", "Nastavení", "Údaje o firmě, DPH, číslování a šablony dokumentů, katalogy, zaměstnanci, role a zálohy."),
]
ROLE = [
    ("Zaměstnanec", ["aplikace.pristup"], False, "Základní přístup. Dostane ji automaticky každý nový zaměstnanec."),
    ("Technik", ["aplikace.pristup", "zakazky.zmenit_stav", "kalendar.upravit"], False, "Opravy: zakázky, práce, materiál a ruční změna stavu zakázky."),
    ("Administrativa", ["aplikace.pristup", "zakazky.zmenit_stav", "zakaznici.upravit", "kalendar.upravit", "nabidky.spravovat", "faktury.spravovat"], False,
     "Kancelář: zákazníci, nabídky, faktury a platby."),
    ("Administrátor", [], True, "Smí všechno včetně mazání a Nastavení."),
]


def vytvor(apps, schema_editor):
    Opravneni = apps.get_model("core", "Opravneni"); Role = apps.get_model("core", "Role"); Zamestnanec = apps.get_model("core", "Zamestnanec")
    o = {}
    for kod, nazev, popis in PRAVA:
        x, nove = Opravneni.objects.get_or_create(kod=kod, defaults={"nazev": nazev, "popis": popis})
        if not nove and not x.popis: x.nazev = nazev; x.popis = popis; x.save()
        o[kod] = x
    for nazev, kody, admin, popis in ROLE:
        if Role.objects.filter(nazev=nazev).exists(): continue  # role se stejným názvem už si firma založila sama
        r = Role.objects.create(nazev=nazev, popis=popis, je_administrator=admin)
        r.opravneni.set([o[k] for k in kody])
    zakladni = Role.objects.get(nazev="Zaměstnanec"); zakladni.opravneni.add(o["aplikace.pristup"])
    for z in Zamestnanec.objects.all(): z.role.add(zakladni)


class Migration(migrations.Migration):
    dependencies = [("core", "0017_telefon_predvolba")]
    operations = [migrations.RunPython(vytvor, migrations.RunPython.noop)]
