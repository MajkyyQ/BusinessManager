"""Převod do PDF přes LibreOffice (bez okna, na pozadí) a miniatury z PDF."""
import os
import shutil
import subprocess
import tempfile
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

_ZAMEK = threading.Lock()  # LibreOffice nesmí běžet se stejným profilem dvakrát naráz (vlákna jednoho procesu)
POKUSY = 3  # první spuštění s novým profilem LibreOffice často skončí bez výsledku (profil teprve zakládá), další už projde
WIN_CESTY = [r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"]


class ChybiLibreOffice(RuntimeError):
    """LibreOffice na počítači není."""


class PrevodSeNepovedl(RuntimeError):
    """LibreOffice je nainstalovaný, ale převod selhal (např. vypršel čas při prvním spuštění)."""


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


@contextmanager
def _zamek_profilu(profil):
    """Převody jdou jeden po druhém: zámek mezi vlákny i mezi procesy (gunicorn má víc workerů)."""
    with _ZAMEK:
        f = open(profil / "businessmanager.lock", "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt
                f.seek(0)
                while True:
                    try:
                        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1); break
                    except OSError:  # LK_LOCK to po 10 s vzdá, zkoušíme dál
                        pass
                try:
                    yield
                finally:
                    f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


def _spust(cmd, limit):
    """Spustí LibreOffice; při překročení limitu ukončí celý strom procesů (ve Windows by jinak zůstal viset soffice.bin
    a držel profil zamčený, takže by selhávaly i další převody)."""
    win = sys.platform == "win32"
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if win else 0, start_new_session=not win)
    try:
        out, err = p.communicate(timeout=limit)
        return p.returncode, (err or out).decode(errors="ignore")[-500:]
    except subprocess.TimeoutExpired:
        if win:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                p.kill()
        p.communicate()
        return None, f"LibreOffice nestihl převod do {limit} s."


def na_pdf(soubor, filtr=None, cil="pdf"):
    """Převede soubor (xlsx, html…) na PDF (nebo jiný formát `cil`) a vrátí jeho obsah (bytes)."""
    exe = soffice()
    if not exe: raise ChybiLibreOffice("Pro převod do PDF je potřeba nainstalovat LibreOffice (zdarma, libreoffice.org).")
    soubor = Path(soubor)
    profil = _profil()
    limit = int(getattr(settings, "LIBREOFFICE_LIMIT", 0) or os.getenv("LIBREOFFICE_LIMIT") or 180)
    chyba = ""
    with _zamek_profilu(profil):
        for pokus in range(POKUSY):
            if pokus: time.sleep(1)
            with tempfile.TemporaryDirectory() as out:
                cmd = [exe, f"-env:UserInstallation={profil.as_uri()}", "--headless", "--norestore", "--nologo",
                       "--convert-to", f"{cil}:{filtr}" if filtr else cil, "--outdir", out, str(soubor)]
                try:
                    _, chyba = _spust(cmd, limit)
                except OSError as e:
                    raise ChybiLibreOffice(f"LibreOffice nejde spustit ({e}).")
                vysledek = Path(out) / (soubor.stem + "." + cil)
                if vysledek.exists() and vysledek.stat().st_size:
                    return vysledek.read_bytes()
    raise PrevodSeNepovedl("LibreOffice soubor nepřevedl" + (f": {chyba.strip()}" if chyba.strip() else "."))


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
