import re
from datetime import date
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
M2 = dict(max_digits=12, decimal_places=2, null=True, blank=True)
def C(n=200, **k): return models.CharField(max_length=n, blank=True, **k)
def T(): return models.TextField(blank=True)
def A(): return models.BooleanField("aktivní", default=True)
def DV(): return models.DateTimeField("datum vytvoření", auto_now_add=True)
def FK(m, **k): return models.ForeignKey(m, on_delete=models.PROTECT, null=True, blank=True, **k)
def DEC(): return models.DecimalField(**M2)
def DPH(): return models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

# Kontroly formátu (SQLite délku textu nehlídá, PostgreSQL ano; formát hlídají tyto validátory ve formulářích)
def validuj_ico(v):
    if not v: return
    if not (len(v) == 8 and v.isdigit()): raise ValidationError("IČO musí mít přesně 8 číslic.")
    z = sum(int(v[i]) * (8 - i) for i in range(7)) % 11
    if (11 - z) % 10 != int(v[7]): raise ValidationError("IČO nemá platný kontrolní součet.")
validuj_dic = RegexValidator(r"^[A-Z]{2}[0-9A-Z]{2,12}$", "DIČ zadejte jako kód země a číslo bez mezer, např. CZ12345678.")
validuj_telefon = RegexValidator(r"^\+?[0-9 ]{6,19}$", "Telefon smí obsahovat jen číslice, mezery a úvodní +.")
def ICO(): return C(8, validators=[validuj_ico], verbose_name="IČO")
def DIC(): return C(14, validators=[validuj_dic], verbose_name="DIČ")
def TEL(): return C(20, validators=[validuj_telefon])
def VYCET(pole, hodnoty, nazev, prazdne=True):
    """CHECK omezení pro výčtový sloupec (Silberschatz, kap. 4.4.4): hodnota musí být jedna z povolených, případně prázdná."""
    q = Q(**{f"{pole}__in": list(hodnoty)})
    if prazdne: q |= Q(**{pole: ""})
    return models.CheckConstraint(condition=q, name=nazev)

class Zakaznik(models.Model):
    TYPY = ("Firma", "Soukromá osoba")
    class Meta:
        verbose_name = "zákazník"; verbose_name_plural = "Zákazníci"; ordering = ["firma", "jmeno"]
        constraints = [VYCET("typ_zakaznika", ("Firma", "Soukromá osoba"), "zakaznik_typ_platny"),
                       models.CheckConstraint(condition=~Q(jmeno="") | ~Q(firma=""), name="zakaznik_jmeno_nebo_firma",
                                              violation_error_message="Vyplňte jméno nebo firmu.")]
    typ_zakaznika = C(20, choices=[(x, x) for x in TYPY])
    jmeno = C(150); firma = C(255); adresa = C(); telefon = TEL(); email = models.EmailField(blank=True)
    ico = ICO(); dic = DIC(); aktivni = A(); datum_vytvoreni = DV()
    def __str__(self): return self.firma or self.jmeno or f"Zákazník {self.pk}"
class KontaktniOsoba(models.Model):
    class Meta: verbose_name = "kontaktní osoba"; verbose_name_plural = "Kontaktní osoby"
    jmeno = C(150); telefon = TEL(); email = models.EmailField(blank=True); poznamka = T(); aktivni = A()
    def __str__(self): return self.jmeno or f"Kontaktní osoba {self.pk}"
class ZakaznikKontakt(models.Model):
    class Meta:
        verbose_name = "kontakt zákazníka"; verbose_name_plural = "Kontakty zákazníků"
        constraints = [models.UniqueConstraint(fields=["zakaznik", "kontakt"], name="zakaznik_kontakt_unikatni",
                                               violation_error_message="Tato kontaktní osoba už je u zákazníka uvedena.")]
    zakaznik = models.ForeignKey(Zakaznik, on_delete=models.CASCADE)
    kontakt = models.ForeignKey(KontaktniOsoba, on_delete=models.CASCADE); poznamka = C()
    def __str__(self): return f"{self.zakaznik} – {self.kontakt}"
class Zarizeni(models.Model):
    class Meta: verbose_name = "zařízení"; verbose_name_plural = "Zařízení"
    zakaznik = models.ForeignKey(Zakaznik, on_delete=models.PROTECT)
    vyrobce = C(100); typ = C(100); seriove_cislo = C(100, db_index=True); popis = T(); aktivni = A(); datum_vytvoreni = DV()
    def __str__(self): return f"{self.vyrobce} {self.typ} {self.seriove_cislo}".strip()
