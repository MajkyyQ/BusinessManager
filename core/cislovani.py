"""Číselné řady dokladů (zakázkový list, nabídka, faktura).

Formát se ukládá jako text se značkami, které uživatel nikdy nepíše ručně – vznikají z vzoru čísla
v Nastavení → Dokumenty:  {YYYY} rok 2026, {YY} rok 26, {MM} měsíc, {DD} den, {N4} pořadové číslo na 4 číslice.
Např. vzor „DMN260001“ = formát „DMN{YY}{N4}“.
"""
import re
from datetime import date

ZNACKA = re.compile(r"\{(YYYY|YY|MM|DD|N(\d{1,2}))\}")
NULOVANI = (("rok", "každý rok"), ("mesic", "každý měsíc"), ("nikdy", "nikdy"))
VYCHOZI = {  # stejné tvary jako dřív, takže se po aktualizaci nic nezmění
    "zakazka": dict(vzor="2026-001", format="{YYYY}-{N3}", nulovat="rok"),
    "nabidka": dict(vzor="2026-001", format="{YYYY}-{N3}", nulovat="rok"),
    "faktura": dict(vzor="001-04-11/2026", format="{N3}-{DD}-{MM}/{YYYY}", nulovat="rok"),
}
MAX_DELKA = 50  # délka sloupce s číslem dokladu


def _hodnoty(d):
    return {"YYYY": f"{d.year:04d}", "YY": f"{d.year % 100:02d}", "MM": f"{d.month:02d}", "DD": f"{d.day:02d}"}


def vyrob(fmt, d, n):
    """Číslo dokladu pro datum d a pořadí n."""
    h = _hodnoty(d)
    return ZNACKA.sub(lambda m: f"{n:0{int(m.group(2))}d}" if m.group(2) else h[m.group(1)], fmt)


def obdobi(nulovat, d):
    """Klíč období, ve kterém se pořadí počítá od 1 (rok 2026, měsíc 2026-11, nebo jedno období pořád)."""
    return f"{d.year}" if nulovat == "rok" else f"{d.year}-{d.month:02d}" if nulovat == "mesic" else ""


def regex(fmt, d=None, nulovat="nikdy"):
    """Regulární výraz, který pozná čísla v daném formátu; pořadí je skupina 1. Rok/měsíc jsou pevné jen
    v rámci období, ve kterém se pořadí počítá, jinak se přijme jakýkoli."""
    h = _hodnoty(d) if d else {}
    pevne = {"YYYY", "YY"} if nulovat in ("rok", "mesic") else set()
    if nulovat == "mesic": pevne.add("MM")
    out, i = "^", 0
    for m in ZNACKA.finditer(fmt):
        out += re.escape(fmt[i:m.start()]); z = m.group(1); i = m.end()
        if m.group(2): out += r"(\d+)"
        elif z in pevne and d: out += re.escape(h[z])
        else: out += r"\d{%d}" % (4 if z == "YYYY" else 2)
    return re.compile(out + re.escape(fmt[i:]) + "$")


def poradi_z_cisla(fmt, cislo):
    """Pořadové číslo z hotového čísla dokladu (None, když číslo do formátu nepatří)."""
    m = regex(fmt).match(cislo or "")
    if m: return int(m.group(1))
    m = re.search(r"(\d+)\D*$", cislo or "")  # ručně zadané číslo: poslední skupina číslic
    return int(m.group(1)) if m else None


def dalsi_poradi(fmt, nulovat, d, existujici, zacit_od=1, zacit_od_obdobi=""):
    """Nejbližší volné pořadí v období data d: za nejvyšším existujícím, ale nejméně „zacit_od“
    (to platí jen v období, ve kterém bylo nastaveno)."""
    rx = regex(fmt, d, nulovat)
    nums = [int(m.group(1)) for m in map(rx.match, existujici) if m]
    spodni = (zacit_od or 1) if obdobi(nulovat, d) == (zacit_od_obdobi or "") else 1
    return max(max(nums, default=0) + 1, spodni)


def over_format(fmt):
    """Chyba formátu jako text, nebo None."""
    if not fmt: return "Vyplňte vzor čísla."
    znacky = [m.group(1) for m in ZNACKA.finditer(fmt)]
    zbytek = ZNACKA.sub("", fmt)
    if "{" in zbytek or "}" in zbytek: return "Vzor nesmí obsahovat složené závorky."
    if sum(1 for z in znacky if z.startswith("N")) != 1: return "Ve vzoru musí být právě jedno pořadové číslo."
    if len(znacky) != len(set(znacky)): return "Rok, měsíc i den smí být ve vzoru nejvýš jednou."
    if len(vyrob(fmt, date(2099, 12, 31), 1)) > MAX_DELKA - 6: return f"Číslo je příliš dlouhé (nejvýš {MAX_DELKA - 6} znaků)."
    return None


def over_nulovani(fmt, nulovat):
    if nulovat in ("rok", "mesic") and "{YY" not in fmt: return "Pořadí lze nulovat každý rok jen tehdy, když je ve vzoru rok."
    if nulovat == "mesic" and "{MM}" not in fmt: return "Pořadí lze nulovat každý měsíc jen tehdy, když je ve vzoru měsíc."
    return None
