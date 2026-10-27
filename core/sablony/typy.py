"""Typy dokumentů. Každý typ zná svá pole a umí z objektu v databázi sestavit data.

Data mají vždy stejný tvar: {"pole": {klíč: hodnota}, "polozky": [{klíč: hodnota}, ...]}.
Klíče polí jsou s tečkou (např. "zakaznik.ico"), položky mají klíče "polozka.*".
Nový typ dokumentu = nová třída zaregistrovaná přes @registruj.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.utils import timezone


@dataclass(frozen=True)
class Pole:
    klic: str
    nazev: str
    skupina: str
    druh: str = "text"   # text | cislo | penize | datum | obrazek | dlouhy_text
    synonyma: tuple = ()  # popisky, podle kterých se pole pozná v cizí šabloně


# ---------- společné skupiny polí ----------
FIRMA = [
    Pole("firma.nazev", "Název firmy", "Naše firma", synonyma=("dodavatel", "prodávající", "zhotovitel")),
    Pole("firma.adresa", "Adresa firmy", "Naše firma", "dlouhy_text", ("adresa dodavatele", "sídlo")),
    Pole("firma.ico", "IČO firmy", "Naše firma", synonyma=("ič dodavatele", "ičo dodavatele")),
    Pole("firma.dic", "DIČ firmy", "Naše firma", synonyma=("dič dodavatele",)),
    Pole("firma.telefon", "Telefon firmy", "Naše firma"),
    Pole("firma.email", "E-mail firmy", "Naše firma"),
    Pole("firma.logo", "Logo", "Naše firma", "obrazek", ("logo",)),
]
ZAKAZNIK = [
    Pole("zakaznik.nazev", "Zákazník (firma nebo jméno)", "Zákazník", synonyma=("zákazník", "odběratel", "objednatel", "kupující", "příjemce")),
    Pole("zakaznik.firma", "Firma zákazníka", "Zákazník", synonyma=("firma",)),
    Pole("zakaznik.jmeno", "Jméno zákazníka", "Zákazník", synonyma=("jméno", "jméno a příjmení", "kontaktní osoba")),
    Pole("zakaznik.adresa", "Adresa zákazníka", "Zákazník", "dlouhy_text", ("adresa", "sídlo odběratele", "bydliště")),
    Pole("zakaznik.ico", "IČO zákazníka", "Zákazník", synonyma=("ičo", "ič")),
    Pole("zakaznik.dic", "DIČ zákazníka", "Zákazník", synonyma=("dič",)),
    Pole("zakaznik.telefon", "Telefon zákazníka", "Zákazník", synonyma=("telefon", "tel", "tel.", "mobil")),
    Pole("zakaznik.email", "E-mail zákazníka", "Zákazník", synonyma=("e-mail", "email")),
]
ZAKAZKA = [
    Pole("zakazka.cislo", "Číslo zakázky", "Zakázka", synonyma=("číslo zakázky", "zakázka č", "zakázka")),
    Pole("zakazka.datum_prijeti", "Datum přijetí", "Zakázka", "datum", ("datum přijetí", "přijato")),
    Pole("zakazka.datum_vydani", "Datum vydání", "Zakázka", "datum", ("datum vydání", "vydáno")),
    Pole("zakazka.stav", "Stav zakázky", "Zakázka", synonyma=("stav",)),
    Pole("zakazka.popis_zavady", "Popis závady", "Zakázka", "dlouhy_text", ("popis závady", "závada", "popis problému")),
    Pole("zakazka.poznamka", "Poznámka k zakázce", "Zakázka", "dlouhy_text", ("poznámka k zakázce",)),
    Pole("zakazka.identifikacni_cislo", "Identifikační číslo", "Zakázka", synonyma=("identifikační číslo",)),
    Pole("zakazka.sekundarni_cislo", "Sekundární číslo", "Zakázka", synonyma=("sekundární číslo",)),
    Pole("zakazka.zamestnanci", "Pracovníci", "Zakázka", synonyma=("technik", "pracovník", "opravu provedl")),
]
ZARIZENI = [
    Pole("zarizeni.vyrobce", "Výrobce", "Zařízení", synonyma=("výrobce", "značka")),
    Pole("zarizeni.typ", "Typ zařízení", "Zařízení", synonyma=("typ", "model", "typ zařízení")),
    Pole("zarizeni.seriove_cislo", "Sériové číslo", "Zařízení", synonyma=("sériové číslo", "výrobní číslo", "s/n", "sn")),
    Pole("zarizeni.popis", "Popis zařízení", "Zařízení", "dlouhy_text", ("popis zařízení", "příslušenství")),
    Pole("zarizeni.vse", "Všechna zařízení (souhrn)", "Zařízení", "dlouhy_text", ("zařízení",)),
]
SOUCTY = [
    Pole("soucty.bez_dph", "Celkem bez DPH", "Finanční údaje", "penize", ("celkem bez dph", "základ", "základ daně", "cena bez dph", "mezisoučet")),
    Pole("soucty.dph", "DPH celkem", "Finanční údaje", "penize", ("dph celkem", "dph", "výše dph")),
    Pole("soucty.s_dph", "Celkem s DPH", "Finanční údaje", "penize", ("celkem k úhradě", "k úhradě", "celkem s dph", "cena s dph", "celkem", "celková cena")),
    Pole("soucty.mena", "Měna", "Finanční údaje", synonyma=("měna",)),
]
POLOZKY = [
    Pole("polozka.poradi", "Pořadí", "Položky", "cislo", ("č.", "poř.", "#", "pořadí")),
    Pole("polozka.popis", "Popis položky", "Položky", synonyma=("popis", "položka", "název", "označení dodávky", "text")),
    Pole("polozka.mnozstvi", "Množství", "Položky", "cislo", ("množství", "množ.", "ks", "počet", "mn.")),
    Pole("polozka.jednotka", "Jednotka", "Položky", synonyma=("jednotka", "mj", "m.j.", "j.")),
    Pole("polozka.jednotkova_cena", "Jednotková cena", "Položky", "penize", ("cena/j", "cena za j.", "jedn. cena", "jednotková cena", "cena za mj", "cena")),
    Pole("polozka.sazba_dph", "Sazba DPH %", "Položky", "cislo", ("dph %", "sazba dph", "sazba", "dph")),
    Pole("polozka.cena_bez_dph", "Cena bez DPH", "Položky", "penize", ("bez dph", "cena bez dph", "základ", "celkem bez dph")),
    Pole("polozka.dph", "DPH (částka)", "Položky", "penize", ("dph kč", "částka dph")),
    Pole("polozka.cena_s_dph", "Cena s DPH", "Položky", "penize", ("s dph", "cena s dph", "celkem s dph", "celkem")),
]


def _d(v):
    """datetime -> lokální datum, ostatní beze změny."""
    if isinstance(v, datetime): return timezone.localtime(v).date() if timezone.is_aware(v) else v.date()
    return v


def _firma():
    from core.models import NastaveniFirmy
    f = NastaveniFirmy.objects.first()
    if not f: return {k.klic: "" for k in FIRMA} | {"soucty.mena": "CZK"}
    return {"firma.nazev": f.nazev_firmy, "firma.adresa": f.adresa, "firma.ico": f.ico, "firma.dic": f.dic,
            "firma.telefon": f.telefon, "firma.email": f.email, "firma.logo": f.logo.path if f.logo else "", "soucty.mena": f.mena or "CZK"}


def _zakaznik(z, snap=None):
    """Údaje zákazníka; u nabídky/faktury mají přednost údaje uložené v dokumentu (snapshot)."""
    s = snap
    jm = s.zakaznik_jmeno if s else z.jmeno; fi = s.zakaznik_firma if s else z.firma
    return {"zakaznik.nazev": fi or jm, "zakaznik.firma": fi, "zakaznik.jmeno": jm,
            "zakaznik.adresa": s.zakaznik_adresa if s else z.adresa, "zakaznik.ico": s.zakaznik_ico if s else z.ico,
            "zakaznik.dic": s.zakaznik_dic if s else z.dic, "zakaznik.telefon": z.telefon, "zakaznik.email": z.email}


def _zakazka(zk):
    if not zk: return {p.klic: "" for p in ZAKAZKA + ZARIZENI}
    zar = list(zk.zarizeni.all()); z0 = zar[0] if zar else None
    return {"zakazka.cislo": zk.cislo_zakazky, "zakazka.datum_prijeti": _d(zk.datum_prijeti), "zakazka.datum_vydani": _d(zk.datum_vydani),
            "zakazka.stav": str(zk.stav or ""), "zakazka.popis_zavady": zk.popis_zavady, "zakazka.poznamka": zk.poznamka,
            "zakazka.identifikacni_cislo": zk.identifikacni_cislo, "zakazka.sekundarni_cislo": zk.sekundarni_cislo,
            "zakazka.zamestnanci": ", ".join(str(e) for e in zk.zamestnanci.all()),
            "zarizeni.vyrobce": z0.vyrobce if z0 else "", "zarizeni.typ": z0.typ if z0 else "",
            "zarizeni.seriove_cislo": z0.seriove_cislo if z0 else "", "zarizeni.popis": z0.popis if z0 else "",
            "zarizeni.vse": "\n".join(f"{x} ({x.popis})" if x.popis else str(x) for x in zar)}


def _polozka(i, popis, mn, jedn, cena, dph, bez=None, s=None):
    mn = Decimal(mn or 0); cena = Decimal(cena or 0); dph = Decimal(dph or 0)
    bez = Decimal(bez) if bez is not None else round(mn * cena, 2)
    s = Decimal(s) if s is not None else round(bez * (1 + dph / 100), 2)
    return {"polozka.poradi": i, "polozka.popis": popis, "polozka.mnozstvi": mn, "polozka.jednotka": jedn, "polozka.jednotkova_cena": cena,
            "polozka.sazba_dph": dph, "polozka.cena_bez_dph": bez, "polozka.dph": s - bez, "polozka.cena_s_dph": s}


def _soucty(pol):
    b = sum((p["polozka.cena_bez_dph"] for p in pol), Decimal(0)); s = sum((p["polozka.cena_s_dph"] for p in pol), Decimal(0))
    return {"soucty.bez_dph": b, "soucty.dph": s - b, "soucty.s_dph": s}


class TypDokumentu:
    kod = ""; nazev = ""; nazev_mn = ""; model = None
    pole_dokumentu = []   # pole specifická pro typ (číslo, data…)
    skupiny = ()          # společné skupiny polí

    @classmethod
    def pole(cls):
        return cls.pole_dokumentu + [p for s in cls.skupiny for p in s] + SOUCTY + POLOZKY

    @classmethod
    def pole_dict(cls): return {p.klic: p for p in cls.pole()}

    @classmethod
    def objekt(cls, pk):
        return cls.model.objects.get(pk=pk)

    @classmethod
    def titulek(cls, obj): return str(obj)

    @classmethod
    def data(cls, obj): raise NotImplementedError

    @classmethod
    def ukazka(cls):
        """Ukázková data pro miniatury šablon a editor (nic se nečte z databáze kromě údajů firmy)."""
        dnes = timezone.localdate()
        pol = [_polozka(1, "Diagnostika a oprava zařízení", 1, "ks", 1500, 21), _polozka(2, "Ložisko 6204-2RS", 2, "ks", 300, 21),
               _polozka(3, "Servisní práce", 1.5, "hod", 650, 21)]
        p = {k.klic: "" for k in cls.pole() if not k.klic.startswith("polozka.")}
        p.update(_firma())
        p.update({"zakaznik.nazev": "ABC s.r.o.", "zakaznik.firma": "ABC s.r.o.", "zakaznik.jmeno": "Jan Novák",
                  "zakaznik.adresa": "Hlavní 123\n400 01 Ústí nad Labem", "zakaznik.ico": "12345678", "zakaznik.dic": "CZ12345678",
                  "zakaznik.telefon": "+420 777 123 456", "zakaznik.email": "jan.novak@example.cz",
                  "zakazka.cislo": f"{dnes.year}-001", "zakazka.datum_prijeti": dnes - timedelta(days=7), "zakazka.datum_vydani": dnes,
                  "zakazka.stav": "Opraveno", "zakazka.popis_zavady": "Zařízení nejde zapnout, při spuštění hlučí.",
                  "zakazka.poznamka": "", "zakazka.identifikacni_cislo": "INV-0042", "zakazka.zamestnanci": "Petr Svoboda",
                  "zarizeni.vyrobce": "Bosch", "zarizeni.typ": "GSR 18V", "zarizeni.seriove_cislo": "SN123456789",
                  "zarizeni.popis": "včetně nabíječky", "zarizeni.vse": "Bosch GSR 18V SN123456789 (včetně nabíječky)",
                  "dokument.cislo": cls.ukazkove_cislo(dnes), "dokument.datum_vystaveni": dnes,
                  "dokument.datum_splatnosti": dnes + timedelta(days=14), "dokument.duzp": dnes, "dokument.vystavil": "Petr Svoboda",
                  "dokument.poznamka": "Děkujeme za Vaši důvěru."})
        p.update(_soucty(pol))
        return {"pole": p, "polozky": pol}

    @classmethod
    def ukazkove_cislo(cls, dnes): return f"{dnes.year}-001"


REGISTR = {}
def registruj(cls):
    REGISTR[cls.kod] = cls; return cls
def typ(kod):
    return REGISTR.get(kod)
def volby():
    return [(k, t.nazev) for k, t in REGISTR.items()]


@registruj
class ZakazkovyList(TypDokumentu):
    kod = "zakazkovy_list"; nazev = "Zakázkový list"; nazev_mn = "Zakázkové listy"
    pole_dokumentu = [Pole("dokument.cislo", "Číslo dokumentu (= číslo zakázky)", "Dokument", synonyma=("zakázkový list č", "číslo listu")),
                      Pole("dokument.datum_vystaveni", "Datum vytištění", "Dokument", "datum", ("datum", "dne", "datum vystavení"))]
    skupiny = (FIRMA, ZAKAZNIK, ZAKAZKA, ZARIZENI)

    @classmethod
    def objekt(cls, pk):
        from core.models import Zakazka
        return Zakazka.objects.select_related("zakaznik", "stav").get(pk=pk)

    @classmethod
    def titulek(cls, z): return f"Zakázkový list {z.cislo_zakazky}"

    @classmethod
    def data(cls, z):
        from core.views import nabidka_polozky
        pol = [_polozka(i, x["popis"], x["mnozstvi"], x["jednotka"], x["cena"], x["dph"], x["bez"], x["s"]) for i, x in enumerate(nabidka_polozky(z), 1)]
        p = {"dokument.cislo": z.cislo_zakazky, "dokument.datum_vystaveni": timezone.localdate()}
        p |= _firma() | _zakaznik(z.zakaznik) | _zakazka(z) | _soucty(pol)
        return {"pole": p, "polozky": pol}


class _Doklad(TypDokumentu):
    """Společný základ pro nabídku a fakturu (model Dokument s položkami)."""
    skupiny = (FIRMA, ZAKAZNIK, ZAKAZKA, ZARIZENI)

    @classmethod
    def data(cls, d):
        pol = [_polozka(i, x.popis, x.mnozstvi, x.jednotka, x.jednotkova_cena, x.sazba_dph, x.cena_bez_dph, x.cena_s_dph)
               for i, x in enumerate(d.polozky.all(), 1)]
        p = cls.pole_dokladu(d) | _firma() | _zakaznik(d.zakaznik, d) | _zakazka(d.zakazky.first()) | _soucty(pol)
        p["dokument.poznamka"] = d.poznamka
        if not pol and d.cena_s_dph is not None:  # dokument bez položek, jen s částkou
            p |= {"soucty.bez_dph": d.cena_bez_dph or 0, "soucty.dph": d.dph or 0, "soucty.s_dph": d.cena_s_dph}
        return {"pole": p, "polozky": pol}


@registruj
class Nabidka(_Doklad):
    kod = "nabidka"; nazev = "Cenová nabídka"; nazev_mn = "Nabídky"
    pole_dokumentu = [Pole("dokument.cislo", "Číslo nabídky", "Dokument", synonyma=("číslo nabídky", "nabídka č", "cenová nabídka č")),
                      Pole("dokument.datum_vystaveni", "Datum vystavení", "Dokument", "datum", ("datum vystavení", "datum", "dne")),
                      Pole("dokument.vystavil", "Vypracoval", "Dokument", synonyma=("vypracoval", "vystavil", "zpracoval")),
                      Pole("dokument.poznamka", "Poznámka", "Dokument", "dlouhy_text", ("poznámka",))]

    @classmethod
    def objekt(cls, pk):
        from core.models import Nabidka as M
        return M.objects.select_related("zakaznik", "vypracoval").get(pk=pk)

    @classmethod
    def pole_dokladu(cls, d):
        u = d.vypracoval
        return {"dokument.cislo": d.cislo_nabidky, "dokument.datum_vystaveni": _d(d.datum_vystaveni),
                "dokument.vystavil": (u.get_full_name() or u.username) if u else ""}

    @classmethod
    def ukazkove_cislo(cls, dnes): return f"NAB-{dnes.year}-001"


@registruj
class Faktura(_Doklad):
    kod = "faktura"; nazev = "Faktura"; nazev_mn = "Faktury"
    pole_dokumentu = [Pole("dokument.cislo", "Číslo faktury", "Dokument", synonyma=("číslo faktury", "faktura č", "faktura - daňový doklad č", "variabilní symbol", "vs")),
                      Pole("dokument.datum_vystaveni", "Datum vystavení", "Dokument", "datum", ("datum vystavení", "vystaveno")),
                      Pole("dokument.datum_splatnosti", "Datum splatnosti", "Dokument", "datum", ("datum splatnosti", "splatnost", "splatno")),
                      Pole("dokument.duzp", "DUZP", "Dokument", "datum", ("duzp", "datum uskutečnění zdanitelného plnění", "datum zdanitelného plnění")),
                      Pole("dokument.vystavil", "Vystavil", "Dokument", synonyma=("vystavil", "fakturu vystavil")),
                      Pole("dokument.poznamka", "Poznámka", "Dokument", "dlouhy_text", ("poznámka",))]

    @classmethod
    def objekt(cls, pk):
        from core.models import Faktura as M
        return M.objects.select_related("zakaznik", "vystavil").get(pk=pk)

    @classmethod
    def pole_dokladu(cls, d):
        u = d.vystavil
        return {"dokument.cislo": d.cislo_faktury, "dokument.datum_vystaveni": d.datum_vystaveni, "dokument.datum_splatnosti": d.datum_splatnosti,
                "dokument.duzp": d.datum_zdanitelneho_plneni, "dokument.vystavil": (u.get_full_name() or u.username) if u else ""}

    @classmethod
    def ukazkove_cislo(cls, dnes): return f"FA-{dnes.year}-001"


# ---------- formátování hodnot pro text (HTML, text v buňce) ----------
def formatuj(v, druh="text", mena=""):
    if v is None or v == "": return ""
    if isinstance(v, datetime): v = _d(v)
    if isinstance(v, date): return f"{v.day}. {v.month}. {v.year}"
    if isinstance(v, (Decimal, int, float)) and not isinstance(v, bool):
        if druh == "penize":
            t = f"{Decimal(v):,.2f}".replace(",", " ").replace(".", ",")
            return f"{t} {'Kč' if mena in ('', 'CZK') else mena}"
        d = Decimal(v).normalize(); t = f"{d:,f}".replace(",", " ").replace(".", ",")
        return t
    return str(v)