class StavZakazky(models.Model):
    class Meta: verbose_name = "stav zakázky"; verbose_name_plural = "Stavy zakázek"; ordering = ["poradi"]
    nazev = models.CharField(max_length=100); popis = T(); aktivni = A(); poradi = models.IntegerField(default=0); datum_vytvoreni = DV()
    def __str__(self): return self.nazev
class Zamestnanec(models.Model):
    class Meta: verbose_name = "zaměstnanec"; verbose_name_plural = "Zaměstnanci"
    jmeno = C(100); prijmeni = C(100); telefon = TEL(); email = models.EmailField(blank=True); pracovni_pozice = C(100); aktivni = A()
    uzivatel = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="uživatelský účet")
    role = models.ManyToManyField("Role", blank=True)
    def __str__(self): return f"{self.jmeno} {self.prijmeni}".strip()
class Opravneni(models.Model):
    class Meta: verbose_name = "oprávnění"; verbose_name_plural = "Oprávnění"
    kod = models.CharField(max_length=100, unique=True); nazev = C(); popis = T()
    def __str__(self): return self.kod
class Role(models.Model):
    class Meta: verbose_name = "role"; verbose_name_plural = "Role"
    nazev = models.CharField(max_length=100); popis = T(); je_administrator = models.BooleanField(default=False); aktivni = A()
    opravneni = models.ManyToManyField(Opravneni, blank=True)
    def __str__(self): return self.nazev
class Zakazka(models.Model):
    class Meta: verbose_name = "zakázka"; verbose_name_plural = "Zakázky"; ordering = ["-datum_vytvoreni"]
    cislo_zakazky = models.CharField(max_length=50, unique=True, blank=True, help_text="Prázdné = vygeneruje se automaticky")
    zakaznik = models.ForeignKey(Zakaznik, on_delete=models.PROTECT); stav = FK(StavZakazky)
    datum_prijeti = models.DateTimeField(null=True, blank=True); datum_vydani = models.DateTimeField(null=True, blank=True)
    identifikacni_cislo = C(50, db_index=True); sekundarni_cislo = C(50, db_index=True); popis_zavady = T(); poznamka = T()
    zarizeni = models.ManyToManyField(Zarizeni, blank=True); zamestnanci = models.ManyToManyField(Zamestnanec, blank=True)
    datum_vytvoreni = DV(); datum_upravy = models.DateTimeField(auto_now=True)
    def save(self, *a, **k):
        if not self.cislo_zakazky:
            y = timezone.now().year; n = Zakazka.objects.filter(cislo_zakazky__startswith=f"{y}-").count() + 1
            while Zakazka.objects.filter(cislo_zakazky=f"{y}-{n:03d}").exists(): n += 1
            self.cislo_zakazky = f"{y}-{n:03d}"
        super().save(*a, **k)
    def __str__(self): return f"Zakázka {self.cislo_zakazky}"
class ZakazkaKontakt(models.Model):
    ROLE = ("Přinesl zařízení", "Vyzvedl zařízení", "Kontakt", "Jiné")
    class Meta:
        verbose_name = "kontakt na zakázce"; verbose_name_plural = "Kontakty na zakázkách"
        constraints = [models.UniqueConstraint(fields=["zakazka", "kontakt", "role"], name="zakazka_kontakt_unikatni",
                                               violation_error_message="Tato kontaktní osoba už má na zakázce stejnou roli."),
                       VYCET("role", ("Přinesl zařízení", "Vyzvedl zařízení", "Kontakt", "Jiné"), "zakazka_kontakt_role_platna")]
    zakazka = models.ForeignKey(Zakazka, on_delete=models.CASCADE); kontakt = models.ForeignKey(KontaktniOsoba, on_delete=models.CASCADE)
    role = C(30, choices=[(x, x) for x in ROLE])
    def __str__(self): return f"{self.zakazka} – {self.kontakt} ({self.role})"
class TypUkonu(models.Model):
    class Meta: verbose_name = "typ úkonu"; verbose_name_plural = "Typy úkonů"
    nazev = models.CharField(max_length=150); popis = T(); aktivni = A(); datum_vytvoreni = DV()
    def __str__(self): return self.nazev
