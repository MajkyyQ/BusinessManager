"""Bezpečné nahrávání a odesílání souborů (fotky, přílohy, přijaté faktury, logo).

Nahrané soubory leží v MEDIA_ROOT a prohlížeč je otevírá ze stejné adresy jako aplikaci. Kdyby uživatel nahrál
soubor .html nebo .svg se skriptem, skript by běžel pod přihlášením toho, kdo soubor otevře (třeba administrátora).
Proto platí dvě pojistky (viz docs/12-bezpecnost.md):

1. Při nahrání se povolí jen známé přípony (`PRIPONY_PRILOH`, `PRIPONY_PRIJATYCH_FAKTUR`), fotky ověří knihovna Pillow.
2. Při odeslání má každý soubor hlavičku `X-Content-Type-Options: nosniff`. Obrázky a PDF se zobrazí v prohlížeči,
   všechno ostatní se jen stáhne (`Content-Disposition: attachment`) a navíc s `Content-Security-Policy: sandbox`,
   takže se skript nespustí, ani kdyby se soubor do MEDIA_ROOT dostal jinou cestou (starší data, ruční kopie).

Velikost nahrávaných souborů hlídají `velikost_souboru` (jeden soubor, výchozí 50 MB) a `LimitNahravaniMiddleware`
(celý požadavek, např. víc fotek najednou, výchozí 500 MB). Obojí jde změnit v .env.

Kdo smí který soubor otevřít, určuje core.prava (MEDIA_PRAVA)."""
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.http import HttpResponse
from django.views.static import serve

MB = 1024 * 1024

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


def velikost_souboru(f):
    """Jeden nahraný soubor nesmí být větší než MAX_VELIKOST_SOUBORU_MB (fotka z mobilu má 3–15 MB, sken PDF jednotky až desítky MB)."""
    limit = settings.MAX_VELIKOST_SOUBORU_MB
    if f and getattr(f, "size", 0) > limit * MB:
        raise ValidationError(f"Soubor {getattr(f, 'name', '')} je příliš velký ({f.size / MB:.0f} MB). Největší povolená velikost je {limit} MB.")


class LimitNahravaniMiddleware:
    """Odmítne požadavek větší než MAX_VELIKOST_NAHRAVANI_MB dřív, než se začne ukládat na disk."""
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        limit = settings.MAX_VELIKOST_NAHRAVANI_MB
        try: delka = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError: delka = 0
        if delka > limit * MB:
            return HttpResponse(f"<!doctype html><meta charset='utf-8'><title>Příliš velké</title><p style='font-family:sans-serif;margin:2rem'>"
                                f"Nahrávané soubory jsou dohromady příliš velké ({delka / MB:.0f} MB, povoleno nejvýš {limit} MB). "
                                f"Nahrajte je po menších částech. <a href='javascript:history.back()'>Zpět</a></p>", status=413)
        return self.get_response(request)


def media(request, path):
    """Nahraný soubor z MEDIA_ROOT s bezpečnostními hlavičkami (oprávnění už ověřil core.prava.PravaMiddleware)."""
    r = serve(request, path, document_root=settings.MEDIA_ROOT)
    r["X-Content-Type-Options"] = "nosniff"
    if PurePosixPath(path).suffix.lower() not in ZOBRAZIT:
        r["Content-Disposition"] = "attachment"
        r["Content-Security-Policy"] = "sandbox"
    return r
