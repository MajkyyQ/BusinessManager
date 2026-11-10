from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from lxml import etree

from .models import Faktura, NastaveniFirmy, PolozkaFaktury, Zakaznik
from .sablony import isdoc

NS = {"i": isdoc.NS}


class RozdeleniAdresyTest(TestCase):
    def test_ulice_cislo_psc_mesto(self):
        self.assertEqual(isdoc.rozdel_adresu("Hlavní 123, 400 01 Ústí nad Labem"), ("Hlavní", "123", "Ústí nad Labem", "40001"))

    def test_cislo_s_lomitkem_a_vice_radku(self):
        self.assertEqual(isdoc.rozdel_adresu("Nová 12/3a\n11000 Praha 1"), ("Nová", "12/3a", "Praha 1", "11000"))

    def test_nerozpoznana_adresa_se_neztrati(self):
        self.assertEqual(isdoc.rozdel_adresu("Dolní Lhota"), ("Dolní Lhota", "", "", ""))
        self.assertEqual(isdoc.rozdel_adresu(""), ("", "", "", ""))

    def test_ucet(self):
        self.assertEqual(isdoc.rozdel_ucet("123-4567890/0800"), ("123-4567890", "0800", ""))
        self.assertEqual(isdoc.rozdel_ucet("CZ65 0800 0000 1920 0014 5399"), ("", "", "CZ6508000000192000145399"))


