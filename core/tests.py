from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from lxml import etree

from .models import Faktura, NastaveniFirmy, PolozkaFaktury, Zakaznik
from .sablony import isdoc

NS = {"i": isdoc.NS}


def uzivatel(jmeno="u", role="Administrativa"):
    """Přihlašovací účet zaměstnance s výchozí rolí (Zaměstnanec, Technik, Administrativa, Administrátor)."""
    from .models import Role, Zamestnanec
    u = User.objects.create_user(jmeno, password="x")
    z = Zamestnanec.objects.create(jmeno=jmeno, uzivatel=u)
    if role: z.role.add(Role.objects.get(nazev=role))
    return u


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
        self.client.force_login(uzivatel("u"))
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
        self.client.force_login(uzivatel("u"))

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
        self.client.force_login(uzivatel("u"))
        self.z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), stav=StavZakazky.objects.create(nazev="Nová"))

    def zvyraznene(self):
        import re
        html = self.client.get(reverse("plocha", args=[self.z.pk])).content.decode()
        return re.findall(r'class="btn (?:btn-sm )?btn-(?:primary|success)" href="[^"]*">([^<]+)</a>', html)

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


class ZamestnanciZakazkyTest(TestCase):
    """Karta Zaměstnanci u zakázky ukazuje všechny zapojené: kdo zakázku převzal i kdo na ní dělal práci."""
    def test_prijemce_i_pracovnici(self):
        import re
        from .models import ProvedenyUkon, StavZakazky, TypUkonu, Zakazka, Zamestnanec
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(uzivatel("u"))
        z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), stav=StavZakazky.objects.create(nazev="Nová"))
        sekretarka = Zamestnanec.objects.create(jmeno="Barunka", prijmeni="Placková", pracovni_pozice="Sekretářka")
        technik = Zamestnanec.objects.create(jmeno="Antonín", prijmeni="Otras")
        z.zamestnanci.add(sekretarka)
        for nazev in ("Oprava", "Diagnostika", "Měření"):
            ProvedenyUkon.objects.create(zakazka=z, typ_ukonu=TypUkonu.objects.create(nazev=nazev)).zamestnanci.add(technik)
        ProvedenyUkon.objects.create(zakazka=z, typ_ukonu=TypUkonu.objects.get(nazev="Oprava")).zamestnanci.add(technik)
        html = self.client.get(reverse("plocha", args=[z.pk])).content.decode()
        karta = re.search(r'<div class="tp d-none" data-tab="zam">(.*?)</div>', html, re.S).group(1)
        self.assertIn("Barunka Placková", karta); self.assertIn("přiřazen(a) k zakázce", karta)
        self.assertIn("Antonín Otras", karta); self.assertIn("práce: Oprava (2×)", karta); self.assertIn("práce: Měření", karta)
        self.assertEqual(karta.count("Antonín Otras"), 1)  # každý jen jednou

class PoznamkaPraceTest(TestCase):
    """Interní poznámka k úkonu se nepropisuje do zakázkového listu ani do nabídky."""
    def test_poznamka_neni_v_nazvu(self):
        from .models import ProvedenyUkon, StavZakazky, TypUkonu, Zakazka
        from .sablony.typy import _seznamy
        from .views import nabidka_polozky
        z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), stav=StavZakazky.objects.create(nazev="Nová"))
        ProvedenyUkon.objects.create(zakazka=z, typ_ukonu=TypUkonu.objects.create(nazev="Oprava"), poznamka="Opraveno")
        _, pr = _seznamy(z)
        self.assertEqual(pr[0]["prace.nazev"], "Oprava"); self.assertNotIn("Opraveno", pr[0]["prace.popis"])
        self.assertEqual(nabidka_polozky(z)[0]["popis"], "Oprava")

class OpravneniNastaveniTest(TestCase):
    """Nastavení (včetně šablon dokumentů) vidí jen ten, kdo má oprávnění Nastavení."""
    STRANKY = [("nastaveni", []), ("nastaveni_firma", []), ("nastaveni_zaloha", []), ("list", ["sazbadph"]), ("create", ["zamestnanec"]), ("list", ["historiezmen"])]

    def test_bezny_uzivatel_nastaveni_neotevre(self):
        self.client.force_login(uzivatel("u"))
        for nazev, args in self.STRANKY:
            r = self.client.get(reverse(nazev, args=args))
            self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False, msg_prefix=nazev)
        r = self.client.get(reverse("dashboard"))
        self.assertNotContains(r, reverse("nastaveni"))
        self.assertRedirects(self.client.get(reverse("sablony")), reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("list", args=["zakazka"])).status_code, 200)

    def test_admin_nastaveni_otevre(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("a", password="x", is_staff=True))
        self.assertContains(self.client.get(reverse("dashboard")), reverse("nastaveni"))
        for nazev, args in self.STRANKY:
            self.assertIn(self.client.get(reverse(nazev, args=args)).status_code, (200, 302), nazev)
        self.assertEqual(self.client.get(reverse("nastaveni")).status_code, 200)

    def test_styly_jsou_pribalene(self):
        self.client.force_login(uzivatel("u"))
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
        self.client.force_login(uzivatel("u"))
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
        volby = {v[0]: (v[4], v[3]) for v in r.context["filtr"]["skupiny"][0]["volby"]}  # stavy jsou v okně Filtrovat (počet, zaškrtnuto)
        self.assertEqual(volby["Nová"], (2, False)); self.assertEqual(volby["Diagnostika"], (1, True))
        self.assertEqual(len(r.context["rows"]), 1)
        self.assertContains(r, 'class="table table-sm table-hover bm-table bm-t-zakazka"')  # pevné rozložení sloupců
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
        self.client.force_login(uzivatel("u"))
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

    def test_po_vytvoreni_nabidky_pokracovat_misto_zpet(self):
        """Po vytvoření nabídky už není „Zpět“, ale Pokračovat do zakázky a Pokračovat na fakturu; po faktuře jen Pokračovat."""
        from urllib.parse import urlencode
        from django.utils.html import escape
        from .models import Nabidka
        det = reverse("detail", args=["zakazka", self.z.pk]); self.client.get(det)
        r = self.client.post(reverse("nabidka_nova"), {"zakazka": self.z.pk, "datum": "2026-11-05T10:00"}, follow=True)
        n = Nabidka.objects.get(); self.assertEqual(r.redirect_chain[0][0], reverse("dokument", args=["nabidka", n.pk]) + "?nove=1")
        self.assertContains(r, f'href="{det}">Pokračovat do zakázky</a>'); self.assertNotContains(r, ">Zpět</a>")
        fa = reverse("faktura_nova") + "?" + urlencode({"zakazka": self.z.pk, "next": det})
        self.assertContains(r, f'href="{escape(fa)}">Pokračovat na fakturu →</a>')
        self.assertContains(self.client.get(reverse("dokument_sablony", args=["nabidka", n.pk]) + "?nove=1"), "nove=1")
        r = self.client.post(fa, {"zakazka": self.z.pk, "datum": "2026-11-05", "splatnost": "2026-11-19"}, follow=True)
        self.assertContains(r, f'href="{det}">Pokračovat do zakázky</a>'); self.assertNotContains(r, "Pokračovat na fakturu")
        r = self.client.get(reverse("dokument", args=["nabidka", n.pk]) + "?nove=1"); self.assertContains(r, "Otevřít fakturu")
        r = self.client.get(reverse("dokument", args=["nabidka", n.pk])); self.assertContains(r, ">Zpět</a>"); self.assertNotContains(r, "Pokračovat")

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
        self.client.force_login(uzivatel("u"))
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
        self.client.force_login(uzivatel("u"))

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
        for slug in ("stavzakazky", "typukonu", "material", "dodavatel", "zamestnanec", "role", "sazbadph"):
            r = self.client.get(reverse("create", args=[slug]))
            self.assertTemplateUsed(r, "core/form_sekce.html"); self.assertEqual(r.status_code, 200, slug)
        self.assertEqual(self.client.get(reverse("create", args=["opravneni"])).status_code, 404)  # oprávnění určuje aplikace


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

    def test_rok_a_poradi_do_sablony(self):
        """Do políček „rok“ a „poř. číslo“ zakázkového listu jde zvlášť rok (2026) a pořadí (0001), ne celé číslo."""
        from . import cislovani as c
        from .models import Zakazka
        from .sablony.typy import ZakazkovyList
        self.assertEqual(c.rozloz("ZL{YY}{N4}", "ZL260001"), (2026, "0001"))
        self.assertEqual(c.rozloz("{YYYY}-{N3}", "2026-048"), (2026, "048"))
        self.assertEqual(c.rozloz("{N3}-{DD}-{MM}/{YYYY}", "012-05-01/2026"), (2026, "012"))
        self.assertEqual(c.rozloz("Z{N5}", "Z00042"), (None, "00042"))
        self.assertEqual(c.rozloz("ZL{YY}{N4}", "jine"), (None, None))
        self.nastav("zakazka", "ZL260001", "ZL{YY}{N4}")
        z = Zakazka.objects.create(zakaznik=self.zak)
        p = ZakazkovyList.data(z)["pole"]; rok = z.datum_vytvoreni.year
        self.assertEqual((p["zakazka.rok"], p["zakazka.poradove_cislo"], p["dokument.poradove_cislo"]), (str(rok), "0001", "0001"))
        Zakazka.objects.filter(pk=z.pk).update(cislo_zakazky="2025-007")  # starší číslo v původním tvaru
        p = ZakazkovyList.data(Zakazka.objects.get(pk=z.pk))["pole"]
        self.assertEqual((p["zakazka.rok"], p["zakazka.poradove_cislo"]), ("2025", "007"))
        self.nastav("zakazka", "Z00001", "Z{N5}", "nikdy")
        p = ZakazkovyList.data(Zakazka.objects.create(zakaznik=self.zak))["pole"]
        self.assertEqual((p["zakazka.rok"], p["zakazka.poradove_cislo"]), (str(date.today().year), "00001"))

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
        from .sablony.typy import Nabidka as NabidkaSablona  # druhá nabídka: v šabloně celé číslo, ne jen „2“
        n2 = Nabidka.objects.create(zakaznik=self.zak, cislo_nabidky=Nabidka.cislo_ze_zakazky(z2))
        self.assertEqual(NabidkaSablona.pole_dokladu(n2)["dokument.poradove_cislo"], f"{rr}0002-2")
        self.assertEqual(NabidkaSablona.nazev_souboru(n2), f"DMN_{rr}0002-2")
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
        self.client.force_login(uzivatel("u"))
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


