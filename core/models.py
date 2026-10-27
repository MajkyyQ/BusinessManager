import re
from datetime import date
from django.db import models
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

class Zakaznik(models.Model):
    class Meta: verbose_name = "zákazník"; verbose_name_plural = "Zákazníci"; ordering = ["firma", "jmeno"]
    typ_zakaznika = C(20, choices=[("Firma", "Firma"), ("Soukromá osoba", "Soukromá osoba")])
    jmeno = C(150); firma = C(255); adresa = C(); telefon = TEL(); email = models.EmailField(blank=True)
    ico = ICO(); dic = DIC(); aktivni = A(); datum_vytvoreni = DV()
    def __str__(self): return self.firma or self.jmeno or f"Zákazník {self.pk}"
class KontaktniOsoba(models.Model):
    class Meta: verbose_name = "kontaktní osoba"; verbose_name_plural = "Kontaktní osoby"
    jmeno = C(150); telefon = TEL(); email = models.EmailField(blank=True); poznamka = T(); aktivni = A()
    def __str__(self): return self.jmeno or f"Kontaktní osoba {self.pk}"
class ZakaznikKontakt(models.Model):
    class Meta: verbose_name = "kontakt zákazníka"; verbose_name_plural = "Kontakty zákazníků"
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
    class Meta: verbose_name = "kontakt na zakázce"; verbose_name_plural = "Kontakty na zakázkách"
    zakazka = models.ForeignKey(Zakazka, on_delete=models.CASCADE); kontakt = models.ForeignKey(KontaktniOsoba, on_delete=models.CASCADE)
    role = C(30, choices=[(x, x) for x in ("Přinesl zařízení", "Vyzvedl zařízení", "Kontakt", "Jiné")])
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
    class Meta: verbose_name = "platba"; verbose_name_plural = "Platby"
    faktura = FK(Faktura); zakazka = FK(Zakazka)
    stav = C(30, choices=[(x, x) for x in ("Čeká na zaplacení", "Zaplaceno")])
    zpusob = C(30, choices=[(x, x) for x in ("Hotově", "Bankovní převod", "Jiný")])
    castka = DEC(); datum_zaplaceni = models.DateTimeField(null=True, blank=True); poznamka = T()
    def __str__(self): return f"Platba {self.pk} – {self.castka} ({self.stav})"
class KalendarUdalost(models.Model):
    class Meta: verbose_name = "událost kalendáře"; verbose_name_plural = "Kalendář"; ordering = ["-datum"]
    nazev = models.CharField(max_length=200); popis = T(); datum = models.DateTimeField(default=timezone.now)
    typ = C(30, choices=[(x, x) for x in ("Přijetí zakázky", "Vydání zařízení", "Fakturováno", "Zaplaceno", "Ruční událost")], default="Ruční událost")
    automaticka = models.BooleanField(default=False, editable=False)
    zakazka = FK(Zakazka); faktura = FK(Faktura); platba = FK(Platba); vytvoril = FK(User)
    zamestnanci = models.ManyToManyField(Zamestnanec, blank=True)
    def __str__(self): return self.nazev
class HistorieZmen(models.Model):
    class Meta: verbose_name = "změna"; verbose_name_plural = "Historie změn"; ordering = ["-datum"]
    uzivatel = FK(User); datum = models.DateTimeField(auto_now_add=True); typ_objektu = C(50); id_objektu = models.IntegerField(null=True)
    akce = C(30); pole = C(100); puvodni_hodnota = T(); nova_hodnota = T(); popis = T()
    def __str__(self): return f"{self.datum:%d.%m.%Y %H:%M} {self.akce} {self.typ_objektu}#{self.id_objektu}"
class NastaveniFirmy(models.Model):
    class Meta: verbose_name = "nastavení firmy"; verbose_name_plural = "Nastavení firmy"
    nazev_firmy = C(255); adresa = C(); ico = ICO(); dic = DIC(); telefon = TEL(); email = models.EmailField(blank=True)
    web = C(200); cislo_uctu = C(50, verbose_name="číslo účtu")
    logo = models.ImageField(upload_to="logo/", blank=True); mena = C(3, default="CZK", choices=[("CZK", "CZK"), ("EUR", "EUR")]); vychozi_dph = DPH(); datum_upravy = models.DateTimeField(auto_now=True)
    def __str__(self): return self.nazev_firmy or "Nastavení"
class SazbaDPH(models.Model):
    class Meta: verbose_name = "sazba DPH"; verbose_name_plural = "Sazby DPH"
    sazba = models.DecimalField(max_digits=5, decimal_places=2); aktivni = A()
    def __str__(self): return f"{self.sazba} %"

# Automatické události kalendáře
@receiver(post_save, sender=Zakazka)
def _ev_z(sender, instance, created, **k):
    if created: KalendarUdalost.objects.create(nazev=f"Přijetí {instance}", datum=instance.datum_prijeti or timezone.now(), typ="Přijetí zakázky", automaticka=True, zakazka=instance)
@receiver(post_save, sender=Faktura)
def _ev_f(sender, instance, created, **k):
    if created: KalendarUdalost.objects.create(nazev=f"Vystavena {instance}", typ="Fakturováno", automaticka=True, faktura=instance)
@receiver(post_save, sender=Platba)
def _ev_p(sender, instance, created, **k):
    if instance.stav == "Zaplaceno" and not instance.kalendarudalost_set.exists():
        KalendarUdalost.objects.create(nazev=f"Zaplaceno {instance.castka or ''}", datum=instance.datum_zaplaceni or timezone.now(), typ="Zaplaceno", automaticka=True, platba=instance, faktura=instance.faktura, zakazka=instance.zakazka)

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