class ExportISDOCTest(TestCase):
    def setUp(self):
        NastaveniFirmy.objects.all().delete()
        NastaveniFirmy.objects.create(nazev_firmy="Servis s.r.o.", adresa="Dílenská 5, 400 01 Ústí nad Labem", ico="12345678", dic="CZ12345678",
                                      cislo_uctu="123456789/0100", mena="CZK")
        self.zak = Zakaznik.objects.create(firma="Odběratel a.s.", jmeno="Jan Novák", adresa="Hlavní 1, 110 00 Praha", ico="87654321", dic="CZ87654321")
        self.f = Faktura.objects.create(zakaznik=self.zak, datum_vystaveni=date(2026, 10, 27), datum_splatnosti=date(2026, 11, 10),
                                        datum_zdanitelneho_plneni=date(2026, 10, 27))
        PolozkaFaktury.objects.create(faktura=self.f, popis="Oprava čerpadla", mnozstvi=Decimal("2"), jednotka="hod", jednotkova_cena=Decimal("500"), sazba_dph=Decimal("21"))
        PolozkaFaktury.objects.create(faktura=self.f, popis="Těsnění", mnozstvi=Decimal("3"), jednotka="ks", jednotkova_cena=Decimal("10.50"), sazba_dph=Decimal("12"))
        self.f.refresh_from_db()

    def _xml(self):
        return etree.fromstring(isdoc.faktura_isdoc(self.f))

    def test_platne_podle_schematu_a_spravne_castky(self):
        x = self._xml()  # faktura_isdoc sama ověřuje proti XSD
        self.assertEqual(x.findtext("i:ID", namespaces=NS), self.f.cislo_faktury)
        self.assertEqual(len(x.findall("i:InvoiceLines/i:InvoiceLine", NS)), 2)
        self.assertEqual(len(x.findall("i:TaxTotal/i:TaxSubTotal", NS)), 2)
        self.assertEqual(x.findtext("i:LegalMonetaryTotal/i:TaxExclusiveAmount", namespaces=NS), "1031.50")
        self.assertEqual(x.findtext("i:LegalMonetaryTotal/i:PayableAmount", namespaces=NS), str(self.f.cena_s_dph.quantize(Decimal("0.01"))))
        self.assertEqual(x.findtext("i:TaxTotal/i:TaxAmount", namespaces=NS), "213.78")
        self.assertEqual(x.findtext("i:PaymentMeans/i:Payment/i:Details/i:BankCode", namespaces=NS), "0100")
        self.assertEqual(x.findtext("i:AccountingCustomerParty/i:Party/i:PostalAddress/i:PostalZone", namespaces=NS), "11000")

    def test_uuid_je_stabilni(self):
        self.assertEqual(self._xml().findtext("i:UUID", namespaces=NS), self._xml().findtext("i:UUID", namespaces=NS))

    def test_soukroma_osoba_bez_uctu_a_bez_polozek(self):
        NastaveniFirmy.objects.update(cislo_uctu="", dic="")
        z = Zakaznik.objects.create(jmeno="Petr Malý", adresa="")
        f = Faktura.objects.create(zakaznik=z, cena_bez_dph=Decimal("1000"), dph=Decimal("0"), cena_s_dph=Decimal("1000"))
        x = etree.fromstring(isdoc.faktura_isdoc(f))
        self.assertEqual(x.findtext("i:VATApplicable", namespaces=NS), "false")
        self.assertEqual(x.findtext("i:PaymentMeans/i:Payment/i:PaymentMeansCode", namespaces=NS), "10")
        self.assertEqual(x.findtext("i:LegalMonetaryTotal/i:PayableAmount", namespaces=NS), "1000.00")

    def test_stazeni_pres_adresu(self):
        self.client.force_login(User.objects.create_user("u", password="x"))
        r = self.client.get(reverse("dokument_isdoc", args=["faktura", self.f.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn(".isdoc", r["Content-Disposition"])
        self.assertEqual(self.client.get(reverse("dokument_isdoc", args=["nabidka", 1])).status_code, 404)


class PrijateFakturyTest(TestCase):
    """Import faktury od dodavatele z ISDOC, kalendář a označení zaplacení."""
    def setUp(self):
        NastaveniFirmy.objects.all().delete()
        # „dodavatel“ vystaví fakturu naší aplikací, tu pak importujeme jako přijatou
        NastaveniFirmy.objects.create(nazev_firmy="Velkoobchod Díly s.r.o.", adresa="Skladová 7, 602 00 Brno", ico="25596641", dic="CZ25596641",
                                      cislo_uctu="2400123456/2010", telefon="+420 777 111 222", email="fakturace@dily.cz", mena="CZK")
        z = Zakaznik.objects.create(firma="Můj servis s.r.o.", adresa="Dílenská 5, 400 01 Ústí nad Labem", ico="12345679")
        f = Faktura.objects.create(zakaznik=z, datum_vystaveni=date(2026, 10, 20), datum_splatnosti=date(2026, 11, 3), datum_zdanitelneho_plneni=date(2026, 10, 20))
        PolozkaFaktury.objects.create(faktura=f, popis="Ložisko 6204", mnozstvi=Decimal("4"), jednotkova_cena=Decimal("120"), sazba_dph=Decimal("21"))
        f.refresh_from_db(); self.cislo = f.cislo_faktury
        self.obsah = isdoc.faktura_isdoc(f)
        NastaveniFirmy.objects.update(nazev_firmy="Můj servis s.r.o.", ico="12345679", dic="", cislo_uctu="")
        self.client.force_login(User.objects.create_user("u", password="x"))

    def _nahraj(self, obsah, jmeno="faktura.isdoc"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post(reverse("prijata_faktura_import"), {"soubor": SimpleUploadedFile(jmeno, obsah)})

    def test_cteni_isdoc(self):
        d = isdoc.nacti(self.obsah)
        self.assertEqual(d["cislo_faktury"], self.cislo)
        self.assertEqual(d["dodavatel"]["ico"], "25596641")
        self.assertEqual(d["dodavatel"]["adresa"], "Skladová 7, 60200 Brno")
        self.assertEqual(d["cislo_uctu"], "2400123456/2010")
        self.assertEqual(d["cena_s_dph"], Decimal("580.80"))
        self.assertEqual(d["datum_splatnosti"], date(2026, 11, 3))
        self.assertEqual(d["polozky"], ["Ložisko 6204"])

    def test_import_dodavatel_kalendar_a_zaplaceni(self):
        from .models import Dodavatel, KalendarUdalost, PrijataFaktura
        r = self._nahraj(self.obsah)
        pf = PrijataFaktura.objects.get()
        self.assertRedirects(r, reverse("detail", args=["prijatafaktura", pf.pk]), fetch_redirect_response=False)
        self.assertEqual(Dodavatel.objects.get().nazev, "Velkoobchod Díly s.r.o.")
        self.assertEqual((pf.stav, pf.cena_bez_dph, pf.variabilni_symbol), ("Nezaplaceno", Decimal("480.00"), "".join(c for c in self.cislo if c.isdigit())))
        self.assertTrue(pf.soubor.name.endswith(".isdoc"))
        typy = set(KalendarUdalost.objects.filter(prijata_faktura=pf).values_list("typ", flat=True))
        self.assertEqual(typy, {"Přijatá faktura", "Splatnost faktury"})
        self.assertIn("NEZAPLACENO", KalendarUdalost.objects.get(prijata_faktura=pf, typ="Splatnost faktury").nazev)
        # stejná faktura podruhé -> žádná duplicita
        self._nahraj(self.obsah); self.assertEqual(PrijataFaktura.objects.count(), 1)
        # označení zaplacení
        self.client.post(reverse("prijata_faktura_zaplaceno", args=[pf.pk])); pf.refresh_from_db()
        self.assertEqual(pf.stav, "Zaplaceno"); self.assertIsNotNone(pf.datum_zaplaceni)
        self.assertIn("zaplaceno", KalendarUdalost.objects.get(prijata_faktura=pf, typ="Splatnost faktury").nazev)
        self.assertTrue(KalendarUdalost.objects.filter(prijata_faktura=pf, typ="Zaplaceno dodavateli").exists())
        for u in ("dokumenty", "kalendar"): self.assertEqual(self.client.get(reverse(u)).status_code, 200)
        self.assertContains(self.client.get(reverse("list", args=["prijatafaktura"])), self.cislo)
        pf.dodavatel.refresh_from_db(); self.assertContains(self.client.get(reverse("detail", args=["prijatafaktura", pf.pk])), "Zaplaceno")

    def test_isdocx_a_chybny_soubor(self):
        import io, zipfile
        from .models import PrijataFaktura
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z: z.writestr("faktura.isdoc", self.obsah); z.writestr("faktura.pdf", b"%PDF")
        self._nahraj(b.getvalue(), "faktura.isdocx"); self.assertEqual(PrijataFaktura.objects.count(), 1)
        r = self._nahraj(b"<html>nic</html>", "x.isdoc")
        self.assertEqual(r.status_code, 200); self.assertContains(r, "není faktura ve formátu ISDOC")


class IntegritniOmezeniTest(TestCase):
    """Omezení přidaná podle Silberschatz et al., Database System Concepts, kap. 4.4 a 6.5.2."""
    def setUp(self):
        self.zak = Zakaznik.objects.create(firma="Firma s.r.o.")

    def test_zakaznik_musi_mit_jmeno_nebo_firmu(self):
        from django.db import IntegrityError, transaction
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Zakaznik.objects.create()

    def test_kontakt_u_zakaznika_jen_jednou(self):
        from django.db import IntegrityError, transaction
        from .models import KontaktniOsoba, ZakaznikKontakt
        k = KontaktniOsoba.objects.create(jmeno="Petr")
        ZakaznikKontakt.objects.create(zakaznik=self.zak, kontakt=k)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            ZakaznikKontakt.objects.create(zakaznik=self.zak, kontakt=k)

    def test_vyctova_hodnota_mimo_seznam(self):
        from django.db import IntegrityError, transaction
        from .models import Platba
        Platba.objects.create(stav="Zaplaceno", zpusob="Hotově")
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Platba.objects.create(stav="Možná")

    def test_formular_hlasi_porusene_omezeni(self):
        from django.forms import modelform_factory
        F = modelform_factory(Zakaznik, fields=["jmeno", "firma"])
        f = F({"jmeno": "", "firma": ""})
        self.assertFalse(f.is_valid())
        self.assertIn("Vyplňte jméno nebo firmu.", str(f.errors))


class UdalostiKalendareTest(TestCase):
    def test_zmena_data_prijeti_posune_udalost(self):
        from datetime import datetime
        from django.utils import timezone
        from .models import KalendarUdalost, Zakazka
        z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), datum_prijeti=timezone.make_aware(datetime(2026, 10, 1, 9)))
        z.datum_prijeti = timezone.make_aware(datetime(2026, 10, 5, 9)); z.save()
        u = KalendarUdalost.objects.get(zakazka=z, typ="Přijetí zakázky")
        self.assertEqual(timezone.localtime(u.datum).day, 5)

    def test_udalost_faktury_ma_datum_vystaveni(self):
        from django.utils import timezone
        from .models import KalendarUdalost
        f = Faktura.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), datum_vystaveni=date(2026, 10, 20))
        f.datum_vystaveni = date(2026, 10, 22); f.save()
        u = KalendarUdalost.objects.get(faktura=f, typ="Fakturováno")
        self.assertEqual(timezone.localtime(u.datum).date(), date(2026, 10, 22))


class HlavniAkceZakazkyTest(TestCase):
    """Na stránce zakázky je zvýrazněn jeden doporučený další krok podle stavu zakázky."""
    def setUp(self):
        from .models import StavZakazky, Zakazka
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), stav=StavZakazky.objects.create(nazev="Nová"))

    def zvyraznene(self):
        import re
        html = self.client.get(reverse("plocha", args=[self.z.pk])).content.decode()
        return re.findall(r'class="btn btn-(?:primary|success)" href="[^"]*">([^<]+)</a>', html)

    def nastav(self, nazev):
        from .models import StavZakazky
        self.z.stav = StavZakazky.objects.get_or_create(nazev=nazev)[0]; self.z.save()

    def test_hlavni_akce_podle_stavu(self):
        from .models import Nabidka
        self.assertEqual(self.zvyraznene(), ["Zakázkový list"])
        self.nastav("Rozpracováno"); self.assertEqual(self.zvyraznene(), ["Přidat práci"])
        self.nastav("Opraveno"); self.assertEqual(self.zvyraznene(), ["Vytvořit nabídku"])
        Nabidka.objects.create(zakaznik=self.z.zakaznik).zakazky.add(self.z)
        self.assertEqual(self.zvyraznene(), ["Vytvořit fakturu"])
        Faktura.objects.create(zakaznik=self.z.zakaznik).zakazky.add(self.z)
        self.assertEqual(self.zvyraznene(), [])
        self.nastav("Vydáno"); self.assertEqual(self.zvyraznene(), [])