class KontrolaEmailuATelefonuTest(TestCase):
    """Špatný e-mail a telefon: srozumitelná česká hláška ze serveru místo anglické bubliny prohlížeče."""
    def setUp(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis", vychozi_dph=Decimal("21"))
        self.admin = User.objects.create_user("admin", password="x", is_staff=True); self.client.force_login(self.admin)

    def test_validator_telefonu(self):
        from django.core.exceptions import ValidationError
        from .models import validuj_telefon
        for ok in ("", "604851237", "604 851 237", "+420 604 851 237", "00420604851237", "+421 905 123 456", "+49 30 1234 5678", "0049301234567"):
            validuj_telefon(ok)
        for spatne in ("45214536", "6048512370", "+420 45214536", "+420 6048512370", "+49 123", "+1 2345 6789 0123 4567", "604-851-237", "abc"):
            with self.assertRaises(ValidationError, msg=spatne): validuj_telefon(spatne)

    def test_novy_zakaznik_cesky_chyby(self):
        r = self.client.post(reverse("create", args=["zakaznik"]), {"typ_zakaznika": "Soukromá osoba", "jmeno": "Barunka", "telefon": "45214536", "email": "barca.plagmail.com"})
        self.assertEqual(r.status_code, 200); self.assertFalse(Zakaznik.objects.exists())
        self.assertContains(r, "Zadejte platný e-mail"); self.assertContains(r, "musí mít 9 číslic")

    def test_novy_zakaznik_z_vyhledavani(self):
        r = self.client.post(reverse("lookup_new", args=["zakaznik"]), {"typ_zakaznika": "Firma", "firma": "Elektro", "telefon": "+420 604851237", "email": "x@"})
        self.assertContains(r, "Zadejte platný e-mail", status_code=400)
        r = self.client.post(reverse("lookup_new", args=["zakaznik"]), {"typ_zakaznika": "Firma", "firma": "Elektro", "telefon": "+420604851237", "email": "info@elektro.cz"})
        self.assertEqual(Zakaznik.objects.get().telefon, "+420 604 851 237")

    def test_zamestnanec_cesky_chyby(self):
        r = self.client.post(reverse("create", args=["zamestnanec"]), {"jmeno": "Barunka", "prijmeni": "Placková", "telefon": "45214536", "email": "barca.plagmail.com"})
        self.assertContains(r, "Zadejte platný e-mail"); self.assertContains(r, "musí mít 9 číslic")

    def test_pruvodce_ucet_cesky_email(self):
        User.objects.all().delete()
        r = self.client.post(reverse("pruvodce_ucet"), {"username": "sef", "first_name": "", "last_name": "", "email": "sef.firma.cz", "password1": "Heslo-12345", "password2": "Heslo-12345"})
        self.assertContains(r, "Zadejte platný e-mail")


class RoleAOpravneniTest(TestCase):
    """Zaměstnanec → Role → Oprávnění: co smí technik, administrativa a účet bez role (core/prava.py)."""
    def setUp(self):
        from .models import StavZakazky, Zakazka, Zamestnanec, KalendarUdalost
        self.k = Zakaznik.objects.create(jmeno="Jan Novák")
        self.z = Zakazka.objects.create(zakaznik=self.k, stav=StavZakazky.objects.get(nazev="Nová"))
        self.Zam, self.Ud = Zamestnanec, KalendarUdalost

    def prihlas(self, role, jmeno="t"):
        u = uzivatel(jmeno, role); self.client.force_login(u); return u

    def test_vychozi_role_a_opravneni(self):
        from .models import Opravneni, Role
        from . import prava
        self.assertEqual(set(Opravneni.objects.values_list("kod", flat=True)), set(prava.vse()))  # včetně oprávnění nainstalovaných modulů
        self.assertEqual(set(Role.objects.get(nazev="Technik").opravneni.values_list("kod", flat=True)) & prava.VSE, {prava.PRISTUP, prava.STAV, prava.KALENDAR})  # bez oprávnění modulů
        self.assertTrue(Role.objects.get(nazev="Administrátor").je_administrator)

    def test_ucet_bez_role_nema_pristup(self):
        self.prihlas(None)
        r = self.client.get(reverse("dashboard")); self.assertEqual(r.status_code, 403); self.assertContains(r, "Nemáte přístup", status_code=403)
        self.assertEqual(self.client.get(reverse("list", args=["zakazka"])).status_code, 403)

    def test_technik_neni_u_dokladu(self):
        self.prihlas("Technik")
        r = self.client.get(reverse("plocha", args=[self.z.pk]))
        self.assertEqual(r.status_code, 200); self.assertContains(r, "Přidat práci")
        self.assertNotContains(r, "Vytvořit fakturu"); self.assertNotContains(r, "Vytvořit nabídku"); self.assertNotContains(r, "Přidat platbu")
        self.assertNotContains(r, reverse("dokumenty"))  # Dokumenty nejsou v menu
        for url in (reverse("faktura_nova"), reverse("nabidka_nova"), reverse("dokumenty"), reverse("list", args=["faktura"]), reverse("prijata_faktura_rucne")):
            self.assertRedirects(self.client.get(url), reverse("dashboard"), fetch_redirect_response=False, msg_prefix=url)
        self.assertEqual(self.client.get(reverse("dokument", args=["zakazkovy_list", self.z.pk])).status_code, 200)

    def test_administrativa_vystavi_doklady(self):
        self.prihlas("Administrativa")
        r = self.client.get(reverse("plocha", args=[self.z.pk])); self.assertContains(r, "Vytvořit fakturu"); self.assertContains(r, "Vytvořit nabídku")
        self.assertEqual(self.client.get(reverse("faktura_nova")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dokumenty")).status_code, 200)

    def test_jen_faktury_bez_nabidek(self):
        from .models import Role, Opravneni
        r = Role.objects.create(nazev="Účetní"); r.opravneni.set(Opravneni.objects.filter(kod__in=["aplikace.pristup", "faktury.spravovat"]))
        u = uzivatel("ucetni", None); self.Zam.objects.get(uzivatel=u).role.add(r); self.client.force_login(u)
        r = self.client.get(reverse("dokumenty")); self.assertContains(r, "+ Faktura"); self.assertNotContains(r, "+ Nabídka")
        self.assertRedirects(self.client.get(reverse("nabidka_nova")), reverse("dashboard"), fetch_redirect_response=False)

    def test_mazani_jen_s_opravnenim(self):
        self.prihlas("Administrativa")
        url = reverse("delete", args=["zakaznik", self.k.pk])
        self.assertRedirects(self.client.post(url), reverse("dashboard"), fetch_redirect_response=False)
        self.k.refresh_from_db(); self.assertTrue(self.k.aktivni)
        self.assertNotContains(self.client.get(reverse("detail", args=["zakaznik", self.k.pk])), "Deaktivovat")
        self.assertNotIn("aktivni", self.client.get(reverse("edit", args=["zakaznik", self.k.pk])).context["form"].fields)
        self.client.force_login(uzivatel("admin", "Administrátor"))
        self.client.post(url); self.k.refresh_from_db(); self.assertFalse(self.k.aktivni)

    def test_uprava_zakaznika(self):
        self.prihlas("Technik")
        url = reverse("edit", args=["zakaznik", self.k.pk])
        self.assertRedirects(self.client.get(url), reverse("dashboard"), fetch_redirect_response=False)
        self.assertNotContains(self.client.get(reverse("detail", args=["zakaznik", self.k.pk])), url)
        self.assertEqual(self.client.get(reverse("create", args=["zakaznik"])).status_code, 200)  # nového zákazníka založí každý
        self.client.force_login(uzivatel("a", "Administrativa"))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_vlastni_udalost_v_kalendari(self):
        from django.utils import timezone
        u = self.prihlas("Zaměstnanec"); jiny = uzivatel("jiny", "Zaměstnanec")
        moje = self.Ud.objects.create(nazev="Moje", datum=timezone.now(), vytvoril=u)
        cizi = self.Ud.objects.create(nazev="Cizí", datum=timezone.now(), vytvoril=jiny)
        self.assertEqual(self.client.get(reverse("edit", args=["kalendarudalost", moje.pk])).status_code, 200)
        self.assertRedirects(self.client.get(reverse("edit", args=["kalendarudalost", cizi.pk])), reverse("dashboard"), fetch_redirect_response=False)
        self.client.force_login(uzivatel("tech", "Technik"))
        self.assertEqual(self.client.get(reverse("edit", args=["kalendarudalost", cizi.pk])).status_code, 200)

    def test_rucni_zmena_stavu(self):
        from .models import StavZakazky
        self.prihlas("Zaměstnanec")
        vydano = StavZakazky.objects.get(nazev="Vydáno")
        self.assertNotContains(self.client.get(reverse("plocha", args=[self.z.pk])), "Změnit ručně")
        self.client.post(reverse("stav_akce", args=[self.z.pk]), {"akce": "rucne", "stav": vydano.pk})
        self.z.refresh_from_db(); self.assertEqual(self.z.stav.nazev, "Nová")
        self.client.force_login(uzivatel("tech", "Technik"))
        self.client.post(reverse("stav_akce", args=[self.z.pk]), {"akce": "rucne", "stav": vydano.pk})
        self.z.refresh_from_db(); self.assertEqual(self.z.stav.nazev, "Vydáno")

    def test_novy_zamestnanec_dostane_zakladni_roli(self):
        self.client.force_login(User.objects.create_user("sef", password="x", is_staff=True))
        self.client.post(reverse("create", args=["zamestnanec"]), {"jmeno": "Petr", "prijmeni": "Nový"})
        self.assertEqual(list(self.Zam.objects.get(jmeno="Petr").role.values_list("nazev", flat=True)), ["Zaměstnanec"])
        r = self.client.get(reverse("create", args=["role"])); self.assertContains(r, "Faktury a platby"); self.assertContains(r, 'type="checkbox"')
        self.assertContains(self.client.get(reverse("list", args=["opravneni"])), "Mazání a deaktivace")


class CitelnaHistorieTest(TestCase):
    """Historie změn: vybraní zaměstnanci a jiné vazby se zapíší jménem, ne jako „[] → <QuerySet […]>“."""
    def setUp(self):
        from .models import StavZakazky, Zakazka, Zamestnanec
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(uzivatel("u"))
        self.e = Zamestnanec.objects.create(jmeno="Barunka", prijmeni="Placková")
        self.z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), stav=StavZakazky.objects.create(nazev="Nová"))

    def uloz(self, **zmena):
        url = reverse("edit", args=["zakazka", self.z.pk]); form = self.client.get(url).context["form"]
        data = {}
        for n in form.fields:
            v = form[n].value(); w = form[n].field.widget
            if isinstance(v, (list, tuple)): data[n] = [str(x.pk if hasattr(x, "pk") else x) for x in v]
            elif v not in (None, False): data[n] = v if isinstance(v, bool) else (w.format_value(v) or "")
        data.update(zmena)
        r = self.client.post(url, data); self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)

    def test_zamestnanci_jmenem(self):
        from .models import HistorieZmen
        self.uloz(zamestnanci=[str(self.e.pk)])
        h = HistorieZmen.objects.get(typ_objektu="zakazka", akce="Úprava")  # jen zaměstnanci, nic jiného se nezměnilo
        self.assertEqual((h.puvodni_hodnota, h.nova_hodnota), ("", str(self.e)))
        html = self.client.get(reverse("plocha", args=[self.z.pk])).content.decode()
        self.assertIn(f"— → {self.e}", html); self.assertNotIn("QuerySet", html); self.assertIn("Zaměstnanci", html)

    def test_starsi_zaznamy(self):
        from .models import HistorieZmen
        from .historie import zmena, pole_nazev
        h = HistorieZmen(typ_objektu="zakazka", pole="zamestnanci", puvodni_hodnota="[]",
                         nova_hodnota="<QuerySet [<Zamestnanec: Barunka Placková>, <Zamestnanec: Milda>]>")
        self.assertEqual(zmena(h), "— → Barunka Placková, Milda"); self.assertEqual(pole_nazev(h), "Zaměstnanci")
        h = HistorieZmen(typ_objektu="zakazka", pole="identifikacni_cislo", puvodni_hodnota="", nova_hodnota="SPL92456")
        self.assertEqual(zmena(h), "— → SPL92456"); self.assertEqual(pole_nazev(h), "Identifikační číslo")
        self.assertEqual(zmena(HistorieZmen(typ_objektu="zakazka")), "")  # vytvoření: žádná osamocená šipka
        self.assertEqual(zmena(HistorieZmen(puvodni_hodnota="[poznámka]", nova_hodnota="True")), "[poznámka] → Ano")


