"""Volitelné moduly: rozšíření, která v základní aplikaci nejsou a přidávají se zvlášť.

Modul je samostatná aplikace Django ve složce `moduly/<kod>/` (vedle složky `core`). Při startu ji najde
`config/settings.py` (funkce `najdi_moduly`), přidá ji do INSTALLED_APPS, její adresy připojí pod `/moduly/<kod>/`
a její tabulky vytvoří migrace, které se spouštějí při každém startu. Odebrání modulu = smazání jeho složky.

Modul se do aplikace „zapojí“ v metodě `ready()` svého AppConfig voláním `registruj(Modul(...))`. Tím aplikaci řekne:
- jak se jmenuje, co dělá a co potřebuje (zobrazí se v Nastavení → Moduly),
- odkazy do Nastavení (`nastaveni`),
- tlačítka na zakázce (`akce_zakazky`) a v náhledu dokumentu (`akce_dokumentu`),
- která oprávnění vyžadují jeho stránky (`prava`; bez záznamu stačí základní přístup).

Základní aplikace o žádném konkrétním modulu neví, zná jen tato místa pro rozšíření. Návod je v docs/11-moduly.md."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

KOD = re.compile(r"^[a-z][a-z0-9_]*$")  # název složky modulu = název balíčku Pythonu


def najdi_moduly(base_dir, vypnute=""):
    """Kódy modulů ve složce moduly/ (každá podsložka s apps.py). Proměnná MODULY_VYPNUTE v .env vypne modul bez mazání."""
    d = Path(base_dir) / "moduly"
    if not d.is_dir(): return []
    vyp = {x.strip() for x in vypnute.split(",") if x.strip()}
    return sorted(p.name for p in d.iterdir() if p.is_dir() and KOD.match(p.name) and (p / "__init__.py").exists() and (p / "apps.py").exists() and p.name not in vyp)


@dataclass
class Modul:
    kod: str
    nazev: str
    popis: str = ""
    verze: str = ""
    pozadavky: str = ""  # např. „připojení k internetu“; zobrazí se v Nastavení → Moduly
    nastaveni: list = field(default_factory=list)  # [(popisek, název adresy)] – odkazy v Nastavení → Moduly
    akce_zakazky: Callable = None  # (request, zakazka) -> [dict(text, url, title)]
    akce_dokumentu: Callable = None  # (request, typ, objekt) -> [dict(text, url, title)]
    prava: dict = field(default_factory=dict)  # {"jmenny_prostor:nazev_adresy": {kód oprávnění}}

    @property
    def odkazy(self):
        from django.urls import NoReverseMatch, reverse
        out = []
        for popisek, nazev in self.nastaveni:
            try: out.append((popisek, reverse(nazev)))
            except NoReverseMatch: pass
        return out


REGISTR: dict[str, Modul] = {}


def registruj(m: Modul):
    REGISTR[m.kod] = m
    return m


def seznam(): return sorted(REGISTR.values(), key=lambda m: m.nazev)


def potrebna_prava(view_name):
    """Oprávnění, která vyžaduje stránka modulu (kromě základního přístupu). None = nejde o stránku modulu."""
    for m in REGISTR.values():
        if view_name in m.prava: return [set(m.prava[view_name])]
    return None


def _akce(request, nazev, *args):
    out = []
    for m in seznam():
        f = getattr(m, nazev)
        if not f: continue
        try:
            out += [dict(a, modul=m.nazev) for a in (f(request, *args) or [])]
        except Exception:  # chyba v modulu nesmí shodit stránku základní aplikace
            import logging
            logging.getLogger(__name__).exception("Modul %s: chyba v %s", m.kod, nazev)
    return [a for a in out if _smi(request, a.get("url"))]


def _smi(request, url):
    from .prava import smi
    return not url or smi(request.user, url)


def akce_zakazky(request, z): return _akce(request, "akce_zakazky", z)
def akce_dokumentu(request, typ, obj): return _akce(request, "akce_dokumentu", typ, obj)