class ProvedenyUkon(models.Model):
    class Meta: verbose_name = "provedený úkon"; verbose_name_plural = "Provedené úkony"
    zakazka = models.ForeignKey(Zakazka, on_delete=models.CASCADE); typ_ukonu = models.ForeignKey(TypUkonu, on_delete=models.PROTECT)
    cena = DEC(); sazba_dph = DPH(); poznamka = T(); zamestnanci = models.ManyToManyField(Zamestnanec, blank=True); datum_vytvoreni = DV()
    def __str__(self): return f"{self.typ_ukonu} ({self.zakazka})"
class Material(models.Model):
    class Meta: verbose_name = "materiál"; verbose_name_plural = "Materiály"
    nazev = models.CharField(max_length=200); jednotka = C(20, default="ks"); posledni_cena = DEC(); aktivni = A(); datum_vytvoreni = DV()
    def __str__(self): return self.nazev
class PouzityMaterial(models.Model):
    class Meta: verbose_name = "použitý materiál"; verbose_name_plural = "Použité materiály"
    zakazka = models.ForeignKey(Zakazka, on_delete=models.CASCADE); material = models.ForeignKey(Material, on_delete=models.PROTECT)
    mnozstvi = models.DecimalField(max_digits=12, decimal_places=3, default=1); jednotkova_cena = DEC(); sazba_dph = DPH(); poznamka = T()
    datum_pridani = models.DateTimeField(auto_now_add=True)
    def save(self, *a, **k):  # cena se při použití zkopíruje -> historie zakázky se nemění
        if self.jednotkova_cena is None: self.jednotkova_cena = self.material.posledni_cena
        super().save(*a, **k)
    def __str__(self): return f"{self.material} × {self.mnozstvi}"
class Fotografie(models.Model):
    class Meta: verbose_name = "fotografie"; verbose_name_plural = "Fotografie"
    zakazka = models.ForeignKey(Zakazka, on_delete=models.CASCADE); soubor = models.ImageField(upload_to="fotky/%Y/%m/", max_length=255)
    popis = T(); nahral = FK(User); datum_nahrani = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"Foto {self.pk} ({self.zakazka})"
class Priloha(models.Model):
    class Meta: verbose_name = "příloha"; verbose_name_plural = "Přílohy"
    nazev = models.CharField(max_length=200); soubor = models.FileField(upload_to="prilohy/%Y/%m/", max_length=255); typ_souboru = C(10)
    nahral = FK(User); datum_nahrani = models.DateTimeField(auto_now_add=True); poznamka = T()
    zakazky = models.ManyToManyField(Zakazka, blank=True)
    def save(self, *a, **k):
        if not self.typ_souboru and self.soubor: self.typ_souboru = self.soubor.name.rsplit(".", 1)[-1].upper()[:10]
        super().save(*a, **k)
    def __str__(self): return self.nazev

class Dokument(models.Model):
    class Meta: abstract = True; ordering = ["-datum_vystaveni", "-pk"]
    zakaznik = models.ForeignKey(Zakaznik, on_delete=models.PROTECT)
    identifikacni_cislo = C(50, db_index=True); sekundarni_cislo = C(50, db_index=True)
    zakaznik_jmeno = C(150); zakaznik_firma = C(255); zakaznik_adresa = C(); zakaznik_ico = C(8); zakaznik_dic = C(14)  # snapshot (stejné délky jako Zakaznik)
    cena_bez_dph = DEC(); dph = DEC(); cena_s_dph = DEC(); poznamka = T()
    zakazky = models.ManyToManyField(Zakazka, blank=True)
    def save(self, *a, **k):
        if not self.pk and not (self.zakaznik_jmeno or self.zakaznik_firma):
            z = self.zakaznik; self.zakaznik_jmeno, self.zakaznik_firma, self.zakaznik_adresa, self.zakaznik_ico, self.zakaznik_dic = z.jmeno, z.firma, z.adresa, z.ico, z.dic
        super().save(*a, **k)
    def prepocitej(self):
        p = self.polozky.all(); b = sum((x.cena_bez_dph or 0) for x in p); s = sum((x.cena_s_dph or 0) for x in p)
        type(self).objects.filter(pk=self.pk).update(cena_bez_dph=b, cena_s_dph=s, dph=s - b)