class PolozkyDokladuBezPridaniTest(TestCase):
    """Položky faktury a nabídky se ručně nepřidávají, vznikají jen ze zakázky."""
    def setUp(self):
        self.client.force_login(uzivatel())
        self.f = Faktura.objects.create(zakaznik=Zakaznik.objects.create(firma="Odběratel a.s."))
        PolozkaFaktury.objects.create(faktura=self.f, popis="Oprava", mnozstvi=Decimal("1"), jednotka="ks", jednotkova_cena=Decimal("100"), sazba_dph=Decimal("21"))

    def test_bez_tlacitka_pridat(self):
        r = self.client.get(reverse("detail", args=["faktura", self.f.pk]))
        self.assertContains(r, "Položky faktury")
        self.assertNotContains(r, reverse("create", args=["polozkafaktury"]))

    def test_formular_nove_polozky_neexistuje(self):
        for s, d in (("polozkafaktury", "faktura"), ("polozkanabidky", "nabidka")):
            r = self.client.get(reverse("create", args=[s]) + f"?{d}={self.f.pk}")
            self.assertRedirects(r, reverse("detail", args=[d, self.f.pk]), fetch_redirect_response=False)
            self.assertRedirects(self.client.get(reverse("create", args=[s])), reverse("list", args=[d]), fetch_redirect_response=False)
        self.assertEqual(PolozkaFaktury.objects.count(), 1)


class PracePrepinaStavZakazkyTest(TestCase):
    """Přidáním práce se nová zakázka přepne na Rozpracováno a změna se zapíše do historie; jiné stavy se nemění."""
    def setUp(self):
        from .models import StavZakazky, Zakazka, TypUkonu
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis", vychozi_dph=Decimal("21"))
        self.client.force_login(User.objects.create_user("admin", password="x", is_staff=True))
        self.k = Zakaznik.objects.create(jmeno="Jan"); self.t = TypUkonu.objects.create(nazev="Diagnostika")
        self.z = Zakazka.objects.create(zakaznik=self.k, stav=StavZakazky.objects.create(nazev="Nová"))

    def pridej_praci(self):
        self.client.post(reverse("create", args=["provedenyukon"]) + f"?zakazka={self.z.pk}",
                         {"zakazka": self.z.pk, "typ_ukonu": self.t.pk, "cena": "100", "sazba_dph": "21"})
        self.z.refresh_from_db()

    def test_nova_zakazka_prejde_na_rozpracovano(self):
        from .models import HistorieZmen
        self.pridej_praci(); self.assertEqual(self.z.stav.nazev, "Rozpracováno")
        h = HistorieZmen.objects.get(typ_objektu="zakazka", id_objektu=self.z.pk, akce="Změna stavu")
        self.assertEqual((h.puvodni_hodnota, h.nova_hodnota), ("Nová", "Rozpracováno"))

    def test_jiny_stav_se_nemeni(self):
        from .models import StavZakazky
        self.z.stav = StavZakazky.objects.create(nazev="Čeká na díl"); self.z.save()
        self.pridej_praci(); self.assertEqual(self.z.stav.nazev, "Čeká na díl")

    def test_zakazkovy_list_s_praci(self):
        from .models import Zakazka
        self.client.post(reverse("zakazka_nova"), {"zakaznik": self.k.pk, "ukon_typ": [self.t.pk], "ukon_cena": ["100"], "ukon_dph": ["21"]})
        self.assertEqual(Zakazka.objects.latest("pk").stav.nazev, "Rozpracováno")
        self.client.post(reverse("zakazka_nova"), {"zakaznik": self.k.pk})
        self.assertEqual(Zakazka.objects.latest("pk").stav.nazev, "Nová")


