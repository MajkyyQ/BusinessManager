"""Export faktury do formátu ISDOC 6.0.2 (český standard elektronické faktury, XML).

Data se berou ze stejného zdroje jako PDF faktury, tedy z typy.Faktura.data(),
takže ISDOC i tištěná faktura vždy obsahují stejné položky a částky.
Výsledné XML se před odesláním ověří proti oficiálnímu schématu XSD (složka schemata/).
"""
import re
import uuid
from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

from lxml import etree

NS = "http://isdoc.cz/namespace/2013"
VERZE = "6.0.2"
XSD = Path(__file__).parent / "schemata" / "isdoc-invoice-6.0.2.xsd"
SYSTEM = "BusinessManager"
# Pevný jmenný prostor pro UUID faktur: stejná faktura dostane při každém exportu stejné UUID.
UUID_NS = uuid.UUID("6f1c2a0e-5b7d-4c1e-9a3f-2d8e4b6c1a90")
HALER = Decimal("0.01")


class NeplatneISDOC(Exception):
    """Vytvořené XML neodpovídá schématu ISDOC."""


@lru_cache(maxsize=1)
def _schema():
    return etree.XMLSchema(etree.parse(str(XSD)))


# ---------------------------------------------------------------- pomocné funkce
def _castka(v):
    return str(Decimal(v or 0).quantize(HALER, ROUND_HALF_UP))


def _cislo(v):
    """Desetinné číslo bez zbytečných nul (množství, procento sazby)."""
    d = Decimal(v or 0).normalize()
    return format(d, "f")


def _el(rodic, nazev, text=None, **atributy):
    e = etree.SubElement(rodic, f"{{{NS}}}{nazev}", **{k: str(v) for k, v in atributy.items()})
    if text is not None: e.text = str(text)
    return e


def rozdel_adresu(adresa):
    """Adresa zapsaná jedním řádkem -> (ulice, číslo domu, město, PSČ).

    „Hlavní 123, 400 01 Ústí nad Labem“ -> ("Hlavní", "123", "Ústí nad Labem", "40001").
    Co nejde rozpoznat, zůstane v ulici nebo ve městě, aby se žádný údaj neztratil.
    """
    casti = [c.strip() for c in (adresa or "").replace("\n", ",").split(",") if c.strip()]
    if not casti: return "", "", "", ""
    ulice, cp = casti[0], ""
    m = re.match(r"^(.*\S)\s+(\d+[\w/]*)$", ulice)
    if m: ulice, cp = m.group(1), m.group(2)
    mesto, psc = " ".join(casti[1:]), ""
    m = re.match(r"^(\d{3})\s?(\d{2})\s+(.*)$", mesto)
    if m: psc, mesto = m.group(1) + m.group(2), m.group(3)
    elif len(casti) == 1:  # jen jedna část: může to být rovnou „PSČ město“
        m = re.match(r"^(.*?)\s*(\d{3})\s?(\d{2})\s+(.*)$", casti[0])
        if m: ulice, psc, mesto = m.group(1), m.group(2) + m.group(3), m.group(4)
    return ulice, cp, mesto, psc


def rozdel_ucet(ucet):
    """Číslo účtu „123-4567890/0800“ -> ("123-4567890", "0800"); IBAN se vrací zvlášť."""
    u = (ucet or "").replace(" ", "")
    if re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]+$", u): return "", "", u
    cislo, _, banka = u.partition("/")
    return cislo, banka, ""


def _strana(rodic, nazev, ico, jmeno, adresa, dic, kontakt=None, telefon="", email=""):
    p = _el(_el(rodic, nazev), "Party")
    _el(_el(p, "PartyIdentification"), "ID", ico or "")
    _el(_el(p, "PartyName"), "Name", jmeno or "")
    ulice, cp, mesto, psc = rozdel_adresu(adresa)
    a = _el(p, "PostalAddress")
    _el(a, "StreetName", ulice); _el(a, "BuildingNumber", cp); _el(a, "CityName", mesto); _el(a, "PostalZone", psc)
    z = _el(a, "Country"); _el(z, "IdentificationCode", "CZ"); _el(z, "Name", "Česká republika")
    if dic:
        t = _el(p, "PartyTaxScheme"); _el(t, "CompanyID", dic); _el(t, "TaxScheme", "VAT")
    if kontakt or telefon or email:
        k = _el(p, "Contact")
        if kontakt: _el(k, "Name", kontakt)
        if telefon: _el(k, "Telephone", telefon)
        if email: _el(k, "ElectronicMail", email)