class Polozka(models.Model):
    class Meta: abstract = True
    popis = models.TextField(); mnozstvi = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    jednotka = C(20, default="ks"); jednotkova_cena = DEC(); sazba_dph = DPH(); cena_bez_dph = DEC(); cena_s_dph = DEC()
    def save(self, *a, **k):
        if self.jednotkova_cena is not None:
            self.cena_bez_dph = round(self.mnozstvi * self.jednotkova_cena, 2)
            self.cena_s_dph = round(self.cena_bez_dph * (1 + (self.sazba_dph or 0) / 100), 2)
        super().save(*a, **k); self.dokument.prepocitej()
    def __str__(self): return self.popis
class Nabidka(Dokument):
    class Meta(Dokument.Meta): verbose_name = "nabídka"; verbose_name_plural = "Nabídky"
    cislo_nabidky = models.CharField(max_length=50, unique=True, blank=True, help_text="Prázdné = vygeneruje se automaticky"); datum_vystaveni = models.DateTimeField(default=timezone.now); vypracoval = FK(User)
    def save(self, *a, **k):
        if not self.cislo_nabidky:
            y = timezone.now().year; n = Nabidka.objects.filter(cislo_nabidky__startswith=f"NAB-{y}-").count() + 1
            while Nabidka.objects.filter(cislo_nabidky=f"NAB-{y}-{n:03d}").exists(): n += 1
            self.cislo_nabidky = f"NAB-{y}-{n:03d}"
        super().save(*a, **k)
    @staticmethod
    def cislo_ze_zakazky(z):
        """Nabídka má stejné číslo jako zakázka (2026-048); další nabídka ke stejné zakázce dostane -2, -3 …"""
        c = z.cislo_zakazky; n = 1
        while Nabidka.objects.filter(cislo_nabidky=c if n == 1 else f"{z.cislo_zakazky}-{n}").exists(): n += 1
        return c if n == 1 else f"{c}-{n}"
    def __str__(self): return f"Nabídka {self.cislo_nabidky}"
class PolozkaNabidky(Polozka):
    class Meta: verbose_name = "položka nabídky"; verbose_name_plural = "Položky nabídek"
    nabidka = models.ForeignKey(Nabidka, on_delete=models.CASCADE, related_name="polozky"); zakazka = FK(Zakazka)
    @property
    def dokument(self): return self.nabidka
class Objednavka(models.Model):
    class Meta: verbose_name = "objednávka"; verbose_name_plural = "Objednávky"
    cislo_objednavky = models.CharField(max_length=50); zakaznik = models.ForeignKey(Zakaznik, on_delete=models.PROTECT)
    datum_objednavky = models.DateField(null=True, blank=True); priloha = FK(Priloha); poznamka = T()
    zakazky = models.ManyToManyField(Zakazka, blank=True); datum_vytvoreni = DV()
    def __str__(self): return f"Objednávka {self.cislo_objednavky}"
class Faktura(Dokument):
    class Meta(Dokument.Meta): verbose_name = "faktura"; verbose_name_plural = "Faktury"
    cislo_faktury = models.CharField(max_length=50, unique=True, blank=True, help_text="Prázdné = vygeneruje se automaticky ve tvaru 001-den-měsíc/rok")
    datum_vystaveni = models.DateField(default=timezone.localdate)
    datum_splatnosti = models.DateField(null=True, blank=True); datum_zdanitelneho_plneni = models.DateField(null=True, blank=True); vystavil = FK(User)
    @staticmethod
    def poradi_z_cisla(c):
        m = re.match(r"^(\d+)-\d{1,2}-\d{1,2}/(\d{4})$", c or ""); return (int(m.group(1)), int(m.group(2))) if m else (None, None)
    def save(self, *a, **k):
        if not self.cislo_faktury:  # pořadí se počítá v rámci roku vystavení: 001-27-10/2026
            d = self.datum_vystaveni or timezone.localdate()
            if isinstance(d, str): d = date.fromisoformat(d)
            n = max([p for p, r in map(Faktura.poradi_z_cisla, Faktura.objects.values_list("cislo_faktury", flat=True)) if r == d.year] or [0]) + 1
            self.cislo_faktury = f"{n:03d}-{d.day:02d}-{d.month:02d}/{d.year}"
        super().save(*a, **k)
    def __str__(self): return f"Faktura {self.cislo_faktury}"
