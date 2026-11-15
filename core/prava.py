"""Oprávnění uživatelů: Zaměstnanec → Role → Oprávnění.

Oprávnění je jeden „klíč“ (např. smí vystavit fakturu), role je svazek klíčů (např. Technik) a zaměstnanci se přiřadí role.
Role s volbou „je administrátor“ smí všechno, stejně jako účet administrátora (staff/superuser z Django adminu).

Které oprávnění je potřeba pro kterou stránku, je popsané na jediném místě: funkce `potrebna_prava()`.
Používá ji middleware (kontrola na serveru) i šablony (filtr `smi`, který skryje tlačítka bez oprávnění)."""
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import resolve, Resolver404
from urllib.parse import urlsplit

PRISTUP, STAV, ZAKAZNICI, KALENDAR, NABIDKY, FAKTURY, MAZAT, NASTAVENI = (
    "aplikace.pristup", "zakazky.zmenit_stav", "zakaznici.upravit", "kalendar.upravit",
    "nabidky.spravovat", "faktury.spravovat", "zaznamy.mazat", "nastaveni.spravovat")

# kód, název, popis – stejný seznam vytváří migrace 0018 a seed po každé migraci (core/apps.py)
PRAVA = [
    (PRISTUP, "Základní přístup", "Pracovní plocha, prohlížení zakázek, zákazníků a zařízení. Zakládání a úprava zakázek, zápis práce, materiálu, fotek "
                                  "a příloh, založení nového zákazníka, kontaktu nebo zařízení a vytváření událostí v kalendáři."),
    (STAV, "Ruční změna stavu zakázky", "Přepnutí zakázky do libovolného stavu mimo běžný postup (Zahájit práci, Dokončit opravu…)."),
    (ZAKAZNICI, "Úprava zákazníků a zařízení", "Úprava už založených zákazníků, kontaktních osob a zařízení."),
    (KALENDAR, "Úprava kalendáře", "Úprava a mazání událostí v kalendáři, i těch, které vytvořil někdo jiný. Svoje události může upravit každý."),
    (NABIDKY, "Nabídky a objednávky", "Vytváření a úprava nabídek a přijatých objednávek. Zpřístupní i sekci Dokumenty a ceny v dokladech."),
    (FAKTURY, "Faktury a platby", "Vystavení faktury, označení zaplacení, platby a přijaté faktury. Zpřístupní i sekci Dokumenty a ceny v dokladech."),
    (MAZAT, "Mazání a deaktivace", "Mazání a deaktivace záznamů (zakázky, zákazníci, zařízení, doklady…). Řádek práce nebo materiálu u zakázky smí smazat každý, "
                                   "fotku a přílohu jen ten, kdo ji nahrál."),
    (NASTAVENI, "Nastavení", "Údaje o firmě, DPH, číslování a šablony dokumentů, katalogy, zaměstnanci, role a zálohy."),
]
VSE = frozenset(k for k, *_ in PRAVA)  # jen oprávnění základní aplikace; včetně modulů viz vse()
NAZEV = {k: n for k, n, _ in PRAVA}


def vse():
    """Všechna oprávnění včetně těch, která přidávají volitelné moduly (core/moduly.py)."""
    from . import moduly
    return VSE | {k for k, *_ in moduly.opravneni()}


def nazev(kod):
    from . import moduly
    return NAZEV.get(kod) or next((n for k, n, *_ in moduly.opravneni() if k == kod), kod)

# výchozí role (vytvoří migrace 0018); název, oprávnění, je administrátor, popis
ROLE = [
    ("Zaměstnanec", [PRISTUP], False, "Základní přístup. Dostane ji automaticky každý nový zaměstnanec."),
    ("Technik", [PRISTUP, STAV, KALENDAR], False, "Opravy: zakázky, práce, materiál a ruční změna stavu zakázky."),
    ("Administrativa", [PRISTUP, STAV, ZAKAZNICI, KALENDAR, NABIDKY, FAKTURY], False, "Kancelář: zákazníci, nabídky, faktury a platby."),
    ("Administrátor", [], True, "Smí všechno včetně mazání a Nastavení."),
]
VYCHOZI_ROLE = "Zaměstnanec"

# tabulky (slug modelu) podle toho, které oprávnění je potřeba
T_NASTAVENI = {"nastavenifirmy", "sazbadph", "zamestnanec", "role", "opravneni", "stavzakazky", "typukonu", "material", "dodavatel", "historiezmen",
               "ciselnarada", "sablonadokumentu"}
