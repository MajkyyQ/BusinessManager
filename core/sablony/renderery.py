"""Formáty šablon. Každý renderer z šablony a dat vyrobí náhled a PDF.

Nový formát (např. Word) = nová třída se stejným rozhraním, zaregistrovaná přes @registruj.
"""
import hashlib
import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template

from . import prevod
from .typy import formatuj

VZORY = Path(__file__).parent / "vzory"   # vestavěné šablony dodávané s aplikací
REGISTR = {}


def registruj(cls):
    REGISTR[cls.kod] = cls(); return cls


def renderer(sablona):
    return REGISTR.get(sablona.format) or REGISTR["html"]


def podle_pripony(nazev):
    e = nazev.rsplit(".", 1)[-1].lower()
    for r in REGISTR.values():
        if e in r.pripony: return r
    return None


def cesta_souboru(sablona):
    if sablona.soubor: return Path(sablona.soubor.path)
    if sablona.vestavena: return VZORY / sablona.vestavena
    return None


def _json(o):
    return json.dumps(o, default=str, sort_keys=True, ensure_ascii=False)


def _cache(sablona, data, pripona):
    """Hotové PDF se ukládá, dokud se nezmění šablona ani data (převod trvá 1–3 s)."""
    k = hashlib.sha1(_json([sablona.pk, sablona.verze, str(sablona.datum_upravy), sablona.format, str(cesta_souboru(sablona)), sablona.mapovani, data]).encode()).hexdigest()
    d = Path(settings.MEDIA_ROOT) / "cache" / "dokumenty"; d.mkdir(parents=True, exist_ok=True)
    return d / f"{k}.{pripona}"


class Renderer:
    kod = ""; nazev = ""; pripony = (); nahled_typ = "application/pdf"

    def analyzuj(self, sablona, typ_cls):
        """Po nahrání souboru: rozbor šablony a návrh mapování. Vrací dict pro sablona.mapovani."""
        return {}

    def nahled(self, sablona, typ_cls, data):
        """Obsah pro zobrazení v náhledu: (content_type, bytes)."""
        return "application/pdf", self.pdf(sablona, typ_cls, data)

    def pdf(self, sablona, typ_cls, data):
        raise NotImplementedError


@registruj
class ExcelRenderer(Renderer):
    kod = "excel"; nazev = "Excel (.xlsx)"; pripony = ("xlsx", "xlsm")

    def analyzuj(self, sablona, typ_cls):
        from .excel import analyzuj
        return analyzuj(cesta_souboru(sablona), typ_cls)

    def xlsx(self, sablona, typ_cls, data):
        from .excel import vypln
        import io
        wb = vypln(cesta_souboru(sablona), sablona.mapovani, data, typ_cls)
        b = io.BytesIO(); wb.save(b); return b.getvalue()

    def pdf(self, sablona, typ_cls, data):
        c = _cache(sablona, data, "pdf")
        if c.exists(): return c.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            x = Path(d) / "dokument.xlsx"; x.write_bytes(self.xlsx(sablona, typ_cls, data))
            pdf = prevod.na_pdf(x)
        c.write_bytes(pdf); return pdf


def html_kontext(typ_cls, data):
    """Data jako vnořené slovníky pro šablonu Django: {{ firma.nazev }}, {% for p in polozky %}{{ p.popis }}."""
    pd = typ_cls.pole_dict(); mena = data["pole"].get("soucty.mena", "CZK")
    def vnor(src):
        out = {}
        for k, v in src.items():
            sk, _, pk = k.partition(".")
            p = pd.get(k); out.setdefault(sk, {})[pk] = v if (p and p.druh == "obrazek") else formatuj(v, p.druh if p else "text", mena)
        return out
    c = vnor(data["pole"]); c["polozky"] = [vnor(p)["polozka"] for p in data["polozky"]]
    c["typ"] = {"kod": typ_cls.kod, "nazev": typ_cls.nazev}
    logo = data["pole"].get("firma.logo")
    if logo:
        try:
            rel = Path(logo).resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())
            c["firma"]["logo_url"] = settings.MEDIA_URL.rstrip("/") + "/" + rel.as_posix()
            c["firma"]["logo_uri"] = Path(logo).resolve().as_uri()
        except ValueError:
            pass
    return c


@registruj
class HtmlRenderer(Renderer):
    """HTML šablona v jazyce šablon Django. Náhled je přímo HTML, PDF vytvoří LibreOffice."""
    kod = "html"; nazev = "HTML"; pripony = ("html", "htm"); nahled_typ = "text/html"

    def analyzuj(self, sablona, typ_cls):
        import re
        t = cesta_souboru(sablona).read_text(encoding="utf-8", errors="ignore")
        return {"verze": 1, "znacky": [{"pole": m} for m in sorted(set(re.findall(r"\{\{\s*([a-z_]+\.[a-z_]+)", t)))]}

    def html(self, sablona, typ_cls, data, pro_pdf=False):
        c = html_kontext(typ_cls, data); c["pro_pdf"] = pro_pdf
        if sablona.soubor:
            return Template(Path(sablona.soubor.path).read_text(encoding="utf-8", errors="ignore")).render(Context(c))
        return get_template(f"sablony_vestavene/{sablona.vestavena}").render(c)

    def nahled(self, sablona, typ_cls, data):
        return "text/html; charset=utf-8", self.html(sablona, typ_cls, data).encode()

    def pdf(self, sablona, typ_cls, data):
        c = _cache(sablona, data, "pdf")
        if c.exists(): return c.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            x = Path(d) / "dokument.html"; x.write_text(self.html(sablona, typ_cls, data, pro_pdf=True), encoding="utf-8")
            pdf = prevod.na_pdf(x, "writer_web_pdf_Export")
        c.write_bytes(pdf); return pdf