class PolozkaFaktury(Polozka):
    class Meta: verbose_name = "položka faktury"; verbose_name_plural = "Položky faktur"
    faktura = models.ForeignKey(Faktura, on_delete=models.CASCADE, related_name="polozky"); zakazka = FK(Zakazka)
    @property
    def dokument(self): return self.faktura
class Platba(models.Model):
    STAVY = ("Čeká na zaplacení", "Zaplaceno"); ZPUSOBY = ("Hotově", "Bankovní převod", "Jiný")
    class Meta:
        verbose_name = "platba"; verbose_name_plural = "Platby"
        constraints = [VYCET("stav", ("Čeká na zaplacení", "Zaplaceno"), "platba_stav_platny"),
                       VYCET("zpusob", ("Hotově", "Bankovní převod", "Jiný"), "platba_zpusob_platny")]
    faktura = FK(Faktura); zakazka = FK(Zakazka)
    stav = C(30, choices=[(x, x) for x in STAVY])
    zpusob = C(30, choices=[(x, x) for x in ZPUSOBY])
    castka = DEC(); datum_zaplaceni = models.DateTimeField(null=True, blank=True); poznamka = T()
    def __str__(self): return f"Platba {self.pk} – {self.castka} ({self.stav})"
class Dodavatel(models.Model):
    class Meta: verbose_name = "dodavatel"; verbose_name_plural = "Dodavatelé"; ordering = ["nazev"]
    nazev = models.CharField("název", max_length=255); ico = ICO(); dic = DIC(); adresa = C(); telefon = TEL(); email = models.EmailField(blank=True)
    cislo_uctu = C(50, verbose_name="číslo účtu"); poznamka = T(); aktivni = A(); datum_vytvoreni = DV()
    def __str__(self): return self.nazev
class PrijataFaktura(models.Model):
    """Faktura, kterou firmě poslal dodavatel (náklad). Částky a údaje se přebírají ručně nebo ze souboru ISDOC."""
    STAVY = ("Nezaplaceno", "Zaplaceno")
    class Meta:
        verbose_name = "přijatá faktura"; verbose_name_plural = "Přijaté faktury"; ordering = ["-datum_doruceni", "-pk"]
        constraints = [models.UniqueConstraint(fields=["dodavatel", "cislo_faktury"], name="prijata_faktura_unikatni"),
                       VYCET("stav", ("Nezaplaceno", "Zaplaceno"), "prijata_faktura_stav_platny", prazdne=False),
                       models.CheckConstraint(condition=Q(stav="Zaplaceno") | Q(datum_zaplaceni__isnull=True), name="prijata_faktura_datum_jen_u_zaplacene")]
    dodavatel = models.ForeignKey(Dodavatel, on_delete=models.PROTECT)
    cislo_faktury = models.CharField("číslo faktury dodavatele", max_length=50); variabilni_symbol = C(20, verbose_name="variabilní symbol")
    datum_vystaveni = models.DateField("datum vystavení", null=True, blank=True); datum_doruceni = models.DateField("datum doručení", default=timezone.localdate)
    datum_zdanitelneho_plneni = models.DateField("DUZP", null=True, blank=True); datum_splatnosti = models.DateField("datum splatnosti", null=True, blank=True)
    cena_bez_dph = models.DecimalField("částka bez DPH", **M2); dph = models.DecimalField("DPH", **M2); cena_s_dph = models.DecimalField("částka k úhradě", **M2)
    mena = C(3, default="CZK", verbose_name="měna"); cislo_uctu = C(50, verbose_name="účet pro platbu")
    stav = models.CharField(max_length=20, choices=[(x, x) for x in STAVY], default="Nezaplaceno"); datum_zaplaceni = models.DateField("datum zaplacení", null=True, blank=True)
    soubor = models.FileField("soubor faktury", upload_to="prijate_faktury/%Y/", max_length=255, blank=True)
    zakazka = FK(Zakazka, verbose_name="zakázka"); poznamka = T(); vytvoril = FK(User); datum_vytvoreni = DV()
    def save(self, *a, **k):
        if self.stav == "Zaplaceno" and not self.datum_zaplaceni: self.datum_zaplaceni = timezone.localdate()
        if self.stav != "Zaplaceno": self.datum_zaplaceni = None
        super().save(*a, **k)
    @property
    def po_splatnosti(self): return self.stav != "Zaplaceno" and self.datum_splatnosti is not None and self.datum_splatnosti < timezone.localdate()
    def __str__(self): return f"Přijatá faktura {self.cislo_faktury} ({self.dodavatel})"
