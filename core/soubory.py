"""Bezpečné nahrávání a odesílání souborů (fotky, přílohy, přijaté faktury, logo).

Nahrané soubory leží v MEDIA_ROOT a prohlížeč je otevírá ze stejné adresy jako aplikaci. Kdyby uživatel nahrál
soubor .html nebo .svg se skriptem, skript by běžel pod přihlášením toho, kdo soubor otevře (třeba administrátora).
Proto platí dvě pojistky (viz docs/12-bezpecnost.md):

1. Při nahrání se povolí jen známé přípony (`PRIPONY_PRILOH`, `PRIPONY_PRIJATYCH_FAKTUR`), fotky ověří knihovna Pillow.
2. Při odeslání má každý soubor hlavičku `X-Content-Type-Options: nosniff`. Obrázky a PDF se zobrazí v prohlížeči,
   všechno ostatní se jen stáhne (`Content-Disposition: attachment`) a navíc s `Content-Security-Policy: sandbox`,
   takže se skript nespustí, ani kdyby se soubor do MEDIA_ROOT dostal jinou cestou (starší data, ruční kopie).

Kdo smí který soubor otevřít, určuje core.prava (MEDIA_PRAVA)."""
from pathlib import PurePosixPath

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.views.static import serve

# Přílohy zakázky: dokumenty, tabulky, obrázky, archivy. Žádné HTML, SVG ani spustitelné soubory.
PRIPONY_PRILOH = ("pdf", "doc", "docx", "xls", "xlsx", "odt", "ods", "odp", "ppt", "pptx", "rtf", "txt", "csv",
                  "jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "heic", "zip", "7z", "rar", "msg", "eml",
                  "isdoc", "isdocx", "xml")
PRIPONY_PRIJATYCH_FAKTUR = ("pdf", "isdoc", "isdocx", "xml", "jpg", "jpeg", "png")
# tyto typy prohlížeč zobrazí sám a skript v nich neběží; ostatní soubory se jen stahují
ZOBRAZIT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".pdf"}

pripona_prilohy = FileExtensionValidator(PRIPONY_PRILOH, "Tento typ souboru nelze nahrát. Povolené přípony: %(allowed_extensions)s.")
pripona_prijate_faktury = FileExtensionValidator(PRIPONY_PRIJATYCH_FAKTUR, "Tento typ souboru nelze nahrát. Povolené přípony: %(allowed_extensions)s.")
pripona_isdoc = FileExtensionValidator(("isdoc", "isdocx", "xml"), "Nahrajte fakturu ve formátu ISDOC (.isdoc nebo .isdocx).")


def media(request, path):
    """Nahraný soubor z MEDIA_ROOT s bezpečnostními hlavičkami (oprávnění už ověřil core.prava.PravaMiddleware)."""
    r = serve(request, path, document_root=settings.MEDIA_ROOT)
    r["X-Content-Type-Options"] = "nosniff"
    if PurePosixPath(path).suffix.lower() not in ZOBRAZIT:
        r["Content-Disposition"] = "attachment"
        r["Content-Security-Policy"] = "sandbox"
    return r
