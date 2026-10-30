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