class OpravneniNastaveniTest(TestCase):
    """Nastavení vidí jen administrátor, šablony dokumentů kdokoli."""
    STRANKY = [("nastaveni", []), ("nastaveni_firma", []), ("nastaveni_zaloha", []), ("list", ["sazbadph"]), ("create", ["zamestnanec"]), ("list", ["historiezmen"])]

    def test_bezny_uzivatel_nastaveni_neotevre(self):
        self.client.force_login(User.objects.create_user("u", password="x"))
        for nazev, args in self.STRANKY:
            r = self.client.get(reverse(nazev, args=args))
            self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False, msg_prefix=nazev)
        r = self.client.get(reverse("dashboard"))
        self.assertNotContains(r, reverse("nastaveni"))
        self.assertEqual(self.client.get(reverse("sablony")).status_code, 200)
        self.assertEqual(self.client.get(reverse("list", args=["zakazka"])).status_code, 200)

    def test_admin_nastaveni_otevre(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("a", password="x", is_staff=True))
        self.assertContains(self.client.get(reverse("dashboard")), reverse("nastaveni"))
        for nazev, args in self.STRANKY:
            self.assertIn(self.client.get(reverse(nazev, args=args)).status_code, (200, 302), nazev)
        self.assertEqual(self.client.get(reverse("nastaveni")).status_code, 200)

    def test_styly_jsou_pribalene(self):
        self.client.force_login(User.objects.create_user("u", password="x"))
        r = self.client.get(reverse("dashboard"))
        self.assertNotContains(r, "cdn.jsdelivr.net"); self.assertNotContains(r, "unpkg.com")
        self.assertContains(r, "vendor/bootstrap.min.css"); self.assertContains(r, "vendor/htmx.min.js")


class PruvodcePrvnimSpustenimTest(TestCase):
    """Při prvním spuštění se nejdřív založí účet administrátora, pak firma."""
    def setUp(self):
        from .pruvodce import PrvniSpusteniMiddleware
        PrvniSpusteniMiddleware.hotovo = False
        NastaveniFirmy.objects.all().delete()

    def test_cely_pruvodce(self):
        self.assertRedirects(self.client.get("/"), reverse("pruvodce_ucet"))
        self.assertRedirects(self.client.get(reverse("login")), reverse("pruvodce_ucet"))
        r = self.client.post(reverse("pruvodce_ucet"), {"username": "sef", "first_name": "Jan", "last_name": "Novák", "email": "",
                                                        "password1": "Tajne-heslo-123", "password2": "Tajne-heslo-123"})
        self.assertRedirects(r, reverse("pruvodce_firma"))
        u = User.objects.get(username="sef"); self.assertTrue(u.is_superuser and u.is_staff)
        self.assertRedirects(self.client.get("/"), reverse("pruvodce_firma"))
        r = self.client.post(reverse("pruvodce_firma"), {"nazev_firmy": ""})
        self.assertEqual(r.status_code, 200); self.assertFalse(NastaveniFirmy.objects.exists())  # název je povinný
        r = self.client.post(reverse("pruvodce_firma"), {"nazev_firmy": "Servis Novák", "ico": "", "dic": "", "adresa": "", "telefon": "", "email": "", "web": ""})
        self.assertRedirects(r, reverse("dashboard"))
        f = NastaveniFirmy.objects.get(); self.assertEqual((f.nazev_firmy, f.vytvoril), ("Servis Novák", u)); self.assertIsNotNone(f.datum_vytvoreni)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertRedirects(self.client.get(reverse("pruvodce_ucet")), reverse("dashboard"), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("nastaveni")), "Firmu založil Jan Novák")

    def test_bezny_uzivatel_firmu_nezaklada(self):
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertRedirects(self.client.get(reverse("pruvodce_firma")), reverse("dashboard"), fetch_redirect_response=False)


class SQLInjectionTest(TestCase):
    """Typické útočné řetězce SQL injection nesmí obejít přihlášení ani rozbít vyhledávání.
    Django ORM předává vstupy databázi jako parametry dotazu, takže je databáze bere jako data, ne jako kód."""
    UTOKY = ["' OR '1'='1", "' OR 1=1 --", "admin'--", "admin' #", "' OR ''='", "\" OR \"\"=\"",
             "'; DROP TABLE auth_user; --", "' UNION SELECT username, password FROM auth_user --", "1' AND SLEEP(5) --"]

    def setUp(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.admin = User.objects.create_superuser("admin", "a@a.cz", "Spravne-heslo-123")
        Zakaznik.objects.create(jmeno="Jan Novák")

    def test_prihlaseni_nejde_obejit(self):
        for utok in self.UTOKY:
            for udaje in ({"username": utok, "password": utok}, {"username": "admin", "password": utok}, {"username": utok, "password": "cokoli"}):
                r = self.client.post(reverse("login"), udaje)
                self.assertEqual(r.status_code, 200, udaje)  # zůstane na přihlášení s chybou, nepřesměruje dál
                self.assertNotIn("_auth_user_id", self.client.session, udaje)
        self.assertTrue(User.objects.filter(username="admin").exists())  # tabulka uživatelů nebyla smazána
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)  # pořád nepřihlášen

    def test_spravne_heslo_funguje(self):
        r = self.client.post(reverse("login"), {"username": "admin", "password": "Spravne-heslo-123"})
        self.assertEqual(r.status_code, 302); self.assertIn("_auth_user_id", self.client.session)

    def test_heslo_smi_obsahovat_jakekoli_znaky(self):
        # heslo s uvozovkami a pomlčkami je jen text, uloží se jako hash a přihlášení funguje
        User.objects.create_user("pepa", password="x' OR '1'='1 --")
        self.assertTrue(self.client.login(username="pepa", password="x' OR '1'='1 --"))
        self.client.logout()
        self.assertFalse(self.client.login(username="pepa", password="' OR '1'='1"))

    def test_vyhledavani_nejde_zneuzit(self):
        self.client.force_login(self.admin)
        for utok in self.UTOKY:
            r = self.client.get(reverse("list", args=["zakaznik"]), {"q": utok})
            self.assertEqual(r.status_code, 200, utok); self.assertNotContains(r, "Jan Novák")
        self.assertContains(self.client.get(reverse("list", args=["zakaznik"]), {"q": "Novák"}), "Jan Novák")
        self.assertEqual(Zakaznik.objects.count(), 1)

    def test_razeni_jen_z_povolenych_sloupcu(self):
        # sloupec pro řazení z adresy se nepřipojuje do SQL, bere se jen z pevného seznamu (Silberschatz, s. 439)
        self.client.force_login(self.admin)
        for utok in self.UTOKY + ["cislo; DROP TABLE auth_user", "-(SELECT 1)"]:
            self.assertEqual(self.client.get(reverse("list", args=["zakazka"]), {"o": utok}).status_code, 200, utok)
        self.assertTrue(User.objects.exists())


