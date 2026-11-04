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
