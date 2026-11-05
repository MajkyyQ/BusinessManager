"""Tlačítka Zpět a Zrušit vrací na stránku, ze které uživatel opravdu přišel.

Aplikace si v relaci pamatuje posledních pár navštívených stránek (jen zobrazení, ne formuláře).
Zpět vede na předchozí stránku v této stopě, Zrušit ve formuláři na stránku, odkud se formulář otevřel."""
from urllib.parse import urlsplit
from django.urls import resolve, Resolver404

KLIC = "bm_stopa"; MAX = 20
# stránky, které se do stopy nezapisují: formuláře, pomocné odpovědi (náhledy, soubory, vyhledávání)
NEZAPISOVAT = {"create", "edit", "delete", "lookup", "lookup_new", "zakazka_nova", "nabidka_nova", "nabidka_nahled", "faktura_nova", "objednavka_nova",
               "prijata_faktura_import", "prijata_faktura_rucne", "nastaveni_firma", "nastaveni_cislovani", "pruvodce_ucet", "pruvodce_firma",
               "sablona_nova", "sablona_edit", "sablona_editor", "sablona_miniatura", "sablona_ukazka", "sablona_stahnout", "sablona_akce",
               "dokument_obsah", "dokument_pdf", "dokument_isdoc", "stav_akce", "prijata_faktura_zaplaceno", "faktura_zaplaceno", "fotografie_nove", "login", "logout"}


def _cesta(u): return urlsplit(u).path


def _zapisovat(request):
    if request.method != "GET" or request.headers.get("HX-Request"): return False
    try: m = resolve(request.path_info)
    except Resolver404: return False
    return m.app_name != "admin" and m.url_name not in NEZAPISOVAT and not request.path.startswith(("/admin/", "/static/", "/media/"))


def _odkud(request, stopa):
    """Stopa oříznutá za stránkou, ze které uživatel opravdu klikl (hlavička Referer). Pozná se tak i návrat tlačítkem Zpět v prohlížeči."""
    ref = request.META.get("HTTP_REFERER", "")
    if not ref: return stopa
    r = urlsplit(ref)
    if r.netloc and r.netloc != request.get_host(): return stopa
    j = next((k for k in range(len(stopa) - 1, -1, -1) if _cesta(stopa[k]) == r.path), None)
    return stopa if j is None else stopa[:j + 1]


def zpet(request, vynechat=()):
    """Adresa stránky, ze které uživatel přišel (nebo None). Stránky z `vynechat` (cesty) se přeskočí."""
    stopa = request.session.get(KLIC, []) if hasattr(request, "session") else []
    if not any(_cesta(u) == request.path for u in stopa): stopa = _odkud(request, stopa)
    tady = request.path; vynechat = set(vynechat) | {tady}
    i = next((k for k in range(len(stopa) - 1, -1, -1) if _cesta(stopa[k]) == tady), len(stopa))  # vrátil-li se uživatel na starší stránku, bere se stopa před ní
    for u in reversed(stopa[:i]):
        if _cesta(u) not in vynechat: return u
    return None


class StopaMiddleware:
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        r = self.get_response(request)
        if r.status_code == 200 and "text/html" in r.get("Content-Type", "") and getattr(request, "user", None) and request.user.is_authenticated and _zapisovat(request):
            stopa = _odkud(request, list(request.session.get(KLIC, []))); u = request.get_full_path()
            i = next((k for k in range(len(stopa) - 1, -1, -1) if _cesta(stopa[k]) == request.path), None)
            if i is not None: stopa = stopa[:i]  # stejná stránka (třeba jen jiný filtr) nebo návrat zpět: stopa se zkrátí
            stopa.append(u); request.session[KLIC] = stopa[-MAX:]
        return r