class JednotneSeznamyTest(TestCase):
    """Seznamy: rychlý filtr stavu s počty, přepínač tabulka / kanban (Odoo), stejné rozložení stránky."""
    def setUp(self):
        from .models import StavZakazky, Zakazka, Zarizeni
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("a", password="x", is_staff=True))
        nova = StavZakazky.objects.get_or_create(nazev="Nová")[0]; self.diag = StavZakazky.objects.get_or_create(nazev="Diagnostika", defaults={"poradi": 2})[0]
        z = Zakaznik.objects.create(jmeno="Jana Fialová", typ_zakaznika="Soukromá osoba")
        d = Zarizeni.objects.create(zakaznik=z, vyrobce="Makita", typ="X1")
        for s in (nova, nova, self.diag): Zakazka.objects.create(zakaznik=z, stav=s).zarizeni.add(d)

    def test_filtr_stavu_s_pocty(self):
        r = self.client.get(reverse("list", args=["zakazka"]), {"st": "Diagnostika"})
        chips = {c[0]: (c[2], c[3]) for c in r.context["chips"]}
        self.assertEqual(chips["Vše"], (3, False)); self.assertEqual(chips["Nová"], (2, False)); self.assertEqual(chips["Diagnostika"], (1, True))
        self.assertEqual(len(r.context["rows"]), 1)
        self.assertContains(r, 'class="table table-sm table-hover bm-table"')  # pevné rozložení sloupců
        self.assertContains(r, 'id="bm-reset"')

    def test_kanban_se_pamatuje(self):
        url = reverse("list", args=["zakazka"])
        r = self.client.get(url, {"v": "kan"})
        sloupce = {c["s"]: len(c["items"]) for c in r.context["sloupce"] if c["items"]}
        self.assertEqual(sloupce, {"Nová": 2, "Diagnostika": 1})
        self.assertContains(r, "bm-board")
        self.assertEqual(self.client.get(url).context["pohled"], "kan")  # volba zůstane i bez parametru
        self.assertEqual(self.client.get(url, {"v": "tab"}).context["pohled"], "tab")
        self.assertContains(self.client.get(reverse("list", args=["zakaznik"]), {"v": "kan"}), "bm-cards")
        r = self.client.get(reverse("zarizeni_prehled"), {"v": "kan"})
        self.assertContains(r, "bm-cards"); self.assertContains(r, "Makita X1")

    def test_vsechny_sekce_maji_stejnou_hlavicku(self):
        for nazev, args in [("dashboard", []), ("list", ["zakazka"]), ("list", ["zakaznik"]), ("zarizeni_prehled", []), ("dokumenty", []), ("kalendar", []), ("nastaveni", [])]:
            self.assertContains(self.client.get(reverse(nazev, args=args)), 'class="bm-head', msg_prefix=nazev)

    def test_souhrn_dokladu(self):
        z = Zakaznik.objects.first()
        Faktura.objects.create(zakaznik=z, cena_s_dph=Decimal("100.50")); Faktura.objects.create(zakaznik=z, cena_s_dph=Decimal("20"))
        r = self.client.get(reverse("dokumenty"), {"typ": "faktura"})
        self.assertEqual(r.context["soucet"], [("120,50", "CZK")])
        self.assertContains(r, "Celkem 2 doklady")