class VicePolozekNajednouTest(TestCase):
    """Tlačítko Přidat ve formuláři práce a materiálu: víc položek se uloží najednou, nevyplněná kopie se přeskočí."""
    def setUp(self):
        from .models import StavZakazky, Zakazka, TypUkonu, Material
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis", vychozi_dph=Decimal("21"))
        self.client.force_login(User.objects.create_user("admin", password="x", is_staff=True))
        self.k = Zakaznik.objects.create(jmeno="Jan"); self.t = TypUkonu.objects.create(nazev="Diagnostika"); self.t2 = TypUkonu.objects.create(nazev="Čištění")
        self.m = Material.objects.create(nazev="Kabel", posledni_cena=Decimal("50")); self.m2 = Material.objects.create(nazev="Šroub", posledni_cena=Decimal("2"))
        self.z = Zakazka.objects.create(zakaznik=self.k, stav=StavZakazky.objects.create(nazev="Nová"))
        self.url = lambda s: reverse("create", args=[s]) + f"?zakazka={self.z.pk}"

    def test_formular_ma_tlacitko_pridat(self):
        for s in ("provedenyukon", "pouzitymaterial"):
            r = self.client.get(self.url(s)); self.assertContains(r, "+ Přidat"); self.assertContains(r, 'id="bm-dalsi-vzor"'); self.assertContains(r, 'name="d__N__-')
            self.assertNotContains(r, 'name="d__N__-zakazka"')
        from .models import ProvedenyUkon
        u = ProvedenyUkon.objects.create(zakazka=self.z, typ_ukonu=self.t)
        self.assertNotContains(self.client.get(reverse("edit", args=["provedenyukon", u.pk])), "bm-dalsi-vzor")  # úprava jedné práce bez kopií

    def test_vice_praci_najednou(self):
        from .models import ProvedenyUkon, HistorieZmen
        r = self.client.post(self.url("provedenyukon"), {"zakazka": self.z.pk, "typ_ukonu": self.t.pk, "cena": "100", "sazba_dph": "21", "dalsi": ["1", "2", "3"],
                                                        "d1-typ_ukonu": self.t2.pk, "d1-cena": "200", "d1-sazba_dph": "21",
                                                        "d2-sazba_dph": "21",  # přidaná, ale nevyplněná
                                                        "d3-typ_ukonu": self.t.pk, "d3-cena": "50", "d3-sazba_dph": "12"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sorted(ProvedenyUkon.objects.filter(zakazka=self.z).values_list("cena", flat=True)), [Decimal("50"), Decimal("100"), Decimal("200")])
        self.assertEqual(HistorieZmen.objects.filter(typ_objektu="provedenyukon", akce="Vytvoření").count(), 3)
        self.z.refresh_from_db(); self.assertEqual(self.z.stav.nazev, "Rozpracováno")

    def test_chyba_v_kopii_neulozi_nic(self):
        from .models import ProvedenyUkon
        r = self.client.post(self.url("provedenyukon"), {"zakazka": self.z.pk, "typ_ukonu": self.t.pk, "cena": "100", "sazba_dph": "21", "dalsi": ["1"],
                                                        "d1-cena": "200", "d1-sazba_dph": "21"})  # chybí typ úkonu
        self.assertEqual(r.status_code, 200); self.assertFalse(ProvedenyUkon.objects.exists())
        self.assertContains(r, 'name="d1-cena"'); self.assertContains(r, 'value="200"'); self.assertContains(r, 'data-dalsi="2"')

    def test_vice_materialu_najednou(self):
        from .models import PouzityMaterial
        r = self.client.post(self.url("pouzitymaterial"), {"zakazka": self.z.pk, "material": self.m.pk, "mnozstvi": "2", "sazba_dph": "21", "dalsi": ["1"],
                                                          "d1-material": self.m2.pk, "d1-mnozstvi": "10", "d1-sazba_dph": "21"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sorted((p.material.nazev, p.mnozstvi, p.jednotkova_cena) for p in PouzityMaterial.objects.filter(zakazka=self.z)),
                         [("Kabel", Decimal("2"), Decimal("50")), ("Šroub", Decimal("10"), Decimal("2"))])


class BarvaStavuTest(TestCase):
    """Barvu stavu zakázky si uživatel nastaví v Nastavení → Stavy zakázek; štítky stavu ji pak používají všude."""
    def setUp(self):
        from .models import StavZakazky, Zakazka
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(uzivatel("u", "Administrátor"))
        self.s = StavZakazky.objects.create(nazev="Reklamace", poradi=9)
        self.z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), stav=self.s)

    def test_vychozi_barvy(self):
        from .models import StavZakazky
        self.assertEqual(StavZakazky.objects.get(nazev="Rozpracováno").barva, "#b45309")
        self.assertEqual(self.s.barva, "#0dcaf0")

    def test_zmena_barvy_a_stitky(self):
        r = self.client.post(reverse("edit", args=["stavzakazky", self.s.pk]), {"nazev": "Reklamace", "poradi": 9, "barva": "#fd7e14", "aktivni": "on"})
        self.assertEqual(r.status_code, 302); self.s.refresh_from_db(); self.assertEqual(self.s.barva, "#fd7e14")
        pravidlo = f".bg-stav-{self.s.pk}{{background-color:#fd7e14!important;color:#212529!important}}"
        for url in (reverse("plocha", args=[self.z.pk]), reverse("list", args=["zakazka"]) + "?v=kan", reverse("list", args=["zakazka"]) + "?v=tab", reverse("zarizeni_prehled")):
            html = self.client.get(url).content.decode()
            self.assertIn(pravidlo, html, url)
        self.assertIn(f"bg-stav-{self.s.pk}", self.client.get(reverse("plocha", args=[self.z.pk])).content.decode())
        self.assertIn('type="color"', self.client.get(reverse("edit", args=["stavzakazky", self.s.pk])).content.decode())

    def test_neplatna_barva(self):
        r = self.client.post(reverse("edit", args=["stavzakazky", self.s.pk]), {"nazev": "Reklamace", "poradi": 9, "barva": "oranžová", "aktivni": "on"})
        self.assertEqual(r.status_code, 200); self.s.refresh_from_db(); self.assertEqual(self.s.barva, "#0dcaf0")

    def test_kontrast_textu(self):
        from .models import StavZakazky
        self.assertEqual(StavZakazky(barva="#ffc107").barva_textu, "#212529")
        self.assertEqual(StavZakazky(barva="#212529").barva_textu, "#fff")
        self.assertEqual(StavZakazky(barva="#0d6efd").barva_textu, "#fff"); self.assertEqual(StavZakazky(barva="#198754").barva_textu, "#fff")


class PoradiStavuTest(TestCase):
    """Nový stav dostane pořadí jako další v řadě; zvolené obsazené místo posune ostatní stavy."""
    def setUp(self):
        from .models import StavZakazky
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(uzivatel("u", "Administrátor"))
        self.S = StavZakazky

    def poradi(self): return list(self.S.objects.order_by("poradi").values_list("nazev", "poradi"))

    def test_predvyplneni_dalsiho_poradi(self):
        self.assertEqual(self.S.dalsi_poradi(), 8)
        html = self.client.get(reverse("create", args=["stavzakazky"])).content.decode()
        self.assertRegex(html, r'name="poradi" value="8"')

    def test_vlozeni_na_obsazene_misto(self):
        self.client.post(reverse("create", args=["stavzakazky"]), {"nazev": "Reklamace", "poradi": 4, "barva": "#fd7e14", "aktivni": "on"})
        p = self.poradi()
        self.assertEqual(p[4], ("Reklamace", 4)); self.assertEqual(p[5], ("Opraveno", 5)); self.assertEqual(p[-1], ("Zrušeno", 8))
        self.assertEqual([x for _, x in p], list(range(9)))

    def test_presun_existujiciho(self):
        s = self.S.objects.get(nazev="Čeká na schválení"); s.poradi = 5; s.save()  # z 2 na 5
        self.assertEqual([x for _, x in self.poradi()], list(range(8)))
        self.assertEqual(self.poradi()[5], ("Čeká na schválení", 5)); self.assertEqual(self.poradi()[2], ("Čeká na díl", 2))
        s.poradi = 0; s.save()  # z 5 na 0
        self.assertEqual(self.poradi()[0], ("Čeká na schválení", 0)); self.assertEqual(self.poradi()[1], ("Nová", 1))
        self.assertEqual([x for _, x in self.poradi()], list(range(8)))


class NovaRoleVeFormulariZamestnanceTest(TestCase):
    """Ve formuláři zaměstnance jde založit novou roli v okně a formulář se neopouští (jako nový zákazník / zařízení u zakázky)."""
    def setUp(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("admin", password="x", is_staff=True))

    def test_tlacitko_ve_formulari(self):
        r = self.client.get(reverse("create", args=["zamestnanec"]))
        self.assertContains(r, "+ Nová role"); self.assertContains(r, reverse("lookup_new", args=["role"]))

    def test_zalozeni_role_v_okne(self):
        from .models import Opravneni, Role
        r = self.client.get(reverse("lookup_new", args=["role"]))
        self.assertContains(r, "Nová role"); self.assertContains(r, 'name="opravneni"')
        op = Opravneni.objects.order_by("pk")[:2]
        r = self.client.post(reverse("lookup_new", args=["role"]), {"nazev": "Skladník", "popis": "Sklad", "opravneni": [o.pk for o in op]})
        role = Role.objects.get(nazev="Skladník")
        self.assertEqual(r.json()["id"], role.pk); self.assertEqual(r.json()["label"], "Skladník")
        self.assertEqual(set(role.opravneni.all()), set(op)); self.assertTrue(role.aktivni)
        r = self.client.post(reverse("lookup_new", args=["role"]), {"nazev": "skladník"})  # duplicita se nezaloží
        self.assertEqual(r.status_code, 400); self.assertContains(r, "už existuje", status_code=400)
        self.assertEqual(Role.objects.filter(nazev__iexact="skladník").count(), 1)

    def test_bez_nastaveni_roli_nezalozi(self):
        from .models import Role
        self.client.force_login(uzivatel("u"))
        r = self.client.post(reverse("lookup_new", args=["role"]), {"nazev": "Šéf", "je_administrator": "on"})
        self.assertIn(r.status_code, (302, 403)); self.assertFalse(Role.objects.filter(nazev="Šéf").exists())


class PrvniNastaveniTest(TestCase):
    """Nastavení → První nastavení: kroky pro administrátora po prvním spuštění a upozornění na pracovní ploše."""
    def setUp(self):
        from .pruvodce import PrvniSpusteniMiddleware
        PrvniSpusteniMiddleware.hotovo = False
        NastaveniFirmy.objects.all().delete()

    def _pruvodce(self):
        self.client.post(reverse("pruvodce_ucet"), {"username": "sef", "first_name": "Jan", "last_name": "Novák", "email": "",
                                                    "password1": "Tajne-heslo-123", "password2": "Tajne-heslo-123"})
        self.client.post(reverse("pruvodce_firma"), {"nazev_firmy": "Servis Novák"})
        return User.objects.get(username="sef")

    def test_pruvodce_zalozi_kartu_administratora(self):
        from .models import Zamestnanec
        u = self._pruvodce(); z = Zamestnanec.objects.get(uzivatel=u)
        self.assertEqual((z.jmeno, z.prijmeni), ("Jan", "Novák")); self.assertTrue(z.role.filter(nazev="Administrátor").exists())

    def test_kroky_a_upozorneni(self):
        from .models import TypUkonu
        self._pruvodce()
        r = self.client.get(reverse("nastaveni"))
        for t in ("První nastavení aplikace", "0 z 4 povinných kroků", "Typy úkonů", "Číslování dokladů"): self.assertContains(r, t)
        self.assertContains(self.client.get("/"), "Dokončete první nastavení")
        TypUkonu.objects.create(nazev="Diagnostika"); f = NastaveniFirmy.objects.get()
        f.ico, f.adresa, f.cislo_uctu = "12345678", "Hlavní 1, Praha", "123456789/0100"; f.save()
        self.client.post(reverse("create", args=["zamestnanec"]), {"jmeno": "Petr", "prijmeni": "Dvořák", "role": [], "ucet_aktivni": "on",
                                                                    "ucet_jmeno": "petr", "ucet_heslo": "Tajne-heslo-456", "ucet_heslo2": "Tajne-heslo-456"})
        self.assertContains(self.client.get(reverse("nastaveni")), "3 z 4 povinných kroků")  # role Zaměstnanec se za úpravu rolí nepočítá
        from .models import Role, Zamestnanec
        Zamestnanec.objects.get(jmeno="Petr").role.add(Role.objects.get(nazev="Technik"))
        self.assertContains(self.client.get(reverse("nastaveni")), "4 z 4 povinných kroků")
        self.assertNotContains(self.client.get("/"), "Dokončete první nastavení")

    def test_skryti_upozorneni(self):
        self._pruvodce()
        self.assertRedirects(self.client.post(reverse("nastaveni_prvni") + "?next=/", {"skryt": "1"}), "/", fetch_redirect_response=False)
        self.assertTrue(NastaveniFirmy.objects.get().prvni_nastaveni_skryto)
        self.assertNotContains(self.client.get("/"), "Dokončete první nastavení")
        self.assertContains(self.client.get(reverse("nastaveni")), "Znovu zobrazit upozornění")

    def test_zamestnanec_upozorneni_nevidi(self):
        self._pruvodce(); self.client.logout()
        self.client.force_login(uzivatel("t", role="Technik"))
        self.assertNotContains(self.client.get("/"), "Dokončete první nastavení")
        self.assertRedirects(self.client.post(reverse("nastaveni_prvni"), {"skryt": "1"}), reverse("dashboard"), fetch_redirect_response=False)
        self.assertFalse(NastaveniFirmy.objects.get().prvni_nastaveni_skryto)