class KalendarUdalost(models.Model):
    TYPY = ("Přijetí zakázky", "Vydání zařízení", "Fakturováno", "Zaplaceno", "Přijatá faktura", "Splatnost faktury", "Zaplaceno dodavateli", "Ruční událost")
    class Meta:
        verbose_name = "událost kalendáře"; verbose_name_plural = "Kalendář"; ordering = ["-datum"]
        constraints = [VYCET("typ", ("Přijetí zakázky", "Vydání zařízení", "Fakturováno", "Zaplaceno", "Přijatá faktura", "Splatnost faktury",
                                     "Zaplaceno dodavateli", "Ruční událost"), "kalendar_typ_platny", prazdne=False)]
    nazev = models.CharField(max_length=200); popis = T(); datum = models.DateTimeField(default=timezone.now)
    typ = C(30, choices=[(x, x) for x in TYPY], default="Ruční událost")
    automaticka = models.BooleanField(default=False, editable=False)
    zakazka = FK(Zakazka); faktura = FK(Faktura); platba = FK(Platba); vytvoril = FK(User)
    prijata_faktura = models.ForeignKey(PrijataFaktura, on_delete=models.CASCADE, null=True, blank=True, verbose_name="přijatá faktura")
    zamestnanci = models.ManyToManyField(Zamestnanec, blank=True)
    def __str__(self): return self.nazev
class HistorieZmen(models.Model):
    class Meta: verbose_name = "změna"; verbose_name_plural = "Historie změn"; ordering = ["-datum"]
    uzivatel = FK(User); datum = models.DateTimeField(auto_now_add=True); typ_objektu = C(50); id_objektu = models.BigIntegerField(null=True)  # stejný typ jako primární klíče (BigAutoField)
    akce = C(30); pole = C(100); puvodni_hodnota = T(); nova_hodnota = T(); popis = T()
    def __str__(self): return f"{self.datum:%d.%m.%Y %H:%M} {self.akce} {self.typ_objektu}#{self.id_objektu}"
class NastaveniFirmy(models.Model):
    class Meta:
        verbose_name = "nastavení firmy"; verbose_name_plural = "Nastavení firmy"
        constraints = [VYCET("mena", ("CZK", "EUR"), "nastaveni_mena_platna"),
                       models.CheckConstraint(condition=Q(vychozi_dph__isnull=True) | Q(vychozi_dph__gte=0, vychozi_dph__lte=100), name="nastaveni_dph_rozsah")]
    nazev_firmy = C(255); adresa = C(); ico = ICO(); dic = DIC(); telefon = TEL(); email = models.EmailField(blank=True)
    web = C(200); cislo_uctu = C(50, verbose_name="číslo účtu")
    logo = models.ImageField(upload_to="logo/", blank=True); mena = C(3, default="CZK", choices=[("CZK", "CZK"), ("EUR", "EUR")]); vychozi_dph = DPH(); datum_upravy = models.DateTimeField(auto_now=True)
    def __str__(self): return self.nazev_firmy or "Nastavení"
class SazbaDPH(models.Model):
    class Meta:
        verbose_name = "sazba DPH"; verbose_name_plural = "Sazby DPH"
        constraints = [models.CheckConstraint(condition=Q(sazba__gte=0, sazba__lte=100), name="sazba_dph_rozsah",
                                              violation_error_message="Sazba DPH musí být mezi 0 a 100 %.")]
    sazba = models.DecimalField(max_digits=5, decimal_places=2); aktivni = A()
    def __str__(self): return f"{self.sazba} %"

# Automatické události kalendáře
def _ve_dne(d, hodina=8):
    from datetime import datetime, time
    return timezone.make_aware(datetime.combine(d, time(hodina)))
# Událost je odvozená kopie údaje z dokladu, proto se při každém uložení dokladu srovná s ním (Silberschatz, kap. 7.9.3).
def _srovnej_udalost(typ, nazev, datum, created, **odkaz):
    if created: KalendarUdalost.objects.create(nazev=nazev[:200], datum=datum, typ=typ, automaticka=True, **odkaz)
    else: KalendarUdalost.objects.filter(typ=typ, automaticka=True, **odkaz).update(nazev=nazev[:200], datum=datum)