class TvorbaDokladuZeZakazkyTest(TestCase):
    """Objednávka a faktura se zakládají jen přes formulář „ze zakázky“, ne přes starý obecný formulář."""
    def setUp(self):
        from .models import StavZakazky, Zakazka
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), stav=StavZakazky.objects.create(nazev="Nová"))

    def test_tlacitka_v_dokumentech(self):
        r = self.client.get(reverse("dokumenty"))
        self.assertContains(r, f'href="{reverse("objednavka_nova")}"'); self.assertContains(r, f'href="{reverse("faktura_nova")}"')
        self.assertNotContains(r, f'href="{reverse("create", args=["objednavka"])}"'); self.assertNotContains(r, f'href="{reverse("create", args=["faktura"])}"')

    def test_stary_formular_presmeruje(self):
        self.assertRedirects(self.client.get(reverse("create", args=["faktura"])), reverse("faktura_nova") + "?", fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("create", args=["objednavka"])), reverse("objednavka_nova") + "?", fetch_redirect_response=False)
        r = self.client.get(reverse("create", args=["objednavka"]), {"zakazky": self.z.pk})
        self.assertRedirects(r, reverse("objednavka_nova") + f"?zakazka={self.z.pk}", fetch_redirect_response=False)

    def test_nova_objednavka(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Objednavka
        self.assertEqual(self.client.get(reverse("objednavka_nova"), {"zakazka": self.z.pk}).status_code, 200)
        r = self.client.post(reverse("objednavka_nova"), {"zakaznik": self.z.zakaznik.pk, "zakazka": self.z.pk, "cislo": "OBJ-7", "predmet": "Oprava zařízení", "stredisko": "Údržba",
                                                          "text": "Objednáváme opravu elektronického zařízení.", "datum": "2026-11-04",
                                                          "soubor": SimpleUploadedFile("obj.pdf", b"%PDF-1.4")})
        self.assertRedirects(r, reverse("detail", args=["zakazka", self.z.pk]), fetch_redirect_response=False)
        o = Objednavka.objects.get(cislo_objednavky="OBJ-7")
        self.assertEqual(o.zakaznik, self.z.zakaznik); self.assertEqual(list(o.zakazky.all()), [self.z])
        self.assertEqual((o.predmet, o.stredisko, o.text), ("Oprava zařízení", "Údržba", "Objednáváme opravu elektronického zařízení."))
        self.assertEqual(list(o.priloha.zakazky.all()), [self.z])
        self.assertContains(self.client.get(reverse("plocha", args=[self.z.pk])), "Objednávka OBJ-7")

    def test_zakazky_nesou_zakaznika(self):
        html = self.client.get(reverse("objednavka_nova")).content.decode()
        self.assertIn(f'value="{self.z.pk}" data-zakaznik="{self.z.zakaznik_id}"', html)

    def test_objednavka_bez_zakazky_neprojde(self):
        from .models import Objednavka
        r = self.client.post(reverse("objednavka_nova"), {"zakaznik": self.z.zakaznik.pk, "cislo": "OBJ-9", "predmet": "Oprava"})
        self.assertEqual(r.status_code, 200); self.assertFalse(Objednavka.objects.exists())

    def test_objednavka_bez_zakaznika_nebo_s_cizi_zakazkou_neprojde(self):
        from .models import Objednavka
        self.assertEqual(self.client.post(reverse("objednavka_nova"), {"cislo": "OBJ-8"}).status_code, 200)
        cizi = Zakaznik.objects.create(jmeno="Petr")
        r = self.client.post(reverse("objednavka_nova"), {"zakaznik": cizi.pk, "zakazka": self.z.pk, "cislo": "OBJ-8", "predmet": "Oprava"})
        self.assertContains(r, "Zakázka patří jinému zákazníkovi."); self.assertFalse(Objednavka.objects.exists())


class PrijataFakturaRucneTest(TestCase):
    """Přijatá faktura zadaná ručně má vlastní formulář; starý obecný formulář na něj přesměruje."""
    def setUp(self):
        from .models import Dodavatel
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.dod = Dodavatel.objects.create(nazev="Elektro Díly s.r.o.", ico="11223344")

    def test_tlacitko_a_presmerovani(self):
        self.assertContains(self.client.get(reverse("dokumenty")), f'href="{reverse("prijata_faktura_rucne")}"')
        self.assertRedirects(self.client.get(reverse("create", args=["prijatafaktura"])), reverse("prijata_faktura_rucne"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("prijata_faktura_rucne")).status_code, 200)

    def test_ulozeni_dopocita_castku(self):
        from .models import KalendarUdalost, PrijataFaktura
        r = self.client.post(reverse("prijata_faktura_rucne"), {"dodavatel": self.dod.pk, "cislo_faktury": "FV-1", "datum_doruceni": "2026-11-04",
                                                                "datum_splatnosti": "2026-11-18", "cena_bez_dph": "100", "dph": "21", "mena": "CZK"})
        pf = PrijataFaktura.objects.get(cislo_faktury="FV-1")
        self.assertRedirects(r, reverse("detail", args=["prijatafaktura", pf.pk]), fetch_redirect_response=False)
        self.assertEqual(pf.cena_s_dph, Decimal("121")); self.assertEqual(pf.stav, "Nezaplaceno"); self.assertEqual(pf.vytvoril.username, "u")
        self.assertTrue(KalendarUdalost.objects.filter(prijata_faktura=pf, typ="Splatnost faktury").exists())

    def test_duplicita_neprojde(self):
        from .models import PrijataFaktura
        d = {"dodavatel": self.dod.pk, "cislo_faktury": "FV-2", "datum_doruceni": "2026-11-04", "mena": "CZK"}
        self.client.post(reverse("prijata_faktura_rucne"), d)
        self.assertEqual(self.client.post(reverse("prijata_faktura_rucne"), d).status_code, 200)
        self.assertEqual(PrijataFaktura.objects.filter(cislo_faktury="FV-2").count(), 1)


class NovyVzhledFormularuTest(TestCase):
    """Nový zákazník a nová událost používají formulář se sekcemi; uložení funguje dál."""
    def setUp(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("u", password="x"))

    def test_novy_zakaznik(self):
        r = self.client.get(reverse("create", args=["zakaznik"]))
        self.assertTemplateUsed(r, "core/form_sekce.html"); self.assertContains(r, "Firemní údaje")
        r = self.client.post(reverse("create", args=["zakaznik"]) + "?next=/", {"typ_zakaznika": "Firma", "firma": "Nová s.r.o.", "aktivni": "on"})
        self.assertRedirects(r, "/", fetch_redirect_response=False); self.assertTrue(Zakaznik.objects.filter(firma="Nová s.r.o.").exists())
        z = Zakaznik.objects.get(firma="Nová s.r.o.")
        self.assertContains(self.client.get(reverse("edit", args=["zakaznik", z.pk])), "Úprava: Nová s.r.o.")

    def test_nova_udalost(self):
        from .models import KalendarUdalost
        r = self.client.get(reverse("create", args=["kalendarudalost"]), {"datum": "2026-11-05T09:00"})
        self.assertTemplateUsed(r, "core/form_sekce.html"); self.assertContains(r, "Nová událost kalendáře")
        self.client.post(reverse("create", args=["kalendarudalost"]), {"nazev": "Výjezd", "datum": "2026-11-05T09:00", "typ": "Vlastní událost"})
        self.assertTrue(KalendarUdalost.objects.filter(nazev="Výjezd").exists())

    def test_rychla_udalost_v_kalendari(self):
        """„+“ u dne v kalendáři otevře pop-up se základními poli; rozšířené možnosti obsahují zbytek formuláře."""
        from .models import KalendarUdalost
        r = self.client.get(reverse("kalendar"), {"d": "2026-11-05"})
        self.assertContains(r, 'id="ud"'); self.assertContains(r, "Rozšířené možnosti"); self.assertContains(r, 'class="ud-ext"')
        self.assertContains(r, 'data-d="2026-11-05"'); self.assertContains(r, 'value="2026-11-05T09:00"')
        self.assertContains(r, '<option value="Vlastní událost" selected>'); self.assertNotContains(r, "Ruční událost")
        r = self.client.post(reverse("create", args=["kalendarudalost"]) + "?next=/kalendar/", {"nazev": "Schůzka", "datum": "2026-11-12T09:00", "typ": "Vlastní událost", "popis": "x"})
        self.assertRedirects(r, "/kalendar/", fetch_redirect_response=False)
        self.assertEqual(KalendarUdalost.objects.get(nazev="Schůzka").datum.date().isoformat(), "2026-11-12")

    def test_nova_zakazka_se_zobrazi(self):
        self.assertContains(self.client.get(reverse("zakazka_nova")), "Zákazník a převzetí")


class UcetZamestnanceTest(TestCase):
    """Administrátor zakládá a spravuje přihlašovací účet zaměstnance přímo v jeho kartě."""
    def setUp(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.admin = User.objects.create_user("admin", password="x", is_staff=True); self.client.force_login(self.admin)

    def test_zalozeni_uctu(self):
        from .models import HistorieZmen, Zamestnanec
        r = self.client.post(reverse("create", args=["zamestnanec"]), {"jmeno": "Petr", "prijmeni": "Novák", "aktivni": "on", "ucet_aktivni": "on",
                                                                      "ucet_jmeno": "petr", "ucet_heslo": "Tajne-heslo-42", "ucet_heslo2": "Tajne-heslo-42"})
        z = Zamestnanec.objects.get(prijmeni="Novák")
        self.assertRedirects(r, reverse("detail", args=["zamestnanec", z.pk]), fetch_redirect_response=False)
        self.assertEqual(z.uzivatel.username, "petr"); self.assertFalse(z.uzivatel.is_staff)
        self.assertTrue(self.client.login(username="petr", password="Tajne-heslo-42"))
        self.assertFalse(HistorieZmen.objects.filter(nova_hodnota__contains="Tajne").exists())

    def test_spatne_heslo_a_duplicitni_jmeno(self):
        from .models import Zamestnanec
        d = {"jmeno": "Jana", "prijmeni": "Malá", "ucet_aktivni": "on", "ucet_jmeno": "ADMIN", "ucet_heslo": "Tajne-heslo-42", "ucet_heslo2": "jine"}
        r = self.client.post(reverse("create", args=["zamestnanec"]), d)
        self.assertContains(r, "Toto jméno už používá jiný účet."); self.assertContains(r, "Hesla se neshodují."); self.assertFalse(Zamestnanec.objects.exists())

    def test_vypnuti_uctu_a_zachovani_hesla(self):
        from .models import Zamestnanec
        u = User.objects.create_user("eva", password="Puvodni-heslo-1"); z = Zamestnanec.objects.create(jmeno="Eva", uzivatel=u)
        self.assertContains(self.client.get(reverse("edit", args=["zamestnanec", z.pk])), 'value="eva"')
        self.client.post(reverse("edit", args=["zamestnanec", z.pk]), {"jmeno": "Eva", "ucet_aktivni": "on", "ucet_jmeno": "eva", "ucet_admin": "on"})
        u.refresh_from_db(); self.assertTrue(u.is_staff); self.assertTrue(u.check_password("Puvodni-heslo-1"))
        self.client.post(reverse("edit", args=["zamestnanec", z.pk]), {"jmeno": "Eva"})
        u.refresh_from_db(); self.assertFalse(u.is_active)

    def test_vlastni_ucet_nelze_vypnout(self):
        from .models import Zamestnanec
        z = Zamestnanec.objects.create(jmeno="Já", uzivatel=self.admin)
        r = self.client.post(reverse("edit", args=["zamestnanec", z.pk]), {"jmeno": "Já"})
        self.assertContains(r, "Vlastní účet nelze vypnout."); self.admin.refresh_from_db(); self.assertTrue(self.admin.is_active)

    def test_nastaveni_bez_odkazu_do_databaze(self):
        self.assertNotContains(self.client.get(reverse("nastaveni")), "/admin/auth/user/")

    def test_vsechny_formulare_v_novem_vzhledu(self):
        for slug in ("stavzakazky", "typukonu", "material", "dodavatel", "zamestnanec", "role", "opravneni", "sazbadph"):
            r = self.client.get(reverse("create", args=[slug]))
            self.assertTemplateUsed(r, "core/form_sekce.html"); self.assertEqual(r.status_code, 200, slug)


class CislovaniDokladuTest(TestCase):
    """Vlastní číslování zakázkových listů, nabídek a faktur (Nastavení → Dokumenty)."""
    def setUp(self):
        from .models import Zakaznik
        self.zak = Zakaznik.objects.create(firma="Test s.r.o."); NastaveniFirmy.objects.create(nazev_firmy="Můj servis")
        self.client.force_login(User.objects.create_user("a", password="x", is_staff=True))

    def nastav(self, typ, vzor, fmt, nulovat="rok", zacit=1):
        from .models import CiselnaRada
        CiselnaRada.objects.update_or_create(typ=typ, defaults=dict(vzor=vzor, format=fmt, nulovat=nulovat, zacit_od=zacit, zacit_od_obdobi=""))

    def test_funkce_formatu(self):
        from . import cislovani as c
        self.assertEqual(c.vyrob("DMN{YY}{N4}", date(2026, 11, 4), 7), "DMN260007")
        self.assertEqual(c.vyrob("{N3}-{DD}-{MM}/{YYYY}", date(2026, 1, 5), 12), "012-05-01/2026")
        self.assertEqual(c.dalsi_poradi("DMN{YY}{N4}", "rok", date(2026, 3, 1), ["DMN260004", "DMN250009", "X"]), 5)
        self.assertEqual(c.dalsi_poradi("DMN{YY}{N4}", "rok", date(2027, 1, 1), ["DMN260004"]), 1)
        self.assertEqual(c.dalsi_poradi("Fa{N4}", "nikdy", date(2027, 1, 1), ["Fa0041"]), 42)
        self.assertEqual(c.dalsi_poradi("FA{YY}{MM}{N3}", "mesic", date(2026, 12, 1), ["FA2611005"]), 1)
        self.assertEqual(c.dalsi_poradi("Fa{N4}", "nikdy", date(2026, 1, 1), [], zacit_od=150), 150)
        self.assertEqual(c.poradi_z_cisla("ZL{YY}{N4}", "ZL260046"), 46)
        self.assertIsNotNone(c.over_format("Fa"))
        self.assertIsNotNone(c.over_format("{N2}{N3}"))
        self.assertIsNone(c.over_format("Fa{N4}"))
        self.assertIsNotNone(c.over_nulovani("Fa{N4}", "rok"))

    def test_vychozi_cisla_beze_zmeny(self):
        from .models import Zakazka
        z = Zakazka.objects.create(zakaznik=self.zak)
        self.assertRegex(z.cislo_zakazky, r"^\d{4}-001$"); self.assertEqual(z.poradi, 1)

    def test_zakazka_faktura_a_nabidka_podle_nastaveni(self):
        from .models import Zakazka, Faktura, Nabidka
        self.nastav("zakazka", "ZL260001", "ZL{YY}{N4}")
        self.nastav("nabidka", "NAB260001", "NAB{YY}{N4}")
        self.nastav("faktura", "Fa0001", "Fa{N4}", "nikdy", zacit=41)
        z1 = Zakazka.objects.create(zakaznik=self.zak); z2 = Zakazka.objects.create(zakaznik=self.zak)
        rr = f"{z1.datum_vytvoreni.year % 100:02d}"
        self.assertEqual((z1.cislo_zakazky, z2.cislo_zakazky), (f"ZL{rr}0001", f"ZL{rr}0002"))
        self.assertEqual(Nabidka.cislo_ze_zakazky(z2), f"NAB{rr}0002")
        Nabidka.objects.create(zakaznik=self.zak, cislo_nabidky=Nabidka.cislo_ze_zakazky(z2))
        self.assertEqual(Nabidka.cislo_ze_zakazky(z2), f"NAB{rr}0002-2")
        f1 = Faktura.objects.create(zakaznik=self.zak); f2 = Faktura.objects.create(zakaznik=self.zak)
        self.assertEqual((f1.cislo_faktury, f2.cislo_faktury), ("Fa0041", "Fa0042"))

    def test_rucni_cislo_zakazky_a_preskoceni_obsazeneho(self):
        from .models import Zakazka
        self.nastav("zakazka", "ZAK0001", "ZAK{N4}", "nikdy")
        Zakazka.objects.create(zakaznik=self.zak, cislo_zakazky="ZAK0005")
        self.assertEqual(Zakazka.objects.create(zakaznik=self.zak).cislo_zakazky, "ZAK0006")
        self.assertEqual(Zakazka.objects.get(cislo_zakazky="ZAK0005").poradi, 5)

    def test_stranka_nastaveni(self):
        from .models import CiselnaRada, Zakazka
        self.assertContains(self.client.get(reverse("nastaveni")), reverse("nastaveni_cislovani"))
        r = self.client.get(reverse("nastaveni_cislovani")); self.assertContains(r, "Vzor čísla")
        d = {"vzor_zakazka": "ZL260001", "format_zakazka": "ZL{YY}{N4}", "nulovat_zakazka": "rok", "zacit_zakazka": "1",
             "vzor_nabidka": "NAB260001", "format_nabidka": "NAB{YY}{N4}",
             "vzor_faktura": "Fa0001", "format_faktura": "Fa{N4}", "nulovat_faktura": "nikdy", "zacit_faktura": "100"}
        self.assertRedirects(self.client.post(reverse("nastaveni_cislovani"), d), reverse("nastaveni"))
        self.assertEqual(CiselnaRada.objects.get(typ="faktura").zacit_od, 100)
        self.assertEqual(CiselnaRada.objects.get(typ="nabidka").nulovat, "rok")
        self.assertTrue(Zakazka.objects.create(zakaznik=self.zak).cislo_zakazky.startswith("ZL"))
        r = self.client.post(reverse("nastaveni_cislovani"), dict(d, format_faktura="Fa", nulovat_faktura="rok"))
        self.assertContains(r, "Ve vzoru musí být právě jedno pořadové číslo.")
        self.assertEqual(CiselnaRada.objects.get(typ="faktura").format, "Fa{N4}")

    def test_bezny_uzivatel_nastaveni_neotevre(self):
        self.client.force_login(User.objects.create_user("u", password="x"))
        self.assertRedirects(self.client.get(reverse("nastaveni_cislovani")), reverse("dashboard"), fetch_redirect_response=False)


class OpravyZProchazeniTest(TestCase):
    """Opravy po procházení celé aplikace: formuláře, tlačítka Zpět/Zrušit, zařízení, telefony a platby."""
    def setUp(self):
        from .models import StavZakazky, Zakazka, TypUkonu, SazbaDPH, Zamestnanec
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis", vychozi_dph=Decimal("21"))
        self.admin = User.objects.create_user("admin", password="x", is_staff=True); self.client.force_login(self.admin)
        self.k = Zakaznik.objects.create(jmeno="Tonda", telefon="604851237")
        self.z = Zakazka.objects.create(zakaznik=self.k, stav=StavZakazky.objects.create(nazev="Nová"))
        self.t = TypUkonu.objects.create(nazev="Diagnostika"); SazbaDPH.objects.create(sazba=Decimal("21")); SazbaDPH.objects.create(sazba=Decimal("12"))
        self.e1 = Zamestnanec.objects.create(jmeno="Tonda", prijmeni="A"); self.e2 = Zamestnanec.objects.create(jmeno="Pepa", prijmeni="B")

    def test_telefon_po_trojicich(self):
        from .models import formatuj_telefon
        self.assertEqual(formatuj_telefon("604851237"), "604 851 237")
        self.assertEqual(formatuj_telefon("+420604851237"), "+420 604 851 237")
        self.assertEqual(formatuj_telefon("00420 604851237"), "+420 604 851 237")
        self.assertEqual(formatuj_telefon("12345"), "12345")
        r = self.client.get(reverse("detail", args=["zakaznik", self.k.pk]))
        self.assertContains(r, "604 851 237"); self.assertNotContains(r, "tel:")

    def test_novy_formular_bez_aktivni_a_nahral(self):
        for slug in ("sazbadph", "zamestnanec", "role", "stavzakazky", "typukonu", "material", "dodavatel", "zakaznik"):
            r = self.client.get(reverse("create", args=[slug]))
            self.assertNotContains(r, 'name="aktivni"', msg_prefix=slug)
        r = self.client.get(reverse("edit", args=["typukonu", self.t.pk])); self.assertContains(r, 'name="aktivni"')
        r = self.client.get(reverse("create", args=["priloha"]))
        self.assertNotContains(r, 'name="nahral"'); self.assertNotContains(r, 'name="typ_souboru"')

    def test_vice_fotek_najednou(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Fotografie
        def png(n):
            b = BytesIO(); Image.new("RGB", (2, 2)).save(b, "PNG"); return SimpleUploadedFile(n, b.getvalue(), content_type="image/png")
        r = self.client.get(reverse("create", args=["fotografie"]) + f"?zakazka={self.z.pk}")
        self.assertContains(r, "multiple"); self.assertNotContains(r, 'name="nahral"'); self.assertNotContains(r, 'name="popis"')
        r = self.client.post(reverse("create", args=["fotografie"]) + f"?zakazka={self.z.pk}", {"zakazka": self.z.pk, "soubory": [png("a.png"), png("b.png")]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(list(Fotografie.objects.values_list("nahral", flat=True)), [self.admin.pk, self.admin.pk])

    def test_prace_vice_zamestnancu_a_sazba(self):
        from .models import ProvedenyUkon
        r = self.client.get(reverse("create", args=["provedenyukon"]) + f"?zakazka={self.z.pk}")
        self.assertContains(r, 'type="checkbox" name="zamestnanci"'); self.assertContains(r, "Sazba DPH"); self.assertContains(r, "Jiná sazba")
        self.client.post(reverse("create", args=["provedenyukon"]) + f"?zakazka={self.z.pk}",
                         {"zakazka": self.z.pk, "typ_ukonu": self.t.pk, "cena": "100", "sazba_dph": "jina", "sazba_dph_jina": "15", "zamestnanci": [self.e1.pk, self.e2.pk]})
        u = ProvedenyUkon.objects.get(); self.assertEqual(u.sazba_dph, Decimal("15")); self.assertEqual(u.zamestnanci.count(), 2)

    def test_zakaznik_soukroma_osoba_bez_firemnich_udaju(self):
        self.client.post(reverse("create", args=["zakaznik"]), {"typ_zakaznika": "Soukromá osoba", "jmeno": "Eva", "firma": "Zbytek", "ico": "", "dic": ""})
        z = Zakaznik.objects.get(jmeno="Eva"); self.assertEqual(z.firma, ""); self.assertTrue(z.aktivni)
        r = self.client.post(reverse("create", args=["zakaznik"]), {"typ_zakaznika": "Firma", "jmeno": "", "firma": ""})
        self.assertContains(r, "Vyplňte název firmy.")

    def test_zarizeni_jen_se_zakazkou_a_jednomu_zakaznikovi(self):
        from .models import Zarizeni
        self.assertRedirects(self.client.get(reverse("create", args=["zarizeni"])), reverse("zakazka_nova"), fetch_redirect_response=False)
        self.client.post(reverse("create", args=["zarizeni"]) + f"?zakazka={self.z.pk}", {"vyrobce": "Makita", "typ": "X", "seriove_cislo": "SN1"})
        d = Zarizeni.objects.get(); self.assertEqual(d.zakaznik, self.k); self.assertIn(d, self.z.zarizeni.all())
        pepa = Zakaznik.objects.create(jmeno="Pepa")
        r = self.client.post(reverse("lookup_new", args=["zarizeni"]), {"dep": pepa.pk, "vyrobce": "makita", "typ": "X", "seriove_cislo": "sn1"})
        self.assertEqual(r.status_code, 400)  # zařízení je právě na firmě v zakázce Tondy
        self.z.stav = self.z.stav.__class__.objects.create(nazev="Vydáno"); self.z.save()
        r = self.client.post(reverse("lookup_new", args=["zarizeni"]), {"dep": pepa.pk, "vyrobce": "makita", "typ": "X", "seriove_cislo": "sn1"})
        self.assertEqual(r.status_code, 200); self.assertEqual(Zarizeni.objects.count(), 1); d.refresh_from_db(); self.assertEqual(d.zakaznik, pepa)

    def test_pomocne_tabulky_a_zpet(self):
        from .models import ProvedenyUkon
        u = ProvedenyUkon.objects.create(zakazka=self.z, typ_ukonu=self.t)
        self.assertEqual(self.client.get(reverse("list", args=["provedenyukon"])).status_code, 302)
        self.assertEqual(self.client.get(reverse("list", args=["kalendarudalost"])).status_code, 302)
        plocha = reverse("detail", args=["zakazka", self.z.pk]); self.client.get(plocha)
        r = self.client.get(reverse("detail", args=["provedenyukon", u.pk]))
        self.assertContains(r, f'href="{plocha}">Zpět</a>')
        r = self.client.get(reverse("edit", args=["provedenyukon", u.pk])); self.assertContains(r, f'href="{reverse("detail", args=["provedenyukon", u.pk])}">Zrušit</a>')
        self.client.get(plocha); r = self.client.get(reverse("create", args=["pouzitymaterial"])); self.assertContains(r, f'href="{plocha}">Zrušit</a>')

    def test_faktura_zaplaceno_a_platba_bez_faktury(self):
        from .models import Platba, KalendarUdalost
        self.client.post(reverse("faktura_nova"), {"zakazka": self.z.pk, "datum": "2026-11-05", "splatnost": "2026-11-19"})
        f = Faktura.objects.get(); p = Platba.objects.get(faktura=f); self.assertEqual(p.stav, "Čeká na zaplacení")
        r = self.client.get(reverse("detail", args=["faktura", f.pk])); self.assertContains(r, "Vystaveno"); self.assertNotContains(r, "<h5 class=\"mt-3\">Kalendář")
        self.client.post(reverse("faktura_zaplaceno", args=[f.pk])); p.refresh_from_db(); self.assertEqual(p.stav, "Zaplaceno")
        self.assertTrue(KalendarUdalost.objects.filter(typ="Zaplaceno", faktura=f).exists())
        r = self.client.get(reverse("create", args=["platba"]) + f"?zakazka={self.z.pk}"); self.assertNotContains(r, 'name="faktura"'); self.assertContains(r, "Způsob platby")
        self.client.post(reverse("create", args=["platba"]) + f"?zakazka={self.z.pk}", {"zpusob": "Hotově", "castka": "500", "datum_zaplaceni": "2026-11-05T10:00"})
        h = Platba.objects.get(faktura__isnull=True); self.assertEqual((h.stav, h.zakazka), ("Zaplaceno", self.z))
        r = self.client.get(reverse("list", args=["platba"])); self.assertContains(r, "Datum splatnosti"); self.assertNotContains(r, "+ Nový")

    def test_zpet_po_navratu_tlacitkem_prohlizece(self):
        """Seznam → detail A → (Zpět v prohlížeči) → detail B: Zpět vede na seznam, ne na A."""
        b = Zakaznik.objects.create(jmeno="Pepa")
        seznam = reverse("list", args=["zakaznik"]); a_url = reverse("detail", args=["zakaznik", self.k.pk])
        self.client.get(seznam); self.client.get(a_url, HTTP_REFERER="http://testserver" + seznam)
        r = self.client.get(reverse("detail", args=["zakaznik", b.pk]), HTTP_REFERER="http://testserver" + seznam)
        self.assertContains(r, f'href="{seznam}">Zpět</a>')


class TmavyRezimTest(TestCase):
    """Přepínač vzhledu je v horní liště a skript tmavého režimu je i na stránkách mimo base.html."""
    def setUp(self):
        self.u = User.objects.create_user("motiv", password="heslo12345", is_staff=True, is_superuser=True)
        NastaveniFirmy.objects.create(nazev_firmy="Test s.r.o.")

    def test_prepinac_v_liste(self):
        self.client.force_login(self.u)
        h = self.client.get("/").content.decode()
        self.assertIn('id="bm-motiv"', h)
        self.assertIn("prefers-color-scheme: dark", h)
        self.assertIn("data-bs-theme", h)

    def test_prihlaseni_respektuje_rezim(self):
        h = self.client.get("/login/").content.decode()
        self.assertIn("prefers-color-scheme: dark", h)



class PrevodLibreOfficeTest(TestCase):
    """Převod přes LibreOffice: opakování po nepovedeném prvním spuštění a rozlišení chyb."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.d = Path(tempfile.mkdtemp()); self.x = self.d / "dokument.xlsx"; self.x.write_bytes(b"x")

    def _falesny_soffice(self, chovani):
        """Podvrhne spuštění LibreOffice: chovani je seznam 'ok' / 'nic' / 'cas' pro jednotlivé pokusy."""
        from pathlib import Path
        from unittest import mock
        from .sablony import prevod
        pokusy = iter(chovani)
        def spust(cmd, limit):
            c = next(pokusy)
            if c == "ok": (Path(cmd[cmd.index("--outdir") + 1]) / "dokument.pdf").write_bytes(b"%PDF-1.4")
            return (None, "LibreOffice nestihl převod") if c == "cas" else (0 if c == "ok" else 81, "")
        return [mock.patch.object(prevod, "soffice", return_value="/usr/bin/soffice"),
                mock.patch.object(prevod, "_spust", side_effect=spust), mock.patch.object(prevod.time, "sleep")]

    def _s(self, chovani):
        from contextlib import ExitStack
        from .sablony import prevod
        with ExitStack() as st:
            for p in self._falesny_soffice(chovani): st.enter_context(p)
            return prevod.na_pdf(self.x)

    def test_prvni_spusteni_bez_vysledku_se_zopakuje(self):
        self.assertEqual(self._s(["nic", "ok"]), b"%PDF-1.4")
        self.assertEqual(self._s(["cas", "nic", "ok"]), b"%PDF-1.4")

    def test_opakovane_selhani_neni_chybejici_libreoffice(self):
        from .sablony import prevod
        with self.assertRaises(prevod.PrevodSeNepovedl) as e:
            self._s(["cas", "cas", "cas"])
        self.assertNotIsInstance(e.exception, prevod.ChybiLibreOffice)

    def test_chybejici_libreoffice(self):
        from unittest import mock
        from .sablony import prevod
        with mock.patch.object(prevod, "soffice", return_value=None), self.assertRaises(prevod.ChybiLibreOffice):
            prevod.na_pdf(self.x)

    def test_limit_ukonci_proces(self):
        import sys
        import time
        from .sablony import prevod
        t = time.time(); kod, text = prevod._spust([sys.executable, "-c", "import time; time.sleep(30)"], 1)
        self.assertIsNone(kod); self.assertIn("nestihl", text); self.assertLess(time.time() - t, 10)

    def test_miniatura_rozlisuje_duvod_a_neuklada_se(self):
        from unittest import mock
        from .models import SablonaDokumentu as S
        from .sablony import prevod
        from .views_sablony import sablona_miniatura
        from django.test import RequestFactory
        s = S.objects.filter(format="excel").first()
        rq = RequestFactory().get("/")
        for chyba, text in ((prevod.PrevodSeNepovedl("x"), "převod se nepovedl"), (prevod.ChybiLibreOffice("x"), "chybí LibreOffice")):
            with mock.patch("core.views_sablony.renderery.renderer", return_value=mock.Mock(pdf=mock.Mock(side_effect=chyba))):
                r = sablona_miniatura(rq, s.pk)
            self.assertIn(text, r.content.decode()); self.assertEqual(r["Cache-Control"], "no-store")
            s.refresh_from_db(); self.assertFalse(s.nahled)