class SystemModuluTest(TestCase):
    """Volitelné moduly (core/moduly.py): nalezení ve složce moduly/, zápis do Nastavení, tlačítka a oprávnění stránek modulu."""
    def setUp(self):
        from unittest import mock
        from . import moduly
        p = mock.patch.dict(moduly.REGISTR, clear=True); p.start(); self.addCleanup(p.stop)  # testy nezávisí na nainstalovaných modulech
        self.moduly = moduly

    def test_najde_jen_platne_moduly(self):
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp()); (d / "moduly").mkdir()
        for nazev, soubory in (("sklad", ("__init__.py", "apps.py")), ("dochazka", ("__init__.py", "apps.py")), ("bez_apps", ("__init__.py",)), ("Spatny-nazev", ("__init__.py", "apps.py"))):
            (d / "moduly" / nazev).mkdir()
            for s in soubory: (d / "moduly" / nazev / s).write_text("")
        (d / "moduly" / "README.md").write_text("")
        self.assertEqual(self.moduly.najdi_moduly(d), ["dochazka", "sklad"])
        self.assertEqual(self.moduly.najdi_moduly(d, "sklad, x"), ["dochazka"])  # MODULY_VYPNUTE
        self.assertEqual(self.moduly.najdi_moduly(Path(tempfile.mkdtemp())), [])  # bez složky moduly

    def test_nastaveni_bez_modulu_a_s_modulem(self):
        self.client.force_login(uzivatel("admin", "Administrátor"))
        self.assertContains(self.client.get(reverse("nastaveni")), "Není nainstalovaný žádný modul")
        self.moduly.registruj(self.moduly.Modul(kod="sklad", nazev="Sklad", verze="0.1", popis="Evidence skladu.", pozadavky="nic",
                                                nastaveni=[("Sklad – nastavení", "nastaveni_firma"), ("Neexistující", "neni:adresa")]))
        r = self.client.get(reverse("nastaveni"))
        self.assertContains(r, "Sklad"); self.assertContains(r, "verze 0.1"); self.assertContains(r, reverse("nastaveni_firma"))
        self.assertNotContains(r, "Neexistující")  # odkaz na neexistující adresu se vynechá, stránka nespadne

    def test_tlacitka_modulu_na_zakazce(self):
        from .models import Zakazka
        z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(firma="Firma"))
        def akce(request, zak): return [dict(text="Akce modulu", url=f"/kalendar/?zakazka={zak.pk}")]
        def chyba(request, zak): raise RuntimeError("chyba v modulu")
        self.moduly.registruj(self.moduly.Modul(kod="a", nazev="A", akce_zakazky=akce))
        self.moduly.registruj(self.moduly.Modul(kod="b", nazev="B", akce_zakazky=chyba))
        self.client.force_login(uzivatel("tech", "Technik"))
        with self.assertLogs("core.moduly", "ERROR"):
            r = self.client.get(reverse("plocha", args=[z.pk]))
        self.assertContains(r, "Akce modulu"); self.assertContains(r, f"/kalendar/?zakazka={z.pk}&next=/plocha/{z.pk}/")

    def test_obrazek_platby_na_miste_od_modulu(self):
        from .models import StavZakazky, Zakazka
        z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(firma="Firma"), stav=StavZakazky.objects.create(nazev="Připraveno k vyzvednutí"))
        self.client.force_login(uzivatel("tech", "Technik"))
        self.assertNotContains(self.client.get(reverse("plocha", args=[z.pk])), 'id="bm-pl-obr"')  # bez modulu okno beze změny
        def qr(request, zak, zpusob): return f"/kalendar/?qr={zak.pk}" if zpusob == "QR kód" else None
        def chyba(request, zak, zpusob): raise RuntimeError("chyba v modulu")
        self.moduly.registruj(self.moduly.Modul(kod="a", nazev="A", platba_na_miste=qr))
        self.moduly.registruj(self.moduly.Modul(kod="b", nazev="B", platba_na_miste=chyba))
        with self.assertLogs("core.moduly", "ERROR"):
            r = self.client.get(reverse("plocha", args=[z.pk]))
        self.assertContains(r, 'id="bm-pl-obr"'); self.assertContains(r, f'{{"QR k\\u00f3d": "/kalendar/?qr={z.pk}"}}')

    def test_opravneni_stranek_modulu(self):
        from . import prava as P
        self.moduly.registruj(self.moduly.Modul(kod="s", nazev="S", prava={"s:nastaveni": {P.NASTAVENI}}))
        self.assertEqual(P.potrebna_prava("s:nastaveni", {}), [{P.PRISTUP}, {P.NASTAVENI}])
        self.assertEqual(P.potrebna_prava("s:prehled", {}), [{P.PRISTUP}])  # bez záznamu stačí základní přístup