@receiver(post_save, sender=Zakazka)
def _ev_z(sender, instance, created, **k):
    if created or instance.datum_prijeti:
        _srovnej_udalost("Přijetí zakázky", f"Přijetí {instance}", instance.datum_prijeti or timezone.now(), created, zakazka=instance)
@receiver(post_save, sender=Faktura)
def _ev_f(sender, instance, created, **k):
    d = instance.datum_vystaveni
    if isinstance(d, str): d = date.fromisoformat(d)
    _srovnej_udalost("Fakturováno", f"Vystavena {instance}", _ve_dne(d) if d else timezone.now(), created, faktura=instance)
@receiver(post_save, sender=Platba)
def _ev_p(sender, instance, created, **k):
    if instance.stav == "Zaplaceno" and not instance.kalendarudalost_set.exists():
        KalendarUdalost.objects.create(nazev=f"Zaplaceno {instance.castka or ''}", datum=instance.datum_zaplaceni or timezone.now(), typ="Zaplaceno", automaticka=True, platba=instance, faktura=instance.faktura, zakazka=instance.zakazka)

@receiver(post_save, sender=PrijataFaktura)
def _ev_pf(sender, instance, **k):
    """Kalendář přijaté faktury: doručení, splatnost (se stavem zaplacení) a zaplacení. Události se při každé změně faktury aktualizují."""
    f = instance; kc = f" {f.cena_s_dph:,.2f} {f.mena}".replace(",", " ").replace(".", ",") if f.cena_s_dph is not None else ""
    def nastav(typ, d, nazev):
        qs = KalendarUdalost.objects.filter(prijata_faktura=f, typ=typ, automaticka=True)
        if not d: qs.delete(); return
        u = qs.first() or KalendarUdalost(prijata_faktura=f, typ=typ, automaticka=True, vytvoril=f.vytvoril)
        u.nazev, u.datum, u.zakazka = nazev[:200], _ve_dne(d), f.zakazka; u.popis = f"Faktura {f.cislo_faktury} od {f.dodavatel}, k úhradě{kc or ' –'}"; u.save()
    zapl = f.stav == "Zaplaceno"
    nastav("Přijatá faktura", f.datum_doruceni, f"Přijata faktura {f.cislo_faktury} – {f.dodavatel}")
    nastav("Splatnost faktury", f.datum_splatnosti, f"Splatnost {f.cislo_faktury} – {f.dodavatel}: " + ("zaplaceno" if zapl else "NEZAPLACENO"))
    nastav("Zaplaceno dodavateli", f.datum_zaplaceni if zapl else None, f"Zaplaceno {f.cislo_faktury} – {f.dodavatel}{kc}")

# ---------------- Šablony výstupních dokumentů ----------------
class SablonaDokumentu(models.Model):
    """Vzhled výsledného dokumentu. Obsahuje jen soubor šablony a mapování polí, žádná data."""
    class Meta: verbose_name = "šablona dokumentu"; verbose_name_plural = "Šablony dokumentů"; ordering = ["typ_dokumentu", "-vychozi", "nazev"]
    nazev = models.CharField("název", max_length=150)
    typ_dokumentu = models.CharField("typ dokumentu", max_length=30, db_index=True)   # klíč z core.sablony.typy.REGISTR
    format = models.CharField("formát", max_length=20, default="excel")              # klíč z core.sablony.renderery.REGISTR
    soubor = models.FileField("soubor šablony", upload_to="sablony/", blank=True)
    vestavena = models.CharField("vestavěná šablona", max_length=100, blank=True, editable=False)  # název souboru v aplikaci (nelze smazat)
    mapovani = models.JSONField("mapování polí", default=dict, blank=True)
    nahled = models.ImageField("miniatura", upload_to="sablony/nahledy/", blank=True, editable=False)
    popis = T(); vychozi = models.BooleanField("výchozí", default=False); aktivni = A()
    verze = models.PositiveIntegerField(default=1, editable=False)
    datum_vytvoreni = DV(); datum_upravy = models.DateTimeField(auto_now=True)
    def save(self, *a, **k):
        super().save(*a, **k)
        if self.vychozi:  # v každém typu je výchozí jen jedna
            SablonaDokumentu.objects.filter(typ_dokumentu=self.typ_dokumentu, vychozi=True).exclude(pk=self.pk).update(vychozi=False)
    def __str__(self): return self.nazev