T_NABIDKY = {"nabidka", "polozkanabidky", "objednavka"}
T_FAKTURY = {"faktura", "polozkafaktury", "platba", "prijatafaktura"}
T_ZAKAZNICI = {"zakaznik", "kontaktniosoba", "zakaznikkontakt", "zarizeni"}
T_CASTI_ZAKAZKY = {"provedenyukon", "pouzitymaterial", "fotografie", "priloha", "zakazkakontakt"}  # zápis práce: smazat smí každý (fotku a přílohu jen svou, viz _vlastni_soubor)
T_NAHRANE = {"fotografie", "priloha"}  # soubory s polem „nahrál“: bez oprávnění Mazání smí smazat jen ten, kdo je nahrál
# soubory v /media/ podle složky: přijaté faktury jen s oprávněním Faktury, šablony dokumentů jen s Nastavením; ostatní (fotky, přílohy, logo) se základním přístupem
MEDIA_PRAVA = {"prijate_faktury/": FAKTURY, "sablony/": NASTAVENI}
DOKLADY = {"nabidka": NABIDKY, "faktura": FAKTURY}  # typ dokumentu (náhled, PDF) -> oprávnění; zakázkový list smí každý
FINANCE = frozenset({NABIDKY, FAKTURY})  # stačí jedno z nich

BEZ_KONTROLY = {"login", "logout", "pruvodce_ucet", "pruvodce_firma"}
SABLONY = {"sablony", "sablona_nova", "sablona_edit", "sablona_detail", "sablona_akce", "sablona_stahnout", "sablony_znacky", "sablona_editor", "sablona_ukazka"}


def prava(user):
    """Množina kódů oprávnění přihlášeného uživatele (spočítá se jednou za požadavek)."""
    if not getattr(user, "is_authenticated", False) or not user.is_active: return frozenset()
    if hasattr(user, "_bm_prava"): return user._bm_prava
    if user.is_staff or user.is_superuser: p = vse()
    else:
        from .models import Role
        role = Role.objects.filter(aktivni=True, zamestnanec__uzivatel=user, zamestnanec__aktivni=True)
        if role.filter(je_administrator=True).exists(): p = vse()
        else: p = frozenset(role.values_list("opravneni__kod", flat=True)) - {None}
    user._bm_prava = p
    return p


def ma(user, kod): return kod in prava(user)
def finance(user): return bool(prava(user) & FINANCE)


def potrebna_prava(name, kw, get=None):
    """Seznam požadavků pro stránku `name` s parametry `kw`. Každý požadavek je množina kódů, z nichž stačí jeden.
    Prázdný seznam = stačí přihlášení. None = bez kontroly (přihlášení, průvodce)."""
    name = name or ""
    if name in BEZ_KONTROLY: return None
    if ":" in name:  # stránka volitelného modulu (jmenný prostor modulu), oprávnění určuje modul sám
        from . import moduly
        return [{PRISTUP}] + (moduly.potrebna_prava(name) or [])
    req = [{PRISTUP}]; slug = kw.get("slug"); get = get or {}
    if name in ("list", "detail", "create", "edit", "delete"):
        if slug in T_NASTAVENI: req.append({NASTAVENI})
        elif slug in T_NABIDKY: req.append({NABIDKY})
        elif slug in T_FAKTURY: req.append({FAKTURY})
        elif slug == "kalendarudalost" and name in ("edit", "delete"): req.append({KALENDAR})  # vlastní událost: viz smi()
        elif slug in T_ZAKAZNICI and name == "edit": req.append({ZAKAZNICI})
        if name == "delete" and (slug not in T_CASTI_ZAKAZKY or slug in T_NAHRANE) and slug != "kalendarudalost": req.append({MAZAT})  # vlastní soubor: viz smi_stranku()
        if name == "create" and slug == "dodavatel": req[-1] = {NASTAVENI, FAKTURY}
    elif name.startswith("nastaveni") or name in SABLONY: req.append({NASTAVENI})
    elif name in ("nabidka_nova", "objednavka_nova"): req.append({NABIDKY})
    elif name in ("faktura_nova", "faktura_zaplaceno") or name.startswith("prijata_faktura"): req.append({FAKTURY})
    elif name in ("dokumenty", "nabidka_nahled"): req.append(set(FINANCE))
    elif name.startswith("dokument"):
        typ = kw.get("typ")
        if typ in DOKLADY: req.append({DOKLADY[typ]})
    elif name == "lookup_new" and slug == "dodavatel": req.append({NASTAVENI, FAKTURY})
    elif name == "lookup_new" and slug == "role": req.append({NASTAVENI})
    return req


