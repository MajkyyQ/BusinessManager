"""Převod do PDF přes LibreOffice (bez okna, na pozadí) a miniatury z PDF."""
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from django.conf import settings

_ZAMEK = threading.Lock()  # LibreOffice nesmí běžet se stejným profilem dvakrát naráz
WIN_CESTY = [r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"]


class ChybiLibreOffice(RuntimeError):
    pass


def soffice():
    """Cesta k LibreOffice: proměnná LIBREOFFICE, nebo PATH, nebo běžné místo instalace ve Windows."""
    c = os.getenv("LIBREOFFICE") or getattr(settings, "LIBREOFFICE", "")
    if c and Path(c).exists(): return c
    for n in ("soffice", "libreoffice"):
        p = shutil.which(n)
        if p: return p
    for p in WIN_CESTY:
        if Path(p).exists(): return p
    return None


XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Setup/L10N"><prop oor:name="ooSetupSystemLocale" oor:op="fuse"><value>cs-CZ</value></prop></item>
<item oor:path="/org.openoffice.Setup/L10N"><prop oor:name="ooLocale" oor:op="fuse"><value>cs-CZ</value></prop></item>
</oor:items>
"""


def _profil():
    """Vlastní profil LibreOffice s českým národním prostředím (formát čísel 1 500,00 a dat 1. 11. 2026)."""
    p = Path(tempfile.gettempdir()) / "businessmanager_lo_profil"
    x = p / "user" / "registrymodifications.xcu"
    if not x.exists():
        x.parent.mkdir(parents=True, exist_ok=True); x.write_text(XCU, encoding="utf-8")
    return p


def na_xlsx(soubor):
    """Starý formát .xls -> .xlsx (bytes)."""
    return na_pdf(soubor, cil="xlsx")


def na_pdf(soubor, filtr=None, cil="pdf"):
    """Převede soubor (xlsx, html…) na PDF (nebo jiný formát `cil`) a vrátí jeho obsah (bytes)."""
    exe = soffice()
    if not exe: raise ChybiLibreOffice("Pro převod do PDF je potřeba nainstalovat LibreOffice (zdarma, libreoffice.org).")
    soubor = Path(soubor)
    profil = _profil()
    with tempfile.TemporaryDirectory() as out, _ZAMEK:
        cmd = [exe, f"-env:UserInstallation={profil.as_uri()}", "--headless", "--norestore", "--nologo",
               "--convert-to", f"{cil}:{filtr}" if filtr else cil, "--outdir", out, str(soubor)]
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        pdf = Path(out) / (soubor.stem + "." + cil)
        if not pdf.exists():
            raise RuntimeError("LibreOffice soubor nepřevedl: " + (r.stderr or r.stdout).decode(errors="ignore")[-500:])
        return pdf.read_bytes()


def miniatura(pdf_bytes, sirka=420):
    """První strana PDF jako PNG (bytes). Bez knihovny pypdfium2 vrátí None."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    import io
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        page = doc[0]; w, _ = page.get_size()
        img = page.render(scale=sirka / w).to_pil()
        b = io.BytesIO(); img.save(b, "PNG", optimize=True); return b.getvalue()
    finally:
        doc.close()