# ---------------------------------------------------------------- sestavení dokumentu
def vytvor(data, uuid_klic=None):
    """Data faktury (výstup typy.Faktura.data()) -> strom XML ve formátu ISDOC."""
    p, polozky = data["pole"], data["polozky"]
    platce_dph = bool(p.get("firma.dic"))
    vat = "true" if platce_dph else "false"

    if not polozky:  # faktura bez položek, jen s celkovou částkou
        bez, s = Decimal(p.get("soucty.bez_dph") or 0), Decimal(p.get("soucty.s_dph") or 0)
        sazba = ((s - bez) / bez * 100).quantize(Decimal("1"), ROUND_HALF_UP) if bez else Decimal(0)
        polozky = [{"polozka.poradi": 1, "polozka.popis": p.get("dokument.poznamka") or "Fakturace dle dokladu", "polozka.mnozstvi": 1, "polozka.jednotka": "",
                    "polozka.jednotkova_cena": bez, "polozka.sazba_dph": sazba, "polozka.cena_bez_dph": bez, "polozka.dph": s - bez, "polozka.cena_s_dph": s}]

    root = etree.Element(f"{{{NS}}}Invoice", nsmap={None: NS}, version=VERZE)
    _el(root, "DocumentType", "1")  # 1 = faktura – daňový doklad
    _el(root, "ID", p.get("dokument.cislo") or "")
    _el(root, "UUID", str(uuid.uuid5(UUID_NS, str(uuid_klic or p.get("dokument.cislo") or ""))).upper())
    _el(root, "IssuingSystem", SYSTEM)
    _el(root, "IssueDate", p["dokument.datum_vystaveni"].isoformat())
    if p.get("dokument.duzp"): _el(root, "TaxPointDate", p["dokument.duzp"].isoformat())
    _el(root, "VATApplicable", vat)
    _el(root, "ElectronicPossibilityAgreementReference", "")
    if p.get("dokument.poznamka"): _el(root, "Note", p["dokument.poznamka"])
    _el(root, "LocalCurrencyCode", p.get("soucty.mena") or "CZK")
    _el(root, "CurrRate", "1"); _el(root, "RefCurrRate", "1")

    _strana(root, "AccountingSupplierParty", p.get("firma.ico"), p.get("firma.nazev"), p.get("firma.adresa"), p.get("firma.dic"),
            telefon=p.get("firma.telefon"), email=p.get("firma.email"))
    firma_zak = p.get("zakaznik.firma")
    _strana(root, "AccountingCustomerParty", p.get("zakaznik.ico"), firma_zak or p.get("zakaznik.jmeno"), p.get("zakaznik.adresa"), p.get("zakaznik.dic"),
            kontakt=p.get("zakaznik.jmeno") if firma_zak else "", telefon=p.get("zakaznik.telefon"), email=p.get("zakaznik.email"))

    radky = _el(root, "InvoiceLines")
    rekap = OrderedDict()  # sazba DPH -> [základ, daň, celkem]
    for x in polozky:
        mn = Decimal(x["polozka.mnozstvi"] or 0); cena = Decimal(x["polozka.jednotkova_cena"] or 0)
        sazba = Decimal(x["polozka.sazba_dph"] or 0)
        bez, s = Decimal(x["polozka.cena_bez_dph"] or 0), Decimal(x["polozka.cena_s_dph"] or 0)
        r = _el(radky, "InvoiceLine")
        _el(r, "ID", x["polozka.poradi"])
        _el(r, "InvoicedQuantity", _cislo(mn), unitCode=x.get("polozka.jednotka") or "")
        _el(r, "LineExtensionAmount", _castka(bez))
        _el(r, "LineExtensionAmountTaxInclusive", _castka(s))
        _el(r, "LineExtensionTaxAmount", _castka(s - bez))
        _el(r, "UnitPrice", _castka(cena))
        _el(r, "UnitPriceTaxInclusive", _castka(cena * (1 + sazba / 100)))
        k = _el(r, "ClassifiedTaxCategory")
        _el(k, "Percent", _cislo(sazba))
        _el(k, "VATCalculationMethod", "0")  # 0 = DPH se počítá zdola (z ceny bez DPH), stejně jako v aplikaci
        _el(k, "VATApplicable", vat)
        _el(_el(r, "Item"), "Description", x["polozka.popis"] or "")
        sk = rekap.setdefault(sazba, [Decimal(0), Decimal(0), Decimal(0)])
        sk[0] += bez; sk[1] += s - bez; sk[2] += s

    dane = _el(root, "TaxTotal")
    for sazba, (bez, dan, s) in sorted(rekap.items()):
        t = _el(dane, "TaxSubTotal")
        for nazev, hodnota in (("TaxableAmount", bez), ("TaxAmount", dan), ("TaxInclusiveAmount", s),
                               ("AlreadyClaimedTaxableAmount", 0), ("AlreadyClaimedTaxAmount", 0), ("AlreadyClaimedTaxInclusiveAmount", 0),
                               ("DifferenceTaxableAmount", bez), ("DifferenceTaxAmount", dan), ("DifferenceTaxInclusiveAmount", s)):
            _el(t, nazev, _castka(hodnota))
        k = _el(t, "TaxCategory"); _el(k, "Percent", _cislo(sazba)); _el(k, "VATApplicable", vat); _el(k, "LocalReverseChargeFlag", "false")
    celk_bez = sum((v[0] for v in rekap.values()), Decimal(0)); celk_dan = sum((v[1] for v in rekap.values()), Decimal(0)); celk = celk_bez + celk_dan
    _el(dane, "TaxAmount", _castka(celk_dan))

    m = _el(root, "LegalMonetaryTotal")
    for nazev, hodnota in (("TaxExclusiveAmount", celk_bez), ("TaxInclusiveAmount", celk),
                           ("AlreadyClaimedTaxExclusiveAmount", 0), ("AlreadyClaimedTaxInclusiveAmount", 0),
                           ("DifferenceTaxExclusiveAmount", celk_bez), ("DifferenceTaxInclusiveAmount", celk),
                           ("PaidDepositsAmount", 0), ("PayableAmount", celk)):
        _el(m, nazev, _castka(hodnota))

    ucet = p.get("firma.cislo_uctu"); splatnost = p.get("dokument.datum_splatnosti")
    platba = _el(_el(root, "PaymentMeans"), "Payment")
    _el(platba, "PaidAmount", _castka(celk))
    _el(platba, "PaymentMeansCode", "42" if ucet else "10")  # 42 = převodem na účet, 10 = hotově
    if ucet and splatnost:
        cislo, banka, iban = rozdel_ucet(ucet)
        d = _el(platba, "Details")
        _el(d, "PaymentDueDate", splatnost.isoformat())
        _el(d, "ID", cislo); _el(d, "BankCode", banka); _el(d, "Name", ""); _el(d, "IBAN", iban); _el(d, "BIC", "")
        if p.get("dokument.variabilni_symbol"): _el(d, "VariableSymbol", p["dokument.variabilni_symbol"])
    return root


def over(root):
    """Ověří strom proti schématu ISDOC 6.0.2; při chybě vyvolá NeplatneISDOC s popisem."""
    s = _schema()
    if not s.validate(root):
        raise NeplatneISDOC("; ".join(f"řádek {e.line}: {e.message}" for e in s.error_log))


def faktura_isdoc(faktura):
    """Model Faktura -> obsah souboru .isdoc (bajty v kódování UTF-8), ověřený proti schématu."""
    from .typy import Faktura
    root = vytvor(Faktura.data(faktura), uuid_klic=f"faktura:{faktura.pk}:{faktura.cislo_faktury}")
    over(root)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