class BezpecnostTest(TestCase):
    """Opravy z bezpečnostního auditu (docs/12-bezpecnost.md): nahrávání a odesílání souborů, mazání cizích souborů,
    přesměrování po uložení formuláře, soubory podle oprávnění a ochrana účtu hlavního administrátora."""
    def setUp(self):
        import tempfile
        from django.test import override_settings
        from .models import Zakazka
        self.media = override_settings(MEDIA_ROOT=tempfile.mkdtemp()); self.media.enable(); self.addCleanup(self.media.disable)
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan Novák"))

    @staticmethod
    def soubor(jmeno, obsah=b"<script>alert(1)</script>", typ="text/html"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(jmeno, obsah, content_type=typ)

    @staticmethod
    def png(jmeno="a.png"):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        b = BytesIO(); Image.new("RGB", (2, 2)).save(b, "PNG"); return SimpleUploadedFile(jmeno, b.getvalue(), content_type="image/png")

    # --- 1. Skript v nahraném souboru se nesmí spustit
    def test_priloha_html_ani_svg_nejde_nahrat(self):
        from .models import Priloha
        self.client.force_login(uzivatel("zam", "Zaměstnanec"))
        for jmeno in ("faktura.html", "obrazek.svg", "stranka.htm"):
            r = self.client.post(reverse("create", args=["priloha"]), {"nazev": "X", "soubor": self.soubor(jmeno), "zakazky": [self.z.pk]})
            self.assertEqual(r.status_code, 200); self.assertContains(r, "Tento typ souboru nelze nahrát")
        self.assertFalse(Priloha.objects.exists())
        r = self.client.post(reverse("create", args=["priloha"]), {"nazev": "Protokol", "soubor": self.soubor("protokol.pdf", b"%PDF-1.4", "application/pdf"), "zakazky": [self.z.pk]})
        self.assertEqual(r.status_code, 302); self.assertTrue(Priloha.objects.filter(nazev="Protokol").exists())

    def test_podvrzena_fotka_nejde_nahrat(self):
        """Typ image/png hlášený prohlížečem nestačí, fotku ověří Pillow (formulář fotek i nová zakázka)."""
        from .models import Fotografie, Zakazka
        self.client.force_login(uzivatel("zam", "Zaměstnanec"))
        r = self.client.post(reverse("create", args=["fotografie"]), {"zakazka": self.z.pk, "soubory": [self.soubor("fotka.html", typ="image/png")]})
        self.assertEqual(r.status_code, 200); self.assertContains(r, "není obrázek")
        r = self.client.post(reverse("create", args=["fotografie"]), {"zakazka": self.z.pk, "soubory": [self.soubor("fotka.png", typ="image/png")]})
        self.assertContains(r, "není obrázek"); self.assertFalse(Fotografie.objects.exists())
        r = self.client.post(reverse("zakazka_nova"), {"zakaznik": self.z.zakaznik_id, "fotky": [self.soubor("x.html", typ="image/png"), self.png("ok.png")]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual([f.soubor.name.rsplit("/", 1)[-1] for f in Fotografie.objects.all()], ["ok.png"])
        self.assertEqual(Zakazka.objects.count(), 2)

    def test_prijata_faktura_jen_povolene_pripony(self):
        self.client.force_login(uzivatel("ucetni", "Administrativa"))
        r = self.client.post(reverse("prijata_faktura_import"), {"soubor": self.soubor("faktura.html", b"<Invoice/>")})
        self.assertContains(r, "Nahrajte fakturu ve formátu ISDOC")

    def test_soubory_se_posilaji_s_bezpecnymi_hlavickami(self):
        """I soubor, který se do složky media dostal jinak (starší data), se jen stáhne a skript v něm neběží."""
        from django.core.files.storage import default_storage
        self.client.force_login(uzivatel("zam", "Zaměstnanec"))
        default_storage.save("prilohy/stary.html", self.soubor("stary.html")); default_storage.save("prilohy/foto.png", self.png())
        default_storage.save("prilohy/navod.pdf", self.soubor("navod.pdf", b"%PDF-1.4"))
        r = self.client.get("/media/prilohy/stary.html")
        self.assertEqual(r.status_code, 200); self.assertEqual(r["Content-Disposition"], "attachment")
        self.assertEqual(r["Content-Security-Policy"], "sandbox"); self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        for cesta in ("/media/prilohy/foto.png", "/media/prilohy/navod.pdf"):  # obrázky a PDF se dál zobrazují v náhledu
            r = self.client.get(cesta)
            self.assertEqual(r.status_code, 200); self.assertNotIn("attachment", r.get("Content-Disposition", "")); self.assertFalse(r.has_header("Content-Security-Policy"))

    # --- 2. Fotku a přílohu smaže jen ten, kdo ji nahrál (nebo kdo má oprávnění Mazání)
    def test_cizi_fotku_nesmaze(self):
        from django.core.files.base import ContentFile
        from .models import Fotografie
        autor, jiny = uzivatel("autor", "Zaměstnanec"), uzivatel("jiny", "Zaměstnanec")
        f = Fotografie.objects.create(zakazka=self.z, soubor=ContentFile(b"x", name="a.png"), nahral=autor)
        self.client.force_login(jiny)
        self.assertNotIn(reverse("delete", args=["fotografie", f.pk]), self.client.get(reverse("plocha", args=[self.z.pk])).content.decode())
        self.client.post(reverse("delete", args=["fotografie", f.pk]))
        self.assertTrue(Fotografie.objects.filter(pk=f.pk).exists())
        self.client.force_login(autor)
        self.client.post(reverse("delete", args=["fotografie", f.pk]))
        self.assertFalse(Fotografie.objects.filter(pk=f.pk).exists())

    def test_spravce_s_opravnenim_mazani_smaze_cizi_prilohu(self):
        from django.core.files.base import ContentFile
        from .models import Priloha
        p = Priloha.objects.create(nazev="P", soubor=ContentFile(b"x", name="p.pdf"), nahral=uzivatel("autor", "Zaměstnanec"))
        self.client.force_login(uzivatel("sef", "Administrátor"))
        self.client.post(reverse("delete", args=["priloha", p.pk]))
        self.assertFalse(Priloha.objects.filter(pk=p.pk).exists())

    # --- 3. Přesměrování po uložení jen v rámci aplikace
    def test_next_nepresmeruje_na_cizi_web(self):
        self.client.force_login(uzivatel("zam", "Zaměstnanec"))
        for nx in ("/\\zly.example", "//zly.example", "https://zly.example/", "/\t/zly.example"):
            r = self.client.post(reverse("create", args=["zakaznik"]) + "?" + __import__("urllib.parse").parse.urlencode({"next": nx}),
                                 {"typ_zakaznika": "Soukromá osoba", "jmeno": f"Test {nx}", "aktivni": "on"})
            self.assertEqual(r.status_code, 302); self.assertNotIn("zly.example", r["Location"])
        r = self.client.post(reverse("create", args=["zakaznik"]) + "?next=/kalendar/", {"typ_zakaznika": "Soukromá osoba", "jmeno": "Ok", "aktivni": "on"})
        self.assertEqual(r["Location"], "/kalendar/")

    # --- 4. Soubory přijatých faktur a šablon jen s oprávněním
    def test_soubor_prijate_faktury_jen_s_opravnenim_faktury(self):
        from django.core.files.storage import default_storage
        default_storage.save("prijate_faktury/2026/dodavatel.pdf", self.soubor("dodavatel.pdf", b"%PDF-1.4"))
        self.client.force_login(uzivatel("technik", "Technik"))
        self.assertEqual(self.client.get("/media/prijate_faktury/2026/dodavatel.pdf").status_code, 403)
        self.assertEqual(self.client.get("/media/fotky/../prijate_faktury/2026/dodavatel.pdf").status_code, 403)  # obejití přes ../
        self.client.force_login(uzivatel("ucetni", "Administrativa"))
        self.assertEqual(self.client.get("/media/prijate_faktury/2026/dodavatel.pdf").status_code, 200)

    # --- 6. Účet hlavního administrátora mění jen hlavní administrátor
    def test_ucet_hlavniho_administratora_nezmeni_spravce_s_nastavenim(self):
        from .models import Role, Zamestnanec
        hlavni = User.objects.create_superuser("hlavni", password="Puvodni-heslo-42")
        zh = Zamestnanec.objects.create(jmeno="Hlavní", prijmeni="Admin", uzivatel=hlavni)
        r = Role.objects.create(nazev="Kancelář"); r.opravneni.set(Role.objects.get(nazev="Administrativa").opravneni.all())
        r.opravneni.add(*__import__("core.models", fromlist=["Opravneni"]).Opravneni.objects.filter(kod="nastaveni.spravovat"))
        self.client.force_login(uzivatel("kancelar", "Kancelář"))
        d = {"jmeno": "Hlavní", "prijmeni": "Admin", "aktivni": "on", "role": [], "ucet_aktivni": "on", "ucet_jmeno": "hlavni", "ucet_admin": "on",
             "ucet_heslo": "Nove-heslo-4242", "ucet_heslo2": "Nove-heslo-4242"}
        r = self.client.post(reverse("edit", args=["zamestnanec", zh.pk]), d)
        self.assertContains(r, "může měnit jen hlavní administrátor")
        hlavni.refresh_from_db(); self.assertTrue(hlavni.check_password("Puvodni-heslo-42"))
        r = self.client.post(reverse("edit", args=["zamestnanec", zh.pk]), dict(d, ucet_heslo="", ucet_heslo2="", ucet_aktivni=""))
        hlavni.refresh_from_db(); self.assertTrue(hlavni.is_active)
        bez_uctu = {k: v for k, v in d.items() if not k.startswith("ucet_heslo")}
        r = self.client.post(reverse("edit", args=["zamestnanec", zh.pk]), dict(bez_uctu, prijmeni="Administrátor"))  # ostatní údaje karty změnit smí
        self.assertEqual(r.status_code, 302); zh.refresh_from_db(); self.assertEqual(zh.prijmeni, "Administrátor")
        self.client.force_login(hlavni)
        r = self.client.post(reverse("edit", args=["zamestnanec", zh.pk]), d)
        self.assertEqual(r.status_code, 302); hlavni.refresh_from_db(); self.assertTrue(hlavni.check_password("Nove-heslo-4242"))


class BezpecneNastaveniTest(TestCase):
    """Výchozí nastavení bez .env je bezpečné: žádný pevný SECRET_KEY z repozitáře, DEBUG jen výslovně (config/settings.py)."""
    def test_tajny_klic_se_vygeneruje_a_ulozi(self):
        import os, tempfile
        from pathlib import Path
        from unittest import mock
        from config import settings as s
        d = Path(tempfile.mkdtemp())
        with mock.patch.object(s, "BASE_DIR", d), mock.patch.dict(os.environ, {}, clear=True):
            k1 = s._tajny_klic(); k2 = s._tajny_klic()
            self.assertGreaterEqual(len(k1), 50); self.assertEqual(k1, k2); self.assertEqual((d / ".secret_key").read_text(), k1)
            self.assertNotIn("dev-zmen", k1)
        with mock.patch.object(s, "BASE_DIR", d), mock.patch.dict(os.environ, {"SECRET_KEY": "z-env"}, clear=True):
            self.assertEqual(s._tajny_klic(), "z-env")

    def test_env_se_nacte_a_promenne_prostredi_maji_prednost(self):
        import os, tempfile
        from pathlib import Path
        from unittest import mock
        from config import settings as s
        f = Path(tempfile.mkdtemp()) / ".env"
        f.write_text("# komentář\nDEBUG=1\nALLOWED_HOSTS=a,b\nSECRET_KEY=\"x y\"\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"ALLOWED_HOSTS": "jine"}, clear=True):
            s._nacti_env(f)
            self.assertEqual(os.environ["DEBUG"], "1"); self.assertEqual(os.environ["ALLOWED_HOSTS"], "jine"); self.assertEqual(os.environ["SECRET_KEY"], "x y")
        f.write_text("DEBUG=1\n", encoding="utf-16")  # PowerShell: echo DEBUG=1 > .env
        with mock.patch.dict(os.environ, {}, clear=True):
            s._nacti_env(f); self.assertEqual(os.environ["DEBUG"], "1")


class LimitVelikostiSouboruTest(TestCase):
    """Limit velikosti nahrávaných souborů (core/soubory.py): jeden soubor i celé nahrání najednou."""
    def setUp(self):
        import tempfile
        from django.test import override_settings
        from .models import Zakazka
        self.nastaveni = override_settings(MEDIA_ROOT=tempfile.mkdtemp(), MAX_VELIKOST_SOUBORU_MB=1, MAX_VELIKOST_NAHRAVANI_MB=2)
        self.nastaveni.enable(); self.addCleanup(self.nastaveni.disable)
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan Novák"))
        self.client.force_login(uzivatel("zam", "Zaměstnanec"))

    def test_prilis_velka_priloha_se_neulozi(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Priloha
        velka = SimpleUploadedFile("sken.pdf", b"%PDF" + b"0" * (1024 * 1024 + 10), content_type="application/pdf")
        r = self.client.post(reverse("create", args=["priloha"]), {"nazev": "X", "soubor": velka, "zakazky": [self.z.pk]})
        self.assertEqual(r.status_code, 200); self.assertContains(r, "je příliš velký"); self.assertContains(r, "1 MB")
        self.assertFalse(Priloha.objects.exists())
        mala = SimpleUploadedFile("sken.pdf", b"%PDF" + b"0" * 1000, content_type="application/pdf")
        self.client.post(reverse("create", args=["priloha"]), {"nazev": "X", "soubor": mala, "zakazky": [self.z.pk]})
        self.assertTrue(Priloha.objects.exists())

    def test_prilis_velka_fotka_se_neulozi(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Fotografie
        velka = SimpleUploadedFile("foto.png", b"0" * (1024 * 1024 + 10), content_type="image/png")
        r = self.client.post(reverse("create", args=["fotografie"]), {"zakazka": self.z.pk, "soubory": [velka]})
        self.assertEqual(r.status_code, 200); self.assertContains(r, "je příliš velký"); self.assertFalse(Fotografie.objects.exists())

    def test_prilis_velke_nahrani_odmitne_hned(self):
        r = self.client.generic("POST", reverse("create", args=["fotografie"]), b"x", CONTENT_LENGTH=str(3 * 1024 * 1024))
        self.assertEqual(r.status_code, 413); self.assertIn("příliš velké", r.content.decode())


class PlatbaNaMisteTest(TestCase):
    """Vydání zakázky se zaplacením na místě bez faktury (hotově, QR kódem, kartou), typicky jen poplatek za diagnostiku."""
    def setUp(self):
        from .models import StavZakazky, Zakazka, TypUkonu, ProvedenyUkon
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis", vychozi_dph=Decimal("21"))
        self.client.force_login(uzivatel("tech", role="Technik"))  # vydává i technik bez oprávnění k fakturám
        self.z = Zakazka.objects.create(zakaznik=Zakaznik.objects.create(jmeno="Jan"), stav=StavZakazky.objects.create(nazev="Připraveno k vyzvednutí"))
        ProvedenyUkon.objects.create(zakazka=self.z, typ_ukonu=TypUkonu.objects.create(nazev="Diagnostika"), cena=Decimal("500"), sazba_dph=Decimal("21"))

    def vydat(self, **data):
        return self.client.post(reverse("stav_akce", args=[self.z.pk]), {"akce": "vydat", **data})

    def test_dialog_vydani_nabidne_platbu_s_castkou_zakazky(self):
        r = self.client.get(reverse("plocha", args=[self.z.pk]))
        self.assertContains(r, 'id="bm-vydat"'); self.assertContains(r, "Zaplaceno na místě bez faktury")
        self.assertContains(r, 'name="castka" inputmode="decimal" value="605"')  # 500 Kč + 21 % DPH
        self.assertContains(r, "<option>QR kód</option>")

    def test_vydani_se_zaplacenim_na_miste(self):
        from .models import Platba, KalendarUdalost, HistorieZmen
        self.vydat(platba="na_miste", castka="300,50", zpusob="QR kód", poznamka="Poplatek za diagnostiku")
        self.z.refresh_from_db(); self.assertEqual(self.z.stav.nazev, "Vydáno")
        p = Platba.objects.get()
        self.assertEqual((p.zakazka, p.faktura, p.stav, p.zpusob, p.castka, p.poznamka), (self.z, None, "Zaplaceno", "QR kód", Decimal("300.50"), "Poplatek za diagnostiku"))
        self.assertTrue(KalendarUdalost.objects.filter(typ="Zaplaceno", zakazka=self.z).exists())
        self.assertTrue(HistorieZmen.objects.filter(akce="Platba na místě", id_objektu=self.z.pk).exists())
        r = self.client.get(reverse("plocha", args=[self.z.pk]))
        self.assertContains(r, "Zaplaceno na místě: 300,50 Kč (QR kód)"); self.assertNotContains(r, 'id="bm-vydat"')

    def test_chybna_castka_zakazku_nevyda(self):
        from .models import Platba
        self.vydat(platba="na_miste", castka="", zpusob="Hotově")
        self.vydat(platba="na_miste", castka="100", zpusob="Bankovní převod")  # převod není platba na místě
        self.z.refresh_from_db(); self.assertEqual(self.z.stav.nazev, "Připraveno k vyzvednutí"); self.assertFalse(Platba.objects.exists())

    def test_vydani_bez_platby_a_dodatecny_zapis(self):
        from .models import Platba
        self.vydat(platba="", castka="605", zpusob="Hotově")
        self.z.refresh_from_db(); self.assertEqual(self.z.stav.nazev, "Vydáno"); self.assertFalse(Platba.objects.exists())
        r = self.client.get(reverse("plocha", args=[self.z.pk])); self.assertContains(r, "Platba není zapsaná"); self.assertContains(r, 'value="zaplaceno"')
        self.client.post(reverse("stav_akce", args=[self.z.pk]), {"akce": "zaplaceno", "castka": "605", "zpusob": "Hotově"})
        self.client.post(reverse("stav_akce", args=[self.z.pk]), {"akce": "zaplaceno", "castka": "605", "zpusob": "Hotově"})  # podruhé se nezapíše
        self.assertEqual(Platba.objects.get().castka, Decimal("605")); self.z.refresh_from_db(); self.assertEqual(self.z.stav.nazev, "Vydáno")

    def test_s_fakturou_je_vychozi_bez_platby(self):
        r = self.client.get(reverse("plocha", args=[self.z.pk])); self.assertContains(r, 'id="bm-pl-ano" checked')
        Faktura.objects.create(zakaznik=self.z.zakaznik).zakazky.add(self.z)
        r = self.client.get(reverse("plocha", args=[self.z.pk])); self.assertContains(r, 'id="bm-pl-ne" checked'); self.assertContains(r, "K zakázce je vystavena faktura")

    def test_po_zaplaceni_na_miste_se_nedoporucuje_faktura(self):
        from .models import Platba
        self.client.force_login(uzivatel("admin", role="Administrátor"))
        self.assertContains(self.client.get(reverse("plocha", args=[self.z.pk])), 'class="btn btn-success" href="/faktura/z-zakazky/')
        Platba.objects.create(zakazka=self.z, stav="Zaplaceno", zpusob="Hotově", castka=Decimal("605"))
        self.assertNotContains(self.client.get(reverse("plocha", args=[self.z.pk])), 'class="btn btn-success" href="/faktura/z-zakazky/')


class OknoFiltrovatTest(TestCase):
    """Okno „Filtrovat“ v Kalendáři a Zařízení: v každé skupině jde zaškrtnout víc voleb, nic = vše."""
    def setUp(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        self.client.force_login(User.objects.create_user("a", password="x", is_staff=True))

    def test_kalendar_vic_typu_a_zamestnancu(self):
        from datetime import datetime
        from django.utils import timezone
        from .models import KalendarUdalost, Zamestnanec
        eva, petr = Zamestnanec.objects.create(jmeno="Eva"), Zamestnanec.objects.create(jmeno="Petr")
        dt = timezone.make_aware(datetime(2026, 11, 10, 9))
        for nazev, typ, zam in [("Schůzka", "Vlastní událost", eva), ("Platba", "Zaplaceno", petr), ("Přijato", "Přijetí zakázky", eva)]:
            KalendarUdalost.objects.create(nazev=nazev, datum=dt, typ=typ).zamestnanci.add(zam)
        url = reverse("kalendar") + "?v=month&d=2026-11-10"
        nazvy = lambda r: {e.nazev for c in r.context["days"] for e in c["ev"]}
        self.assertEqual(nazvy(self.client.get(url)), {"Schůzka", "Platba", "Přijato"})
        r = self.client.get(url + "&typ=Vlastní událost&typ=Zaplaceno")
        self.assertEqual(nazvy(r), {"Schůzka", "Platba"})
        self.assertContains(r, 'class="bm-filtr-n">2<'); self.assertContains(r, "bm-filtr-st")
        self.assertEqual(nazvy(self.client.get(url + f"&zam={eva.pk}")), {"Schůzka", "Přijato"})
        self.assertEqual(nazvy(self.client.get(url + f"&typ=Zaplaceno&zam={eva.pk}")), set())
        self.assertEqual(nazvy(self.client.get(url + "&typ=Neexistuje")), {"Schůzka", "Platba", "Přijato"})  # neplatná volba se ignoruje

    def test_zarizeni_vic_skupin_a_umisteni(self):
        from .models import StavZakazky, Zakazka, Zarizeni
        z = Zakaznik.objects.create(jmeno="Jana", typ_zakaznika="Soukromá osoba")
        dil = Zarizeni.objects.create(zakaznik=z, vyrobce="Makita", typ="Dil")
        Zakazka.objects.create(zakaznik=z, stav=StavZakazky.objects.get_or_create(nazev="Čeká na díl")[0]).zarizeni.add(dil)
        Zarizeni.objects.create(zakaznik=z, vyrobce="Bosch", typ="Bez"); Zarizeni.objects.create(zakaznik=z, vyrobce="Narex", typ="Stary", aktivni=False)
        url = reverse("zarizeni_prehled")
        typy = lambda q: {r["d"].typ for r in self.client.get(url + q).context["rows"]}
        self.assertEqual(typy(""), {"Dil", "Bez"})
        self.assertEqual(typy("?f=dil&f=bez"), {"Dil", "Bez"})
        self.assertEqual(typy("?f=dil"), {"Dil"})
        self.assertEqual(typy("?f=neaktivni"), {"Stary"})
        self.assertEqual(typy("?f=neaktivni&f=bez"), {"Bez", "Stary"})
        self.assertEqual(typy("?fi=ano"), {"Dil"}); self.assertEqual(typy("?fi=ne"), {"Bez"}); self.assertEqual(typy("?fi=ano&fi=ne"), {"Dil", "Bez"})
        r = self.client.get(url + "?f=dil&f=bez")
        self.assertContains(r, 'name="f" value="dil" checked'); self.assertContains(r, 'href="?f=bez"')  # štítek odebere jen svou volbu
        # stavy poslední zakázky jsou v okně Filtrovat (víc naráz, s počty), řádek stavů nad tabulkou už není
        from urllib.parse import urlencode
        st = lambda *x: "?" + urlencode([("st", v) for v in x])
        self.assertEqual(typy(st("Čeká na díl")), {"Dil"}); self.assertEqual(typy(st("Bez zakázky")), {"Bez"})
        self.assertEqual(typy(st("Čeká na díl", "Bez zakázky")), {"Dil", "Bez"})
        r = self.client.get(url + st("Bez zakázky"))
        self.assertContains(r, 'name="st" value="Bez zakázky" checked'); self.assertNotContains(r, '<nav class="bm-chips'); self.assertContains(r, "Zrušit filtr")

    def test_dokumenty_typ_bez_zrusit_filtr(self):
        r = self.client.get(reverse("dokumenty"), {"typ": "faktura"})
        self.assertContains(r, '<nav class="bm-chips'); self.assertNotContains(r, "Zrušit filtr")  # přepínání typu je jen záložka
        self.assertContains(self.client.get(reverse("dokumenty"), {"typ": "faktura", "q": "x"}), 'href="/dokumenty/?typ=faktura">Zrušit filtr')

    def test_zakazky_stavy_data_a_razeni(self):
        from datetime import datetime
        from django.utils import timezone
        from .models import StavZakazky, Zakazka
        z = Zakaznik.objects.create(jmeno="Jan")
        nova, dil, vyd = (StavZakazky.objects.get_or_create(nazev=n)[0] for n in ("Nová", "Čeká na díl", "Vydáno"))
        t = lambda d: timezone.make_aware(datetime(2026, 11, d, 9))
        a = Zakazka.objects.create(zakaznik=z, stav=nova, datum_prijeti=t(2)); b = Zakazka.objects.create(zakaznik=z, stav=dil, datum_prijeti=t(10))
        c = Zakazka.objects.create(zakaznik=z, stav=vyd, datum_prijeti=t(5), datum_vydani=t(20))
        url = reverse("list", args=["zakazka"])
        pk = lambda q: [o.pk for o, *_ in self.client.get(url + q).context["rows"]]
        self.assertEqual(set(pk("?st=Nová&st=Čeká na díl")), {a.pk, b.pk})
        self.assertEqual(pk("?o=-prijeti"), [b.pk, c.pk, a.pk]); self.assertEqual(pk("?o=prijeti"), [a.pk, c.pk, b.pk])
        self.assertEqual(pk("?o=-vydani")[0], c.pk)
        r = self.client.get(url + "?st=Nová&o=-prijeti")
        self.assertContains(r, 'class="bm-filtr-n">2<'); self.assertNotContains(r, "<nav class=\"bm-chips")
        self.assertContains(r, 'name="o" value="-prijeti" checked'); self.assertNotContains(r, 'type="date"')  # jen Vzestupně / Sestupně
        self.assertContains(r, 'href="?st=Nov%C3%A1"')  # štítek řazení vrátí výchozí řazení
        self.assertContains(self.client.get(url + "?o=cislo"), 'type="hidden" name="o" value="cislo"')  # řazení číslem ze záhlaví zůstane


class UpravaNaMisteTest(TestCase):
    """Detail zařízení a zákazníka: úprava přímo v kartách, náhled fotky ze zakázky vedle údajů, prohlížeč dokumentů na pracovní ploše zakázky."""
    def setUp(self):
        from django.core.files.base import ContentFile
        from .models import Fotografie, Zakazka, Zarizeni
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis", vychozi_dph=Decimal("21"))
        self.c = Zakaznik.objects.create(jmeno="Jan", telefon="602314785")
        self.d = Zarizeni.objects.create(zakaznik=self.c, vyrobce="Narex", typ="ESP", seriove_cislo="NA1")
        self.z = Zakazka.objects.create(zakaznik=self.c); self.z.zarizeni.add(self.d)
        Fotografie.objects.create(zakazka=self.z, soubor=ContentFile(b"x", name="stitek.png"), popis="Štítek")
        self.admin = User.objects.create_user("admin", password="x", is_staff=True); self.client.force_login(self.admin)

    def test_zarizeni_uprava_a_nahled(self):
        r = self.client.get(reverse("detail", args=["zarizeni", self.d.pk]))
        self.assertContains(r, "data-upravit"); self.assertContains(r, 'name="vyrobce"'); self.assertContains(r, 'class="lk position-relative"')
        self.assertContains(r, "Zobrazit fotku / dokument"); self.assertContains(r, 'data-soubor="0"'); self.assertContains(r, 'id="bmv"')
        self.assertEqual(r.context["soubory"][0]["title"], "Štítek")
        r = self.client.post(reverse("edit", args=["zarizeni", self.d.pk]) + f"?next=/zarizeni/{self.d.pk}/",
                             {"zakaznik": self.c.pk, "vyrobce": "Narex", "typ": "ESP 200", "seriove_cislo": "NA1", "popis": "", "aktivni": "on"})
        self.assertRedirects(r, f"/zarizeni/{self.d.pk}/", fetch_redirect_response=False)
        self.d.refresh_from_db(); self.assertEqual(self.d.typ, "ESP 200")

    def test_bez_opravneni_jen_cteni(self):
        self.client.force_login(uzivatel("tech", "Technik"))
        for slug, o in (("zarizeni", self.d), ("zakaznik", self.c)):
            r = self.client.get(reverse("detail", args=[slug, o.pk])); self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, "data-upravit"); self.assertNotContains(r, reverse("edit", args=[slug, o.pk])); self.assertNotContains(r, 'name="aktivni"')

    def test_zakaznik_uprava_karty_informace(self):
        r = self.client.get(reverse("detail", args=["zakaznik", self.c.pk]))
        self.assertContains(r, "data-upravit"); self.assertContains(r, 'name="typ_zakaznika"'); self.assertContains(r, 'name="aktivni"')
        self.assertContains(r, 'class="bm-jen-firma"')

    def test_plocha_prohlizec_v_okne(self):
        r = self.client.get(reverse("plocha", args=[self.z.pk]))
        self.assertContains(r, 'id="bmv"'); self.assertContains(r, "bm-zalozky")


class ChyboveStrankyTest(TestCase):
    """Vlastní stránky 404 a 500 (core/templates/404.html, 500.html), které Django použije při DEBUG=0."""

    def test_404_vlastni_stranka(self):
        from django.test import override_settings
        self.client.force_login(uzivatel())
        with override_settings(DEBUG=False):
            r = self.client.get("/tahle-stranka-neexistuje/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Ups, špatná stránka", status_code=404)
        self.assertContains(r, "Tu klikni a budeš zpět v aplikaci", status_code=404)

    def test_500_bez_databaze(self):
        from django.test import RequestFactory
        from django.views.defaults import server_error
        with self.assertNumQueries(0):
            r = server_error(RequestFactory().get("/"))
        self.assertEqual(r.status_code, 500)
        self.assertIn("Jejda, server šel do opravy", r.content.decode())
        self.assertIn('href="/"', r.content.decode())
class OmezeniPokusuPrihlaseniTest(TestCase):
    """Po 3 špatných heslech se přihlášení zablokuje na 5 minut, po dalších 3 na 10 minut. Blokace je v databázi (přežije restart)."""
    def setUp(self):
        NastaveniFirmy.objects.get_or_create(nazev_firmy="Servis")
        User.objects.create_user("petr", password="Spravne-heslo-1")

    def prihlas(self, heslo, jmeno="petr"):
        return self.client.post(reverse("login"), {"username": jmeno, "password": heslo})

    def zaznam(self):
        from .models import BlokacePrihlaseni
        return BlokacePrihlaseni.objects.get(uzivatelske_jmeno="petr")

    def vyprsi(self):
        from datetime import timedelta
        from django.utils import timezone
        z = self.zaznam(); z.blokovano_do = timezone.now() - timedelta(seconds=1); z.save()

    def minut_blokace(self):
        from django.utils import timezone
        return round((self.zaznam().blokovano_do - timezone.now()).total_seconds() / 60)

    def test_hlaska_o_zbyvajicich_pokusech(self):
        self.assertContains(self.prihlas("spatne"), "Zbývají 2 pokusy")
        self.assertContains(self.prihlas("spatne"), "Zbývá poslední pokus")
        self.assertContains(self.prihlas("spatne"), "zkuste to znovu za 5 minut")

    def test_po_trech_pokusech_nepusti_ani_spravne_heslo(self):
        for _ in range(3): self.prihlas("spatne")
        self.assertEqual(self.minut_blokace(), 5)
        r = self.prihlas("Spravne-heslo-1")
        self.assertEqual(r.status_code, 200); self.assertContains(r, "Přihlášení je zablokované")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(self.client.login(username="petr", password="Spravne-heslo-1"))  # backend blokuje i /admin/ a jiná přihlášení
        self.assertEqual(self.minut_blokace(), 5)  # pokusy během blokace ji neprodlužují

    def test_eskalace_5_a_pak_10_minut(self):
        for _ in range(3): self.prihlas("spatne")
        self.assertEqual(self.minut_blokace(), 5)
        self.vyprsi()
        self.assertContains(self.prihlas("spatne"), "Zbývají 2 pokusy")  # po blokaci znovu 3 pokusy
        for _ in range(2): self.prihlas("spatne")
        self.assertEqual(self.minut_blokace(), 10)
        self.vyprsi()
        for _ in range(3): self.prihlas("spatne")
        self.assertEqual(self.minut_blokace(), 10)  # další blokace zůstávají na 10 minutách

    def test_po_vyprseni_blokace_spravne_heslo_projde_a_vse_se_vynuluje(self):
        from .models import BlokacePrihlaseni
        for _ in range(3): self.prihlas("spatne")
        self.vyprsi()
        self.assertEqual(self.prihlas("Spravne-heslo-1").status_code, 302)
        self.assertFalse(BlokacePrihlaseni.objects.exists())

    def test_po_24_hodinach_se_zacina_znovu_od_5_minut(self):
        from datetime import timedelta
        from django.utils import timezone
        for _ in range(3): self.prihlas("spatne")
        z = self.zaznam(); z.blokovano_do = None; z.pocet_blokaci = 1; z.neuspesne_pokusy = 2
        z.posledni_pokus = timezone.now() - timedelta(hours=25); z.save()
        self.assertContains(self.prihlas("spatne"), "Zbývají 2 pokusy")
        for _ in range(2): self.prihlas("spatne")
        self.assertEqual(self.minut_blokace(), 5)

    def test_blokace_jen_pro_dane_jmeno_bez_ohledu_na_velka_pismena(self):
        User.objects.create_user("jana", password="Heslo-jany-1")
        for jmeno in ("petr", "PETR", " Petr"): self.prihlas("spatne", jmeno)
        self.assertContains(self.prihlas("Spravne-heslo-1"), "Přihlášení je zablokované")
        self.assertEqual(self.prihlas("Heslo-jany-1", "jana").status_code, 302)

    def test_blokace_je_v_databazi_restart_ji_nezrusi(self):
        from django.core.cache import cache
        for _ in range(3): self.prihlas("spatne")
        cache.clear(); self.client.cookies.clear()  # nová relace prohlížeče a prázdná paměť jako po restartu
        self.assertContains(self.prihlas("Spravne-heslo-1"), "Přihlášení je zablokované")