def _splneno(p, req): return all(p & r for r in req)


def _vlastni_udalost(user, name, kw):
    if kw.get("slug") != "kalendarudalost" or name not in ("edit", "delete") or not kw.get("pk"): return False
    from .models import KalendarUdalost
    return KalendarUdalost.objects.filter(pk=kw["pk"], vytvoril=user, automaticka=False).exists()


def _vlastni_soubor(user, name, kw):
    """Fotka nebo příloha, kterou nahrál sám uživatel (smí ji smazat i bez oprávnění Mazání)."""
    slug = kw.get("slug")
    if slug not in T_NAHRANE or name != "delete" or not kw.get("pk"): return False
    from django.apps import apps
    return apps.get_model("core", slug).objects.filter(pk=kw["pk"], nahral=user).exists()


def smi_stranku(user, name, kw, get=None):
    req = potrebna_prava(name, kw, get)
    if req is None: return True
    p = prava(user)
    if _splneno(p, req): return True
    if _splneno(p, [r for r in req if r != {MAZAT}]) and _vlastni_soubor(user, name, kw): return True
    return _splneno(p, [r for r in req if r != {KALENDAR}]) and _vlastni_udalost(user, name, kw)


def pravo_souboru(cesta):
    """Oprávnění potřebné pro soubor v /media/ (cesta bez /media/). Cesta se normalizuje stejně jako při odeslání souboru (fotky/../prijate_faktury/…)."""
    import posixpath
    cesta = posixpath.normpath(cesta.replace("\\", "/")).lstrip("/")
    return next((k for slozka, k in MEDIA_PRAVA.items() if cesta.startswith(slozka)), PRISTUP)


def smi(user, url):
    """Smí uživatel otevřít adresu `url`? (pro skrývání tlačítek v šablonách)"""
    try: m = resolve(urlsplit(str(url)).path)
    except Resolver404: return True
    if m.app_name == "admin": return bool(user.is_staff)
    return smi_stranku(user, m.view_name, m.kwargs)


def popis_chybejiciho(user, req):
    p = prava(user)
    chybi = next((r for r in req if not p & r), set())
    return " nebo ".join(f"„{nazev(k)}“" for k in sorted(chybi))


class PravaMiddleware:
    """Kontrola oprávnění na serveru pro každou stránku aplikace (tlačítko skryté v šabloně nestačí – adresa jde zadat ručně)."""
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request): return self.get_response(request)

    def process_view(self, request, view, args, kwargs):
        m = getattr(request, "resolver_match", None)
        if not m or m.app_name == "admin" or not request.user.is_authenticated: return None
        if request.path.startswith("/media/"):  # soubory: fotky a přílohy se základním přístupem, přijaté faktury a šablony podle MEDIA_PRAVA
            return None if ma(request.user, PRISTUP) and ma(request.user, pravo_souboru(request.path[len("/media/"):])) else HttpResponseForbidden("Nemáte přístup.")
        req = potrebna_prava(m.view_name, kwargs, request.GET)  # view_name = url_name, u modulů „modul:název“
        if req is None or smi_stranku(request.user, m.view_name, kwargs, request.GET): return None
        if not ma(request.user, PRISTUP):
            return render(request, "core/bez_pristupu.html", status=403)
        text = f"Na tuto akci nemáte oprávnění (potřebné oprávnění: {popis_chybejiciho(request.user, req)}). Požádejte administrátora o přidělení role."
        if request.headers.get("HX-Request") or m.url_name in ("lookup", "lookup_new", "nabidka_nahled", "dokument_obsah"):
            return JsonResponse({"chyba": text}, status=403) if m.url_name.startswith("lookup") else HttpResponseForbidden(text)
        messages.error(request, text)
        return redirect("dashboard")


def kontext(request):
    """Šablony: {% if "faktury.spravovat" in prava %} a {% if finance %}."""
    u = getattr(request, "user", None)
    return {"prava": prava(u) if u else frozenset(), "finance": finance(u) if u else False}
