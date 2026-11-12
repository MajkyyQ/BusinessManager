from django import forms
from django.apps import apps
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q, ProtectedError
from django.forms import modelform_factory
from django.http import Http404
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
import operator
from functools import reduce
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.db.models import OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils.text import capfirst
from django.http import JsonResponse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.dateparse import parse_datetime
from django.db.models import Count, Prefetch
from urllib.parse import urlencode
from django.db import transaction
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST
from django.urls import reverse
from .models import (Zarizeni, KontaktniOsoba, Material, ZakaznikKontakt, ZakazkaKontakt, StavZakazky, TypUkonu, SazbaDPH, Fotografie, ProvedenyUkon, PouzityMaterial,
                     KalendarUdalost, Zamestnanec, Objednavka, Zakaznik, PolozkaNabidky, HistorieZmen, Zakazka, Nabidka, Faktura, NastaveniFirmy, Platba, PolozkaFaktury,
                     Dodavatel, PrijataFaktura, Priloha, CiselnaRada, Role, Opravneni)
from . import cislovani
from .historie import hodnota_text
from .models import formatuj_telefon, TEL_PRIKLAD
from .navigace import zpet as zpet_url
from . import prava as P

MODELS = {m._meta.model_name: m for m in apps.get_app_config("core").get_models()}
READONLY = {"historiezmen", "opravneni"}  # oprávnění určuje aplikace (core/prava.py), měnit se dají jen jejich přiřazení rolím
SECT = [("plocha", "🖥 Pracovní plocha", "dashboard", []), ("zakazky", "📋 Zakázky", "list", ["zakazka"]), ("zakaznici", "👥 Zákazníci", "list", ["zakaznik"]),
        ("zarizeni", "🔧 Zařízení", "zarizeni_prehled", []),
        ("dokumenty", "📄 Dokumenty", "dokumenty", []), ("kalendar", "📅 Kalendář", "kalendar", []), ("nastaveni", "⚙ Nastavení", "nastaveni", [])]
SEC = {}   # slug modelu -> (sekce aplikace, skupina nastavení); tabulka NENÍ položka menu, jen se zobrazí v kontextu sekce
for _s in ("zakazka", "zakazkakontakt", "provedenyukon", "pouzitymaterial", "fotografie", "priloha"): SEC[_s] = ("zakazky", None)
for _s in ("zakaznik", "kontaktniosoba", "zakaznikkontakt"): SEC[_s] = ("zakaznici", None)
SEC["zarizeni"] = ("zarizeni", None)
for _s in ("nabidka", "polozkanabidky", "objednavka", "faktura", "polozkafaktury", "platba", "prijatafaktura"): SEC[_s] = ("dokumenty", None)
SEC["kalendarudalost"] = ("kalendar", None)
for _s, _g in (("nastavenifirmy", "Firma"), ("sazbadph", "DPH"), ("zamestnanec", "Uživatelé a oprávnění"), ("role", "Uživatelé a oprávnění"),
               ("opravneni", "Uživatelé a oprávnění"), ("stavzakazky", "Katalogy"), ("typukonu", "Katalogy"), ("material", "Katalogy"), ("dodavatel", "Katalogy"), ("historiezmen", "Systém")): SEC[_s] = ("nastaveni", _g)
SEC["ciselnarada"] = ("nastaveni", "Dokumenty")
SEC["sablonadokumentu"] = ("dokumenty", None)  # šablony smí upravovat každý uživatel, nejsou součástí Nastavení

def je_admin(user): return P.ma(user, P.NASTAVENI)
def jen_admin_ok(request, slug=None):
    """Nastavení (údaje firmy, DPH, uživatelé, katalogy, systém) smí otevřít jen ten, kdo má oprávnění Nastavení (hlídá i core.prava.PravaMiddleware)."""
    if slug is not None and SEC.get(slug, (None,))[0] != "nastaveni": return True
    if je_admin(request.user): return True
    messages.error(request, "Nastavení může otevřít jen administrátor."); return False

def safe_next(request):
    n = request.GET.get("next", "")
    return n if n.startswith("/") and not n.startswith("//") else None
def get(slug):
    if slug not in MODELS: raise Http404
    return MODELS[slug]
def R(request, tpl, sec=None, crumbs=None, **c):
    if "M" in c: c["vn"], c["vnp"] = c["M"]._meta.verbose_name, c["M"]._meta.verbose_name_plural
    skryt = set() if je_admin(request.user) else {"nastaveni"}  # menu jen se sekcemi, na které má uživatel oprávnění
    if not P.finance(request.user): skryt.add("dokumenty")
    sect = [x for x in SECT if x[0] not in skryt]
    nav = [(k, l, reverse(u, args=a)) for k, l, u, a in sect]; sl = {k: (l, reverse(u, args=a)) for k, l, u, a in SECT}; g = None; slug = c.get("slug")
    if slug in SEC and not sec: sec, g = SEC[slug]
    if crumbs is None and slug in SEC:
        crumbs = [(sl[sec][0], sl[sec][1])] + ([(g, reverse("nastaveni"))] if g else []) + [(c["vnp"], None if tpl == "list" or slug in SKRYTE_SEZNAMY else reverse("list", args=[slug]))]
        if not g and sl[sec][0].split(" ", 1)[-1] == c["vnp"]:  # sekce a tabulka se jmenují stejně (Zakázky › Zakázky) -> bez duplicity
            crumbs = None if tpl == "list" else crumbs[:1]
    navx = [(k, *(l.split(" ", 1) if " " in l else ("", l)), u) for k, l, u in nav]  # (klíč, ikona, název, url) pro levou lištu
    if "zpet" not in c: c["zpet"] = zpet_url(request)  # tlačítko Zpět = stránka, ze které uživatel přišel
    c.setdefault("zrusit_url", safe_next(request) or c["zpet"])  # Zrušit ve formuláři = zpět tam, odkud se formulář otevřel
    return render(request, f"core/{tpl}.html", {"nav": nav, "navx": navx, "sec": sec, "crumbs": crumbs, **c})

# ---------- Vyhledávací pole s inline vytvářením (místo <select>) ----------
LOOKUP = {  # slug -> pole pro hledání, závislost (filtr podle zákazníka), pole formuláře "Nový ..."
    "zakaznik": dict(f=["jmeno", "firma", "telefon", "email", "ico"], dep=None, new=["typ_zakaznika", "jmeno", "firma", "telefon", "email", "adresa", "ico", "dic"]),
    "zarizeni": dict(f=["vyrobce", "typ", "seriove_cislo", "popis", "zakaznik__firma", "zakaznik__jmeno"], dep="zakaznik", new=["vyrobce", "typ", "seriove_cislo", "popis"]),
    "material": dict(f=["nazev"], dep=None, new=["nazev", "jednotka", "posledni_cena"]),
    "kontaktniosoba": dict(f=["jmeno", "telefon", "email"], dep="zakaznik", new=["jmeno", "telefon", "email", "poznamka"]),
    "dodavatel": dict(f=["nazev", "ico", "email"], dep=None, new=["nazev", "ico", "dic", "adresa", "telefon", "email", "cislo_uctu"]),
}
NOVY_V_OKNE = {  # záznamy, které jde založit v okně přímo z jiného formuláře, i když se nevybírají vyhledávacím polem (role v kartě zaměstnance)
    "role": dict(new=["nazev", "popis", "opravneni", "je_administrator"]),
}
def lk_item(slug, o):
    if slug == "role": return dict(id=o.pk, label=o.nazev, sub="")
    if slug == "zarizeni": return dict(id=o.pk, label=f"{o.vyrobce} {o.typ}".strip() or "Zařízení", sub=f"S/N: {o.seriove_cislo or '–'} · {o.zakaznik} · zakázek: {getattr(o, 'n', 0)}")
    if slug == "material": return dict(id=o.pk, label=o.nazev, sub=f"{o.jednotka} · {o.posledni_cena if o.posledni_cena is not None else '–'} Kč", price=None if o.posledni_cena is None else str(o.posledni_cena))
    return dict(id=o.pk, label=str(o), sub=" · ".join(x for x in (formatuj_telefon(o.telefon), o.email, getattr(o, "adresa", "")) if x))

class LookupWidget(forms.Widget):
    def __init__(self, slug, model, multi=False, dep=""):
        super().__init__(); self.slug, self.model, self.multi, self.dep = slug, model, multi, dep
    def value_from_datadict(self, data, files, name): return data.getlist(name) if self.multi else (data.get(name) or None)
    def render(self, name, value, attrs=None, renderer=None):
        ids = [str(i) for i in (value if isinstance(value, (list, tuple)) else [value]) if i not in (None, "")]
        objs = {str(o.pk): o for o in self.model.objects.filter(pk__in=[i for i in ids if i.isdigit()])}
        lab = lambda o: lk_item(self.slug, o)["label"]
        chips = "".join(f'<span class="badge bg-secondary me-1 lk-chip">{escape(lab(o))} <a href="#" class="lk-x text-white text-decoration-none">×</a><input type="hidden" name="{name}" value="{i}"></span>' for i, o in objs.items()) if self.multi else ""
        o1 = next(iter(objs.values()), None)
        hid = "" if self.multi else f'<input type="hidden" name="{name}" value="{o1.pk if o1 else ""}" class="lk-v">'
        txt = escape(lab(o1)) if (o1 and not self.multi) else ""
        return mark_safe(f'<div class="lk position-relative" data-slug="{self.slug}" data-name="{name}" data-multi="{int(self.multi)}" data-dep="{self.dep}" data-url="{reverse("lookup", args=[self.slug])}" data-new="{reverse("lookup_new", args=[self.slug])}">'
            f'<div>{chips}</div>{hid}<div class="d-flex gap-1"><input type="text" class="form-control lk-q" autocomplete="off" placeholder="Začněte psát…" value="{txt}"><button type="button" class="btn btn-outline-primary lk-new text-nowrap">+ Nový</button></div>'
            f'<div class="lk-dd list-group position-absolute w-100 shadow d-none" style="z-index:1050;max-height:260px;overflow:auto"></div></div>')

def lookup(request, slug):
    c = LOOKUP.get(slug)
    if not c: raise Http404
    M = MODELS[slug]; qs = M.objects.all(); q = request.GET.get("q", "").strip(); dep = request.GET.get("dep", "")
    if "aktivni" in [f.name for f in M._meta.fields]: qs = qs.filter(aktivni=True)
    for w in q.split(): qs = qs.filter(reduce(operator.or_, [Q(**{f + "__icontains": w}) for f in c["f"]]))
    if dep.isdigit() and not (slug == "kontaktniosoba" and q): qs = qs.filter(zakaznik_id=dep) if slug == "zarizeni" else qs.filter(zakaznikkontakt__zakaznik_id=dep) if slug == "kontaktniosoba" else qs
    if slug == "zarizeni": qs = qs.select_related("zakaznik").annotate(n=Count("zakazka"))
    return JsonResponse([lk_item(slug, o) for o in qs.distinct()[:12]], safe=False)

class VolbySNovym(forms.CheckboxSelectMultiple):
    """Zaškrtávací políčka (role zaměstnance) s tlačítkem „+ Nová …“: nový záznam se založí v okně a rovnou se zaškrtne, formulář se neopouští."""
    def __init__(self, slug, text, attrs=None):
        super().__init__(attrs); self.slug, self.text = slug, text
    def render(self, name, value, attrs=None, renderer=None):
        return mark_safe(f'<div class="lk-volby" data-name="{name}" data-new="{reverse("lookup_new", args=[self.slug])}">{super().render(name, value, attrs, renderer)}'
                         f'<button type="button" class="btn btn-sm btn-outline-primary lk-new mt-1">{escape(self.text)}</button></div>')

def lookup_new(request, slug):
    c = LOOKUP.get(slug) or NOVY_V_OKNE.get(slug)
    if not c: raise Http404
    M = MODELS[slug]; dep = request.GET.get("dep") or request.POST.get("dep") or ""
    form = modelform_factory(M, form=ZakaznikForm if slug == "zakaznik" else BaseForm, fields=c["new"], formfield_callback=cb)(request.POST or None)
    ctx = {"form": form, "slug": slug, "dep": dep, "title": nadpis_novy(slug, M)}
    if request.method == "POST":
        if slug == "zarizeni" and not dep.isdigit(): form.add_error(None, "Nejdřív vyberte zákazníka.")
        elif form.is_valid():
            cd = form.cleaned_data; dup = None
            if slug == "zarizeni" and cd["seriove_cislo"]:
                jiny = zarizeni_stejne(cd["vyrobce"], cd["seriove_cislo"])
                if jiny and jiny.zakaznik_id == int(dep): dup = jiny
                elif jiny:  # stejné zařízení teď přinesl jiný zákazník -> zařízení přejde k němu (nikdy nepatří dvěma zákazníkům najednou)
                    z_otevrena = otevrena_zakazka(jiny)
                    if z_otevrena: form.add_error(None, f"Zařízení {jiny} je právě na firmě v zakázce {z_otevrena.cislo_zakazky} zákazníka {jiny.zakaznik}. Jedno zařízení nemůže mít dva zákazníci najednou.")
                    else:
                        stary = jiny.zakaznik; jiny.zakaznik_id = int(dep); jiny.save(update_fields=["zakaznik"]); jiny.refresh_from_db()
                        log(request, jiny, "Změna vlastníka", "zakaznik", stary, jiny.zakaznik)
                        it = lk_item(slug, jiny); it["sub"] = f"Převedeno od zákazníka {stary} · " + it["sub"]; return JsonResponse(it)
            elif slug == "material": dup = Material.objects.filter(nazev__iexact=cd["nazev"]).first()
            elif slug == "dodavatel" and cd["ico"]: dup = Dodavatel.objects.filter(ico=cd["ico"]).first()
            elif slug == "role": dup = Role.objects.filter(nazev__iexact=cd["nazev"].strip()).first()
            elif slug == "zakaznik":
                if not (cd["jmeno"] or cd["firma"]): form.add_error(None, "Vyplňte jméno nebo firmu.")
                elif cd["ico"]: dup = Zakaznik.objects.filter(ico=cd["ico"]).first()
            if dup: form.add_error(None, f"Takový záznam už existuje ({dup}) – vyberte ho ze seznamu, nevytváří se duplicita.")
            if not form.errors:
                o = form.save(commit=False)
                if slug == "zarizeni": o.zakaznik_id = dep
                o.save(); form.save_m2m(); log(request, o, "Vytvoření")
                if slug == "kontaktniosoba" and dep.isdigit(): ZakaznikKontakt.objects.create(zakaznik_id=dep, kontakt=o)
                return JsonResponse(lk_item(slug, o))
        return render(request, "core/lookup_form.html", ctx, status=400)
    return render(request, "core/lookup_form.html", ctx)

POPISKY = {"jmeno": "Jméno", "typ_zakaznika": "Typ zákazníka", "nazev": "Název", "zakazka": "Zakázka", "zakazky": "Zakázky", "zakaznik": "Zákazník",
           "zamestnanci": "Zaměstnanci", "vytvoril": "Vytvořil", "nahral": "Nahrál", "vystavil": "Vystavil", "vypracoval": "Vypracoval", "poznamka": "Poznámka",
           "zarizeni": "Zařízení", "vyrobce": "Výrobce", "seriove_cislo": "Sériové číslo", "posledni_cena": "Poslední cena", "cislo_uctu": "Číslo účtu",
           "datum_vytvoreni": "Datum vytvoření", "priloha": "Příloha", "stredisko": "Středisko",
           "prijmeni": "Příjmení", "pracovni_pozice": "Pracovní pozice", "poradi": "Pořadí", "kod": "Kód", "je_administrator": "Je administrátor",
           "opravneni": "Oprávnění", "material": "Materiál", "typ_ukonu": "Typ úkonu", "mnozstvi": "Množství", "jednotkova_cena": "Jednotková cena",
           "zakaznik_kontakt": "Kontakt", "datum_prijeti": "Datum přijetí", "popis_zavady": "Popis závady",
           # české popisky s diakritikou pro pole, která nemají verbose_name
           "castka": "Částka", "zpusob": "Způsob platby", "datum_zaplaceni": "Datum zaplacení", "datum_splatnosti": "Datum splatnosti", "cena": "Cena bez DPH",
           "cena_bez_dph": "Cena bez DPH", "cena_s_dph": "Cena s DPH", "dph": "DPH", "sazba": "Sazba DPH", "sazba_dph": "Sazba DPH", "vychozi_dph": "Výchozí sazba DPH",
           "cislo_faktury": "Číslo faktury", "cislo_nabidky": "Číslo nabídky", "cislo_objednavky": "Číslo objednávky", "cislo_zakazky": "Číslo zakázky",
           "datum": "Datum", "datum_vydani": "Datum vydání", "datum_vystaveni": "Datum vystavení", "datum_zdanitelneho_plneni": "Datum zdanitelného plnění",
           "datum_nahrani": "Datum nahrání", "datum_pridani": "Datum přidání", "datum_upravy": "Datum úpravy", "email": "E-mail", "telefon": "Telefon",
           "adresa": "Adresa", "firma": "Název firmy", "faktura": "Faktura", "nabidka": "Nabídka", "platba": "Platba", "dodavatel": "Dodavatel", "kontakt": "Kontakt",
           "role": "Role", "stav": "Stav", "typ": "Typ", "popis": "Popis", "jednotka": "Jednotka", "soubor": "Soubor", "logo": "Logo", "mena": "Měna",
           "nazev_firmy": "Název firmy", "web": "Web", "identifikacni_cislo": "Identifikační číslo", "sekundarni_cislo": "Sekundární číslo", "uzivatel": "Uživatel",
           "typ_dokumentu": "Typ dokumentu", "format": "Formát"}
def vychozi_dph():
    ns = NastaveniFirmy.objects.first()
    return ns.vychozi_dph if ns and ns.vychozi_dph is not None else Decimal(21)
def _dph_text(x): return f"{x:.2f}".rstrip("0").rstrip(".")
class SazbaDPHWidget(forms.Widget):
    """Sazba DPH: výběr ze sazeb v Nastavení → DPH, nebo „Jiná sazba…“ a vlastní číslo."""
    def value_from_datadict(self, data, files, name):
        v = data.get(name, "")
        return data.get(name + "_jina", "").strip().replace(",", ".") if v == "jina" else v
    def render(self, name, value, attrs=None, renderer=None):
        sazby = [_dph_text(x) for x in SazbaDPH.objects.filter(aktivni=True).order_by("-sazba").values_list("sazba", flat=True)]
        v = "" if value in (None, "") else _dph_text(Decimal(str(value).replace(",", "."))) if _dec(value) is not None else str(value)
        jina = bool(v) and v not in sazby; i = (attrs or {}).get("id", "id_" + name)
        opt = '<option value="">—</option>' + "".join(f'<option value="{x}"{" selected" if x == v else ""}>{x} %</option>' for x in sazby)
        opt += f'<option value="jina"{" selected" if jina else ""}>Jiná sazba…</option>'
        return mark_safe(f'<div class="d-flex gap-1"><select name="{name}" id="{i}" class="form-select" onchange="var j=this.nextElementSibling;j.classList.toggle(\'d-none\',this.value!=\'jina\');if(this.value==\'jina\')j.focus()">{opt}</select>'
                         f'<input type="number" step="0.01" min="0" max="100" name="{name}_jina" class="form-control{"" if jina else " d-none"}" placeholder="vlastní sazba v %" value="{escape(v) if jina else ""}"></div>')
AUTO_UZIVATEL = ("nahral", "vytvoril", "vystavil", "vypracoval")  # kdo záznam vytvořil = vždy přihlášený uživatel, ve formuláři se nevybírá
class BaseForm(forms.ModelForm):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for n, f in self.fields.items():
            t = getattr(getattr(f, "queryset", None), "model", None); s = t and t._meta.model_name
            if n in POPISKY and f.label == n.replace("_", " ").capitalize(): f.label = POPISKY[n]  # pole bez verbose_name -> čeština s diakritikou
            if s in LOOKUP:
                d = LOOKUP[s]["dep"]; f.widget = LookupWidget(s, t, isinstance(f, forms.ModelMultipleChoiceField), d if d in self.fields else ""); continue
            if s == "zamestnanec" and isinstance(f, forms.ModelMultipleChoiceField):  # víc zaměstnanců najednou: zaškrtávací políčka místo seznamu s Ctrl
                ted = list(self.instance.zamestnanci.values_list("pk", flat=True)) if self.instance.pk and hasattr(self.instance, "zamestnanci") else []
                f.queryset = Zamestnanec.objects.filter(Q(aktivni=True) | Q(pk__in=ted)).order_by("prijmeni", "jmeno")
                f.widget = forms.CheckboxSelectMultiple(attrs={"class": "bm-volby"}); f.widget.choices = f.choices; continue
            if s in ("opravneni", "role") and isinstance(f, forms.ModelMultipleChoiceField): zaskrtavatka(f, s); continue
            if n == "sazba_dph":
                f.widget = SazbaDPHWidget()
                if not self.instance.pk and not self.initial.get(n): self.initial[n] = vychozi_dph()
                continue
            w = f.widget; c = "form-check-input" if isinstance(w, forms.CheckboxInput) else "form-select" if isinstance(w, forms.Select) else "form-control"
            w.attrs["class"] = c
            if isinstance(w, forms.Textarea): w.attrs["rows"] = 3
            if n == "barva": w.input_type = "color"; w.attrs["class"] = "form-control form-control-color"; w.attrs["title"] = "Vyberte barvu"
            if n == "telefon": w.attrs.setdefault("placeholder", TEL_PRIKLAD)
    def _post_clean(self):
        for n in ("telefon",):  # telefon se ukládá jednotně po trojicích (604 851 237)
            if n in self.cleaned_data: self.cleaned_data[n] = formatuj_telefon(self.cleaned_data[n])
        super()._post_clean()
def zaskrtavatka(f, s):
    """Role a oprávnění jako zaškrtávací políčka s názvem (místo seznamu s Ctrl)."""
    f.queryset = Opravneni.objects.order_by("pk") if s == "opravneni" else Role.objects.filter(aktivni=True).order_by("nazev")
    f.label_from_instance = lambda o: o.nazev or str(o)
    f.widget = forms.CheckboxSelectMultiple(attrs={"class": "bm-volby"}); f.widget.choices = f.choices
    if s == "opravneni": f.help_text = "Co role smí. Popis jednotlivých oprávnění najdete v Nastavení → Oprávnění."
    else: f.help_text = "Co zaměstnanec v aplikaci smí, určují jeho role (Nastavení → Role)."
class ZakazkaChoice(forms.ModelChoiceField):
    def label_from_instance(self, z): return f"{z.cislo_zakazky} – {z.zakaznik}"
class ZakaznikForm(BaseForm):
    """Zákazník: přepínač Soukromá osoba / Firma. U soukromé osoby se firemní údaje (název firmy, IČO, DIČ) skryjí a neukládají."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        f = self.fields.get("typ_zakaznika")
        if f:
            f.choices = [(x, x) for x in ("Soukromá osoba", "Firma")]; f.required = True; f.label = "Zákazník je"
            f.widget = forms.RadioSelect(choices=f.choices, attrs={"class": "bm-volby"})
            if not self.initial.get("typ_zakaznika"): self.initial["typ_zakaznika"] = "Firma" if self.instance.firma or self.instance.ico else "Soukromá osoba"
    def clean(self):
        c = super().clean()
        if c.get("typ_zakaznika") == "Firma":
            if "firma" in self.fields and not c.get("firma"): self.add_error("firma", "Vyplňte název firmy.")
        elif c.get("typ_zakaznika") == "Soukromá osoba":
            for n in ("firma", "ico", "dic"):
                if n in c: c[n] = ""
            if "jmeno" in self.fields and not c.get("jmeno"): self.add_error("jmeno", "Vyplňte jméno a příjmení.")
        return c
def cb(f, **k):
    ff = f.formfield(**k)
    if ff and isinstance(f, models.DateTimeField): ff.widget = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
    elif ff and isinstance(f, models.DateField): ff.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    return ff

def log(request, obj, akce, pole="", old="", new="", popis_z=None):
    HistorieZmen.objects.create(uzivatel=request.user, typ_objektu=obj._meta.model_name, id_objektu=obj.pk, akce=akce,
                                pole=pole, puvodni_hodnota=hodnota_text(old), nova_hodnota=hodnota_text(new), popis=(str(obj) + (f" ze zakázky {popis_z.cislo_zakazky}" if popis_z else ""))[:200])
def val(o, f):
    if f.choices: return o._get_FIELD_display(f) or "–"
    v = getattr(o, f.name)
    if isinstance(o, StavZakazky) and f.name == "barva":  # ukázka barvy místo kódu #RRGGBB
        return mark_safe(f'<span class="badge bg-stav-{o.pk}">{escape(o.nazev)}</span> <small class="text-muted">{escape(v)}</small>')
    return "–" if v in (None, "") else "✓" if v is True else "✗" if v is False else v

# ---------- Společné části seznamů (jednotné rozložení) ----------
def _url(request, **zmena):
    """Aktuální parametry adresy se změnou (prázdná hodnota parametr odebere); stránkování se vždy vrací na začátek."""
    p = request.GET.copy(); p.pop("page", None)
    for k, x in zmena.items():
        if x in ("", None): p.pop(k, None)
        else: p[k] = x
    return "?" + p.urlencode() if p else "?"
def _pohled(request, klic):
    """Přepínač tabulka / kanban (inspirace Odoo). Volba se pamatuje v relaci zvlášť pro každý seznam."""
    v = request.GET.get("v")
    if v in ("tab", "kan"): request.session["pohled_" + klic] = v
    else: v = request.session.get("pohled_" + klic, "tab")
    return v, [("tab", "☰ Tabulka", _url(request, v="tab"), v == "tab"), ("kan", "▦ Kanban", _url(request, v="kan"), v == "kan")]
def _chips(request, param, polozky, aktivni, celkem, vse="Vše"):
    """Rychlý filtr podle stavu s počty: [(popisek, url, počet, aktivní, barva)]."""
    return [(vse, _url(request, **{param: ""}), celkem, not aktivni, "")] + [(l, _url(request, **{param: k}), n, k == aktivni, css) for k, l, n, css in polozky]

def dashboard(request):
    return R(request, "dashboard", groups=[(g, [(s, MODELS[s]._meta.verbose_name_plural, MODELS[s].objects.count()) for s in ss]) for g, ss in GROUPS])

TYP_ZKR = {"Firma": ("F", "Firma"), "Soukromá osoba": ("SO", "Soukromá osoba")}
ZAK_RAZENI = {"cislo": "cislo_zakazky", "prijeti": "datum_prijeti", "vydani": "datum_vydani"}  # sloupce zakázek, podle kterých jde řadit
KANBAN = {"zakazka", "zakaznik"}  # seznamy s přepínačem tabulka / kanban (zařízení má vlastní přehled)
KANBAN_MAX = 300  # kanban zakázek se nestránkuje; při větším počtu stačí zúžit vyhledáním nebo stavem
def _dt(v): return timezone.localtime(v).strftime("%d.%m.%Y %H:%M") if v else "–"
# Pomocné tabulky bez vlastní stránky: jejich záznamy se zobrazují a přidávají u zakázky, dokladu nebo v kalendáři.
SKRYTE_SEZNAMY = {"provedenyukon": "zakazka", "pouzitymaterial": "zakazka", "fotografie": "zakazka", "priloha": "zakazka", "zakazkakontakt": "zakazka",
                  "zakaznikkontakt": "zakaznik", "kalendarudalost": None, "polozkanabidky": "nabidka", "polozkafaktury": "faktura"}
def _mimo_seznam(request, slug):
    """Kam vede Zpět z pomocného záznamu, když uživatel nepřišel odjinud: na jeho zakázku, doklad nebo do kalendáře."""
    return zpet_url(request) or (reverse("kalendar") if slug == "kalendarudalost" else reverse("list", args=[SKRYTE_SEZNAMY.get(slug) or "zakazka"]))
def lst(request, slug):
    if not jen_admin_ok(request, slug): return redirect("dashboard")
    if slug in SKRYTE_SEZNAMY: return redirect(_mimo_seznam(request, slug))
    M = get(slug); q = request.GET.get("q", ""); qs = M.objects.all(); flt = {}; o = ""
    if q:
        f = Q()
        for x in M._meta.fields:
            if isinstance(x, (models.CharField, models.TextField)): f |= Q(**{x.name + "__icontains": q})
        if slug == "zakazka": f |= Q(zakaznik__firma__icontains=q) | Q(zakaznik__jmeno__icontains=q)
        qs = qs.filter(f)
    chips = None; pohled, pohledy = _pohled(request, slug) if slug in KANBAN else ("tab", None); sloupce = None
    if slug == "zakazka":
        st = request.GET.get("st", "")
        stavy = list(StavZakazky.objects.filter(aktivni=True).order_by("poradi", "nazev").values_list("nazev", flat=True))
        cnt = dict(qs.order_by().values("stav__nazev").annotate(n=Count("pk")).values_list("stav__nazev", "n"))
        css = stav_css(); chips = _chips(request, "st", [(s, s, cnt.get(s, 0), css.get(s, "light")) for s in stavy], st, sum(cnt.values()))
        if st: flt["st"] = st; qs = qs.filter(stav__nazev=st)
        o = request.GET.get("o", "-cislo"); key = o.lstrip("-") if o.lstrip("-") in ZAK_RAZENI else "cislo"; desc = o.startswith("-"); o = ("-" if desc else "") + key
        pole = models.F(ZAK_RAZENI[key]); qs = qs.select_related("zakaznik", "stav").order_by(pole.desc(nulls_last=True) if desc else pole.asc(nulls_last=True), "-pk")
    if slug == "zakaznik":
        h = HistorieZmen.objects.filter(typ_objektu="zakaznik", id_objektu=OuterRef("pk")).order_by("-datum").values("datum")[:1]
        qs = qs.annotate(posl=Coalesce(Subquery(h), "datum_vytvoreni"))
        if pohled == "kan":
            nzar = Zarizeni.objects.filter(zakaznik=OuterRef("pk")).order_by().values("zakaznik").annotate(n=Count("pk")).values("n")
            nzak = Zakazka.objects.filter(zakaznik=OuterRef("pk")).order_by().values("zakaznik").annotate(n=Count("pk")).values("n")
            qs = qs.annotate(n_zar=Coalesce(Subquery(nzar), 0), n_zak=Coalesce(Subquery(nzak), 0))
    if slug == "zakazka" and pohled == "kan":  # kanban zakázek: sloupec = stav, karty bez stránkování
        zz = list(qs.prefetch_related("zarizeni")[:KANBAN_MAX]); sl = [st] if st else stavy
        # uzavřené stavy (Vydáno, Zrušeno) jsou ve výchozím kanbanu sbalené jen na počet; rozbalí se kliknutím na stav
        sloupce = [dict(s=s, css=css.get(s, "light"), items=[z for z in zz if z.stav and z.stav.nazev == s], sbaleno=not st and s in CLOSED, url=_url(request, st=s)) for s in sl]
        if not st and any(not z.stav for z in zz): sloupce.append(dict(s="Bez stavu", css="light", items=[z for z in zz if not z.stav], sbaleno=False, url=""))
    if slug == "platba": qs = qs.select_related("faktura", "zakazka").order_by("-pk")
    if slug == "opravneni": qs = qs.prefetch_related("role_set").order_by("pk")
    page = Paginator(qs if qs.ordered else qs.order_by("pk"), 50).get_page(request.GET.get("page"))
    if slug == "zakaznik":
        heads = [dict(l=x) for x in ["Jméno", "Firma", "Adresa", "Telefon", "E-mail", "Poslední změna"]]
        rows = [(o, [o.jmeno or o.firma or str(o), o.firma or "–", o.adresa or "–", formatuj_telefon(o.telefon) or "–", o.email or "–", _dt(o.posl)], TYP_ZKR.get(o.typ_zakaznika)) for o in page]
    elif slug == "platba":
        heads = [dict(l=x) for x in ["Stav platby", "Faktura", "Zakázka", "Částka", "Způsob platby", "Datum splatnosti", "Datum zaplacení"]]
        d = lambda x: x.strftime("%d.%m.%Y") if x else "–"
        rows = [(o, [o.stav or "–", o.faktura or "bez faktury", o.zakazka or "–", o.castka if o.castka is not None else "–", o.zpusob or "–",
                     d(o.faktura.datum_splatnosti) if o.faktura else "–", _dt(o.datum_zaplaceni) if o.stav == "Zaplaceno" else "–"], None) for o in page]
    elif slug == "prijatafaktura":
        heads = [dict(l=x) for x in ["Číslo faktury", "Dodavatel", "Doručeno", "Splatnost", "K úhradě", "Stav"]]
        rows = [(o, [o.cislo_faktury, o.dodavatel, o.datum_doruceni.strftime("%d.%m.%Y"), o.datum_splatnosti.strftime("%d.%m.%Y") if o.datum_splatnosti else "–",
                     f"{o.cena_s_dph} {o.mena}" if o.cena_s_dph is not None else "–", "Po splatnosti" if o.po_splatnosti else o.stav], None) for o in page]
    elif slug == "opravneni":
        heads = [dict(l=x, w=w) for x, w in (("Oprávnění", 20), ("Popis", 45), ("Role", 20), ("Kód", 15))]
        rows = [(o, [o.nazev or o.kod, o.popis or "–", ", ".join(r.nazev for r in o.role_set.all() if r.aktivni) or "–", o.kod], None) for o in page]
    elif slug == "zakazka":
        sk = {"Číslo zakázky": "cislo", "Datum přijetí": "prijeti", "Datum vydání": "vydani"}
        sirka = {"Číslo zakázky": 13, "Zákazník": 23, "Stav": 18, "Datum přijetí": 15, "Datum vydání": 15, "Identifikační číslo": 16}  # pevné šířky: tabulka se po filtru nepřeskupí
        heads = [dict(l=x, w=sirka[x], ord=sk.get(x) and ("" if desc or sk[x] != key else "-") + sk[x], ar=(("▼" if desc else "▲") if sk.get(x) == key else ("↕" if x in sk else "")))
                 for x in sirka]
        rows = [(o, [o.cislo_zakazky, o.zakaznik, mark_safe(f'<span class="badge bg-stav-{o.stav_id}">{escape(o.stav)}</span>') if o.stav else "–", _dt(o.datum_prijeti), _dt(o.datum_vydani), o.identifikacni_cislo or "–"], None) for o in page]
    else:
        cols = [x for x in M._meta.fields if x.name != "id" and not isinstance(x, models.TextField) and not isinstance(x, models.FileField)][:6]
        heads = [dict(l=capfirst(c.verbose_name)) for c in cols]; rows = [(o, [val(o, c) for c in cols], None) for o in page]
    keep = urlencode({k: x for k, x in {"q": q, **flt}.items() if x})
    return R(request, "list", slug=slug, M=M, q=q, page=page, heads=heads, rows=rows, ro=slug in READONLY, bez_noveho=slug == "platba" or slug in BEZ_PRIDANI, flt=flt, keep=keep, o=o,
             keep_o=urlencode({k: x for k, x in {"q": q, **flt, "o": o}.items() if x}), chips=chips, pohled=pohled, pohledy=pohledy, sloupce=sloupce,
             kanban_max=KANBAN_MAX, ph={"zakazka": "Číslo zakázky, zákazník, závada…", "zakaznik": "Jméno, firma, telefon, e-mail…"}.get(slug, "Hledat…"))

def detail(request, slug, pk):
    if slug == "zakazka": return plocha(request, pk)       # detail zakázky = pracovní prostor zakázky
    if slug == "zakaznik": return zakaznik_detail(request, pk)
    if slug == "zarizeni": return zarizeni_detail(request, pk)
    M = get(slug); o = get_object_or_404(M, pk=pk); fields = []
    for f in M._meta.fields:
        v = val(o, f)
        if isinstance(f, models.FileField) and getattr(o, f.name): fields.append((f.verbose_name, getattr(o, f.name).name, getattr(o, f.name).url, isinstance(f, models.ImageField)))
        elif f.name != "id": fields.append((f.verbose_name, v, None, False))
    for f in M._meta.many_to_many: fields.append((f.verbose_name, ", ".join(map(str, getattr(o, f.name).all())) or "–", None, False))
    rel = []
    for r in M._meta.related_objects:
        s = r.related_model._meta.model_name
        if s in MODELS and s not in DETAIL_BEZ and (r.one_to_many or r.many_to_many):
            rel.append((DETAIL_NAZEV.get(s, r.related_model._meta.verbose_name_plural), s, list(getattr(o, r.get_accessor_name()).all()[:50]),
                        r.field.name if r.one_to_many and s not in BEZ_PRIDANI else None))
    hist = HistorieZmen.objects.filter(typ_objektu=slug, id_objektu=pk)[:30]
    z = getattr(o, "zakazka", None) if slug in SKRYTE_SEZNAMY else None  # práce, materiál, foto… patří k zakázce
    nahradni = reverse("detail", args=["zakazka", z.pk]) if isinstance(z, Zakazka) else _mimo_seznam(request, slug) if slug in SKRYTE_SEZNAMY else reverse("list", args=[slug])
    zaplaceno = o.platba_set.filter(stav="Zaplaceno").order_by("-datum_zaplaceni").first() if slug == "faktura" else None
    return R(request, "detail", slug=slug, M=M, o=o, fields=fields, rel=rel, hist=hist, ro=slug in READONLY, nahradni=nahradni, zaplaceno=zaplaceno)
VICE = {"provedenyukon", "pouzitymaterial"}  # při přidání jde tlačítkem Přidat vyplnit víc položek najednou
DETAIL_BEZ = {"kalendarudalost", "platba"}  # události jsou v Kalendáři; platba faktury se řídí tlačítkem Zaplaceno, platby zakázky jsou na její stránce
BEZ_PRIDANI = {"polozkafaktury": "faktura", "polozkanabidky": "nabidka"}  # položky dokladů vznikají jen při vystavení ze zakázky, ručně se nepřidávají
DETAIL_NAZEV = {"polozkafaktury": "Položky faktury", "polozkanabidky": "Položky nabídky"}

def edit(request, slug, pk=None):
    if not jen_admin_ok(request, slug): return redirect("dashboard")
    M = get(slug)
    if slug in READONLY: raise Http404
    if slug == "nabidka" and not pk:  # nabídka se vždy zakládá ze zakázky
        q = {"zakazka": request.GET.get("zakazky") or request.GET.get("zakazka") or "", "next": request.GET.get("next", "")}
        return redirect(reverse("nabidka_nova") + "?" + urlencode({k: x for k, x in q.items() if x}))
    if slug in ("faktura", "objednavka") and not pk:  # faktura i objednávka se vždy zakládají ze zakázky (starý obecný formulář se už nepoužívá)
        q = {"zakazka": request.GET.get("zakazky") or request.GET.get("zakazka") or "", "next": request.GET.get("next", "")}
        return redirect(reverse(f"{slug}_nova") + "?" + urlencode({k: x for k, x in q.items() if x}))
    if slug in BEZ_PRIDANI and not pk:  # formulář na novou položku faktury/nabídky neexistuje, vrátí se na doklad
        d = BEZ_PRIDANI[slug]; dpk = request.GET.get(d, "")
        return redirect(reverse("detail", args=[d, int(dpk)]) if dpk.isdigit() else reverse("list", args=[d]))
    if slug == "prijatafaktura" and not pk:  # přijatá faktura ručně má vlastní přehledný formulář
        return redirect(reverse("prijata_faktura_rucne") + ("?" + request.GET.urlencode() if request.GET else ""))
    if slug == "zakazka" and not pk:  # nová zakázka = zakázkový list
        return redirect(reverse("zakazka_nova") + ("?" + request.GET.urlencode() if request.GET else ""))
    if slug == "fotografie" and not pk: return fotografie_nove(request)  # víc fotek najednou
    o = get_object_or_404(M, pk=pk) if pk else None
    zak = None  # nové zařízení vzniká jen ze zakázky (přijetí zařízení), ne samostatně
    if slug == "zarizeni" and not o:
        zak = Zakazka.objects.filter(pk=request.GET.get("zakazka") or 0).select_related("zakaznik").first()
        if not zak:
            messages.info(request, "Nové zařízení se zakládá s novou zakázkou (zařízení se eviduje, když ho zákazník přinese)."); return redirect("zakazka_nova")
    if slug == "platba" and not o:  # ručně se zapisuje jen platba k zakázce bez faktury (např. hotově); platbu faktury řeší tlačítko Zaplaceno u faktury
        zak = Zakazka.objects.filter(pk=request.GET.get("zakazka") or 0).first()
        if not zak: messages.info(request, "Platba se zapisuje u zakázky (Dokumenty zakázky → Přidat platbu). Platbu faktury označíte tlačítkem Zaplaceno v detailu faktury."); return redirect(zpet_url(request) or "dokumenty")
    exclude = {"zakazka": ["stav", "datum_vydani"], "zamestnanec": ["uzivatel"], "priloha": ["typ_souboru"], "zarizeni": [] if o else ["zakaznik"],
               "platba": ["faktura"] + ([] if o else ["stav"])}.get(slug, [])  # stav se mění jen akcemi workflow, účet zaměstnance má vlastní sekci, typ souboru se pozná z přípony
    exclude += [n for n in AUTO_UZIVATEL if n in {f.name for f in M._meta.fields}]  # kdo záznam vytvořil, se doplní sám
    if any(f.name == "aktivni" for f in M._meta.fields) and (not o or (not P.ma(request.user, P.MAZAT) and slug not in P.T_NASTAVENI)):
        exclude.append("aktivni")  # nový záznam je vždy aktivní; deaktivovat smí jen ten, kdo má oprávnění Mazání a deaktivace
    Form = modelform_factory(M, form=ZamestnanecForm if slug == "zamestnanec" else ZakaznikForm if slug == "zakaznik" else BaseForm, fields="__all__", formfield_callback=cb, exclude=exclude)
    init = {} if o else request.GET.dict()
    if slug == "stavzakazky" and not o: init.setdefault("poradi", StavZakazky.dalsi_poradi())  # nový stav jako další v řadě (lze přepsat)
    if slug == "platba" and not o: init.update(zakazka=zak.pk, zpusob=init.get("zpusob", "Hotově"), datum_zaplaceni=timezone.localtime().strftime("%Y-%m-%dT%H:%M"))
    form = Form(request.POST or None, request.FILES or None, instance=o, initial=init or None)
    dalsi = None  # další práce / materiál vyplněné ve stejném formuláři (tlačítko Přidat), každá kopie má vlastní prefix d<číslo>
    if slug in VICE and not o:
        cisla = [n for n in dict.fromkeys(request.POST.getlist("dalsi")) if n.isdigit()][:50]
        data = request.POST.copy() if request.method == "POST" else None
        init_d = dict(init, zakazka=data.get("zakazka", "") if data else init.get("zakazka", ""))  # zakázka je pro všechny kopie stejná jako v prvním formuláři
        for n in cisla: data[f"d{n}-zakazka"] = init_d["zakazka"]
        dalsi = [(n, Form(data, prefix=f"d{n}", initial=init_d, empty_permitted=True, use_required_attribute=False)) for n in cisla]
        prazdny = Form(prefix="d__N__", initial=init_d, use_required_attribute=False)
    if slug == "platba" and "zakazka" in form.fields and (zak or (o and o.faktura_id)): form.fields["zakazka"].disabled = True  # zakázka (a faktura) se ve formuláři nemění
    if slug == "zamestnanec": form.prihlaseny = request.user
    nx = safe_next(request); zpet = zpet_url(request)
    dalsi_ok = all([f.is_valid() for _, f in dalsi or []])  # seznam, ať se zkontrolují (a ukážou chyby) všechny kopie
    if request.method == "POST" and form.is_valid() and _kontrola(request, slug, form, o, zak) and dalsi_ok:
        changed = [n for n in (form.changed_data if o else []) if n not in getattr(form, "UCET", ())]  # údaje účtu (heslo!) se do historie nepíší
        old = {n: form.initial.get(n) for n in changed}
        with transaction.atomic():
            o = form.save(commit=False)
            if not pk:
                for n in AUTO_UZIVATEL:
                    if hasattr(o, n + "_id"): setattr(o, n, request.user)
                if zak and slug == "zarizeni": o.zakaznik = zak.zakaznik
                if slug == "platba": o.stav = "Zaplaceno"; o.zakazka = zak; o.datum_zaplaceni = o.datum_zaplaceni or timezone.now()
            o.save(); form.save_m2m()
            if zak and slug == "zarizeni": zak.zarizeni.add(o)
            ulozene = []
            for _, f in dalsi or []:
                if not f.has_changed(): continue  # přidaná, ale nevyplněná kopie se přeskočí
                d = f.save(commit=False)
                for n in AUTO_UZIVATEL:
                    if hasattr(d, n + "_id"): setattr(d, n, request.user)
                d.save(); f.save_m2m(); ulozene.append(d)
            if slug == "provedenyukon" and not pk: prace_pridana(request, o.zakazka)
            if slug == "zamestnanec" and not pk and not o.role.exists():  # nový zaměstnanec bez vybrané role dostane základní přístup
                o.role.add(*Role.objects.filter(nazev=P.VYCHOZI_ROLE)[:1])
            if hasattr(form, "uloz_ucet"):
                zprava = form.uloz_ucet(o)
                if zprava: log(request, o, "Účet", "uzivatel", "", zprava)
        if changed:
            for n in changed:  # vybrané záznamy (zaměstnanci, zákazník…) jménem, ne číslem nebo QuerySetem
                log(request, o, "Úprava", n, hodnota_text(old[n], form.fields[n]), hodnota_text(form.cleaned_data[n], form.fields[n]))
        else: log(request, o, "Vytvoření" if not pk else "Úprava", popis_z=zak if slug == "zarizeni" else None)
        for d in ulozene: log(request, d, "Vytvoření")
        messages.success(request, f"Uloženo ({len(ulozene) + 1} položky)." if 1 <= len(ulozene) <= 3 else f"Uloženo ({len(ulozene) + 1} položek)." if ulozene else "Uloženo.")
        return redirect(nx or zpet or reverse("detail", args=[slug, o.pk]))
    uvod, sekce = sekce_formulare(slug, form)
    zrusit = nx or zpet or (reverse("detail", args=[slug, o.pk]) if o else reverse("list", args=[slug]))
    if zak and slug == "zarizeni": uvod = f"Zařízení zákazníka {zak.zakaznik}, přidá se k zakázce {zak.cislo_zakazky}."
    if zak and slug == "platba": uvod = f"Zaplacená částka k zakázce {zak.cislo_zakazky} bez faktury, např. hotově při vyzvednutí. Platbu faktury označíte tlačítkem Zaplaceno v detailu faktury."
    if dalsi is not None:  # kopie formuláře bez pole zakázka (to je společné v prvním formuláři)
        bez_zak = lambda f: [(t, [(x, w) for x, w in pp if x.name != "zakazka"]) for t, pp in sekce_formulare(slug, f)[1]]
        dalsi = dict(kopie=[(n, f.non_field_errors(), bez_zak(f)) for n, f in dalsi], vzor=bez_zak(prazdny), dalsi_cislo=max([int(n) for n, _ in dalsi] + [0]) + 1,
                     co="práci" if slug == "provedenyukon" else "materiál", nazev="Další práce" if slug == "provedenyukon" else "Další materiál")
    return R(request, "form_sekce", slug=slug, M=M, o=o, form=form, multipart=form.is_multipart(), sekce=sekce, zrusit=zrusit, dalsi=dalsi,
             nadpis=f"Úprava: {o}" if o else nadpis_novy(slug, M), uvod=None if o and not zak else uvod)

def _kontrola(request, slug, form, o, zak):
    """Kontroly, které potřebují víc než jedno pole formuláře. Chybu zapíše do formuláře a vrátí False."""
    c = form.cleaned_data
    if slug == "zarizeni":
        majitel = zak.zakaznik if zak else c.get("zakaznik")
        jiny = zarizeni_stejne(c.get("vyrobce", ""), c.get("seriove_cislo", ""), bez=o.pk if o else None)
        if jiny and majitel and jiny.zakaznik_id != majitel.pk:
            form.add_error("seriove_cislo", f"Zařízení s tímto sériovým číslem už je v evidenci u zákazníka {jiny.zakaznik}. Jedno zařízení nemůže patřit dvěma zákazníkům – "
                                            f"otevřete stávající zařízení a změňte u něj zákazníka.")
        elif jiny: form.add_error("seriove_cislo", f"Toto zařízení už je v evidenci ({jiny}).")
        if o and majitel and "zakaznik" in form.changed_data:  # převod zařízení na jiného zákazníka jen tehdy, když není rozpracované u původního
            z = otevrena_zakazka(o)
            if z and z.zakaznik_id != majitel.pk: form.add_error("zakaznik", f"Zařízení je právě na firmě v zakázce {z.cislo_zakazky} zákazníka {z.zakaznik}. Převést ho jde až po jejím uzavření.")
    if slug == "zakazka" and c.get("zakaznik"):  # zakázka smí obsahovat jen zařízení svého zákazníka
        cizi = [d for d in c.get("zarizeni", []) if d.zakaznik_id != c["zakaznik"].pk]
        if cizi: form.add_error("zarizeni", "Zařízení " + ", ".join(map(str, cizi)) + " patří jinému zákazníkovi.")
    return not form.errors

def otevrena_zakazka(d):
    """Neuzavřená zakázka, ve které je zařízení právě na firmě (nebo None)."""
    return d.zakazka_set.exclude(stav__nazev__in=CLOSED).order_by("-datum_vytvoreni").first() if d.pk else None
def zarizeni_stejne(vyrobce, sn, bez=None):
    """Stejné fyzické zařízení = stejný výrobce a sériové číslo (bez ohledu na velikost písmen a mezery)."""
    sn = (sn or "").strip()
    if not sn: return None
    qs = Zarizeni.objects.filter(seriove_cislo__iexact=sn, vyrobce__iexact=(vyrobce or "").strip()).select_related("zakaznik")
    return (qs.exclude(pk=bez) if bez else qs).first()

class FotkyForm(forms.Form):
    class VicSouboru(forms.ClearableFileInput): allow_multiple_selected = True
    class VicSouboruPole(forms.FileField):
        def clean(self, data, initial=None):
            data = [x for x in (data if isinstance(data, (list, tuple)) else [data]) if x]
            if not data: raise forms.ValidationError("Vyberte aspoň jednu fotografii.")
            r = [forms.FileField.clean(self, x, initial) for x in data]
            for x in r:
                if not (getattr(x, "content_type", "") or "").startswith("image/"): raise forms.ValidationError(f"Soubor {x.name} není obrázek.")
            return r
    zakazka = ZakazkaChoice(Zakazka.objects.select_related("zakaznik").order_by("-datum_vytvoreni"), label="Zakázka", empty_label="— vyberte zakázku —",
                            widget=forms.Select(attrs={"class": "form-select"}))
    soubory = VicSouboruPole(label="Fotografie", help_text="Můžete vybrat víc fotek najednou (Ctrl nebo Shift).",
                             widget=VicSouboru(attrs={"class": "form-control", "accept": "image/*"}))

def fotografie_nove(request):
    form = FotkyForm(request.POST or None, request.FILES or None, initial={"zakazka": request.GET.get("zakazka")})
    nx = safe_next(request); zpet = zpet_url(request)
    if request.method == "POST" and form.is_valid():
        z = form.cleaned_data["zakazka"]
        with transaction.atomic():
            for f in form.cleaned_data["soubory"]:
                o = Fotografie.objects.create(zakazka=z, soubor=f, nahral=request.user); log(request, o, "Vytvoření", popis_z=z)
        n = len(form.cleaned_data["soubory"]); messages.success(request, f"Nahráno fotografií: {n}.")
        return redirect(nx or zpet or reverse("detail", args=["zakazka", z.pk]) + "#foto")
    sekce = [("Fotografie", [(form["zakazka"], 12), (form["soubory"], 12)])]
    return R(request, "form_sekce", slug="fotografie", M=Fotografie, o=None, form=form, multipart=True, sekce=sekce, zrusit=nx or zpet or reverse("list", args=["zakazka"]),
             nadpis="Nové fotografie", uvod="Fotografie se uloží k vybrané zakázce. Kdo je nahrál, se zapíše automaticky.")

def sekce_formulare(slug, form):
    """Všechny obecné formuláře mají nový vzhled: sekce a pole vedle sebe; rozvržení podle ROZVRH, jinak automaticky. Vrátí (úvod, sekce)."""
    sirka = lambda n: 12 if form[n].widget_type in ("textarea", "checkbox", "selectmultiple", "checkboxselectmultiple", "radioselect", "clearablefile", "file") else 6
    uvod, rozvrh = ROZVRH.get(slug, (None, [("Údaje", [])]))
    umistena = {n for _, pp in rozvrh for n, _ in pp}
    sekce = [(t, [(form[n], w) for n, w in pp if n in form.fields]) for t, pp in rozvrh]
    zbyle = [(form[n], sirka(n)) for n in form.fields if n not in umistena]
    if zbyle:
        if slug in ROZVRH: sekce.append(("Další údaje", zbyle))
        else: sekce[0][1].extend(zbyle)
    return uvod, [x for x in sekce if x[1]]

ROD = {"zakaznik": "Nový", "stavzakazky": "Nový", "typukonu": "Nový", "material": "Nový", "dodavatel": "Nový", "zamestnanec": "Nový", "kontaktniosoba": "Nová",
       "zarizeni": "Nové", "opravneni": "Nové", "kalendarudalost": "Nová", "role": "Nová", "sazbadph": "Nová", "platba": "Nová", "priloha": "Nová",
       "fotografie": "Nová", "provedenyukon": "Nová", "pouzitymaterial": "Nový", "faktura": "Nová", "nabidka": "Nová", "objednavka": "Nová"}
def nadpis_novy(slug, M):
    n = {"provedenyukon": "práce", "kalendarudalost": "událost kalendáře"}.get(slug, M._meta.verbose_name)
    return f"{ROD[slug]} {n}" if slug in ROD else f"Nový záznam: {n}"

class ZamestnanecForm(forms.ModelForm):
    """Zaměstnanec + jeho přihlašovací účet (uživatelské jméno, heslo, administrátor) – bez Django adminu."""
    UCET = ("ucet_aktivni", "ucet_jmeno", "ucet_heslo", "ucet_heslo2", "ucet_admin")
    ucet_aktivni = forms.BooleanField(label="Může se přihlásit do aplikace", required=False)
    ucet_jmeno = forms.CharField(label="Přihlašovací jméno", required=False, max_length=150)
    ucet_heslo = forms.CharField(label="Heslo", required=False, strip=False, widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
                                 help_text="U existujícího účtu nechte prázdné, pokud heslo neměníte.")
    ucet_heslo2 = forms.CharField(label="Heslo znovu", required=False, strip=False, widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}))
    ucet_admin = forms.BooleanField(label="Hlavní administrátor (smí všechno bez ohledu na role, včetně Django adminu)", required=False)
    prihlaseny = None
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for n, f in self.fields.items():
            if n in POPISKY and f.label == n.replace("_", " ").capitalize(): f.label = POPISKY[n]
            w = f.widget; w.attrs["class"] = "form-check-input" if isinstance(w, forms.CheckboxInput) else "form-select" if isinstance(w, forms.Select) else "form-control"
            if n == "telefon": w.attrs.setdefault("placeholder", TEL_PRIKLAD)
        if "role" in self.fields:
            f = self.fields["role"]; zaskrtavatka(f, "role")
            f.widget = VolbySNovym("role", "+ Nová role", attrs={"class": "bm-volby"}); f.widget.choices = f.choices
            f.help_text += " Chybí vhodná role? Založte ji tlačítkem + Nová role, formulář zůstane rozpracovaný."
        u = self.instance.uzivatel if self.instance.pk else None
        if u: self.initial.update(ucet_aktivni=u.is_active, ucet_jmeno=u.username, ucet_admin=u.is_staff or u.is_superuser)
    def clean(self):
        c = super().clean(); u = self.instance.uzivatel if self.instance.pk else None
        if not c.get("ucet_aktivni"):
            if u and self.prihlaseny and u.pk == self.prihlaseny.pk: self.add_error("ucet_aktivni", "Vlastní účet nelze vypnout.")
            return c
        jm = (c.get("ucet_jmeno") or "").strip(); c["ucet_jmeno"] = jm
        if not jm: self.add_error("ucet_jmeno", "Zadejte přihlašovací jméno.")
        elif User.objects.filter(username__iexact=jm).exclude(pk=u.pk if u else None).exists(): self.add_error("ucet_jmeno", "Toto jméno už používá jiný účet.")
        h, h2 = c.get("ucet_heslo") or "", c.get("ucet_heslo2") or ""
        if not u and not h: self.add_error("ucet_heslo", "Zadejte heslo pro nový účet.")
        if h or h2:
            if h != h2: self.add_error("ucet_heslo2", "Hesla se neshodují.")
            else:
                from django.contrib.auth.password_validation import validate_password
                try: validate_password(h, user=u)
                except forms.ValidationError as e: self.add_error("ucet_heslo", e)
        if u and self.prihlaseny and u.pk == self.prihlaseny.pk and not c.get("ucet_admin") and (u.is_staff or u.is_superuser):
            self.add_error("ucet_admin", "Sami sobě administrátora odebrat nelze.")
        return c
    def uloz_ucet(self, z):
        """Vytvoří / upraví / vypne účet zaměstnance; vrátí popis změny pro historii (bez hesla)."""
        c = self.cleaned_data; u = z.uzivatel
        if not c.get("ucet_aktivni"):
            if u and u.is_active: u.is_active = False; u.save(update_fields=["is_active"]); return f"účet {u.username} vypnut"
            return ""
        nov = u is None; u = u or User(); zm = []
        if u.username != c["ucet_jmeno"]: u.username = c["ucet_jmeno"]; zm.append("jméno")
        if not u.is_active: u.is_active = True; zm.append("zapnut")
        if not u.is_superuser and u.is_staff != bool(c.get("ucet_admin")): u.is_staff = bool(c.get("ucet_admin")); zm.append("administrátor" if u.is_staff else "bez administrátora")
        if c.get("ucet_heslo"): u.set_password(c["ucet_heslo"]); zm.append("heslo")
        u.first_name, u.last_name, u.email = z.jmeno[:150], z.prijmeni[:150], z.email
        u.save()
        if nov: z.uzivatel = u; z.save(update_fields=["uzivatel"]); return f"účet {u.username} vytvořen"
        return f"účet {u.username}: " + ", ".join(zm) if zm else ""

ROZVRH = {  # slug -> (úvodní text, [(nadpis sekce, [(pole, šířka 1–12)])]); pole, která tu chybí, se ukážou v sekci „Další údaje“
    "zakaznik": ("Nejdřív vyberte, jestli jde o soukromou osobu, nebo o firmu. U firmy vyplňte název firmy a IČO, jméno je nepovinné (kontaktní osoba). Kontaktní osoby přidáte na stránce zákazníka.",
                 [("Zákazník", [("typ_zakaznika", 12), ("jmeno", 6), ("firma", 6)]),
                  ("Kontakt", [("telefon", 4), ("email", 8), ("adresa", 12)]),
                  ("Firemní údaje", [("ico", 4), ("dic", 4)]),
                  ("Stav", [("aktivni", 12)])]),
    "zarizeni": ("Zařízení vždy patří zákazníkovi. Když zákazník ještě není v evidenci, založte ho přes „+ Nový“.",
                 [("Zařízení", [("zakaznik", 12), ("vyrobce", 4), ("typ", 4), ("seriove_cislo", 4), ("popis", 12)]), ("Stav", [("aktivni", 12)])]),
    "zamestnanec": ("Zaměstnanec, který se má přihlašovat do aplikace, potřebuje účet – nastavíte ho níže v sekci Přihlašovací účet.",
                 [("Zaměstnanec", [("jmeno", 4), ("prijmeni", 4), ("pracovni_pozice", 4)]), ("Kontakt", [("telefon", 4), ("email", 8)]),
                  ("Role", [("role", 12), ("aktivni", 12)]),
                  ("Přihlašovací účet", [("ucet_aktivni", 12), ("ucet_jmeno", 4), ("ucet_heslo", 4), ("ucet_heslo2", 4), ("ucet_admin", 12)])]),
    "role": ("Role je svazek oprávnění, např. Technik nebo Administrativa. Zaškrtněte, co role smí, a pak ji přiřaďte zaměstnancům v jejich kartě. "
             "Role s volbou „Je administrátor“ smí všechno.",
                 [("Role", [("nazev", 6), ("popis", 12), ("opravneni", 12)]), ("Nastavení", [("je_administrator", 12), ("aktivni", 12)])]),
    "opravneni": ("Oprávnění je konkrétní akce, kterou může role povolit (např. vystavení faktury). Seznam oprávnění určuje aplikace, přiřazují se rolím.",
                 [("Oprávnění", [("kod", 6), ("nazev", 6), ("popis", 12)])]),
    "stavzakazky": ("Stavy, kterými zakázka prochází. Pořadí určuje, jak jdou stavy za sebou v přehledech. Nový stav se zařadí na konec; "
                    "zvolíte-li obsazené pořadí, ostatní stavy se posunou.",
                 [("Stav zakázky", [("nazev", 6), ("poradi", 3), ("barva", 3), ("popis", 12), ("aktivni", 12)])]),
    "typukonu": ("Typy prací, ze kterých se vybírá při zápisu práce na zakázce.", [("Typ úkonu", [("nazev", 6), ("popis", 12), ("aktivni", 12)])]),
    "material": ("Katalog materiálu. Poslední cena se nabídne při přidání materiálu na zakázku.",
                 [("Materiál", [("nazev", 6), ("jednotka", 3), ("posledni_cena", 3), ("aktivni", 12)])]),
    "dodavatel": ("Dodavatelé, od kterých přijímáte faktury. Při importu ISDOC se dodavatel najde podle IČO nebo založí sám.",
                 [("Dodavatel", [("nazev", 6), ("ico", 3), ("dic", 3), ("adresa", 12)]), ("Kontakt a platba", [("telefon", 4), ("email", 4), ("cislo_uctu", 4), ("poznamka", 12)]),
                  ("Stav", [("aktivni", 12)])]),
    "sazbadph": ("Sazby DPH, ze kterých se vybírá u prací a materiálu. Výchozí sazba se nastavuje v Nastavení → Firma.", [("Sazba DPH", [("sazba", 3), ("aktivni", 12)])]),
    "platba": (None, [("Platba", [("zakazka", 6), ("zpusob", 6), ("castka", 6), ("datum_zaplaceni", 6), ("stav", 6), ("poznamka", 12)])]),
    "provedenyukon": ("Práce provedená na zakázce. Pokud na ní pracovalo víc lidí (třeba každý jiný den), zaškrtněte všechny.",
                 [("Práce", [("zakazka", 12), ("typ_ukonu", 5), ("cena", 3), ("sazba_dph", 4), ("zamestnanci", 12), ("poznamka", 12)])]),
    "priloha": ("Příloha zakázky, např. PDF, dokument nebo tabulka. Typ souboru se pozná z přípony a kdo přílohu nahrál, se zapíše automaticky.",
                 [("Příloha", [("nazev", 6), ("soubor", 6), ("zakazky", 12), ("poznamka", 12)])]),
    "kalendarudalost": ("Vlastní záznam do kalendáře, např. schůzka, výjezd nebo připomínka. Události zakázek a faktur se do kalendáře zapisují samy.",
                 [("Událost", [("nazev", 6), ("datum", 3), ("typ", 3), ("popis", 12)]),
                  ("Zařazení", [("zakazka", 6), ("zamestnanci", 6)]),
                  ("Další vazby (nepovinné)", [("faktura", 4), ("platba", 4), ("prijata_faktura", 4)])]),
}

def delete(request, slug, pk):
    if not jen_admin_ok(request, slug): return redirect("dashboard")
    M = get(slug); o = get_object_or_404(M, pk=pk)
    if slug in READONLY: raise Http404
    detail_url = reverse("detail", args=[slug, pk])
    if request.method == "POST":
        if hasattr(o, "aktivni"):
            o.aktivni = False; o.save(); log(request, o, "Deaktivace", "aktivni", True, False); messages.success(request, "Záznam byl deaktivován (smazání se u záznamů s historií neprovádí).")
            return redirect(safe_next(request) or zpet_url(request) or reverse("list", args=[slug]))
        try: log(request, o, "Smazání"); o.delete(); messages.success(request, "Smazáno.")
        except ProtectedError: messages.error(request, "Záznam nelze smazat, je na něj navázán jiný záznam."); return redirect(safe_next(request) or zpet_url(request) or detail_url)
        return redirect(safe_next(request) or zpet_url(request, vynechat=[detail_url]) or (_mimo_seznam(request, slug) if slug in SKRYTE_SEZNAMY else reverse("list", args=[slug])))  # smazaný záznam už nejde otevřít
    return R(request, "delete", slug=slug, M=M, o=o, zrusit=safe_next(request) or zpet_url(request) or detail_url)

# ---------------- Pracovní plocha ----------------
IMG = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
def kind_of(name):
    e = name.rsplit(".", 1)[-1].lower()
    return "img" if e in IMG else "pdf" if e == "pdf" else "file"

def plocha_home(request):
    q = request.GET.get("q", ""); res = None
    if q:
        res = Zakazka.objects.select_related("zakaznik", "stav").filter(Q(cislo_zakazky__icontains=q) | Q(zakaznik__firma__icontains=q) | Q(zakaznik__jmeno__icontains=q)
            | Q(popis_zavady__icontains=q) | Q(zarizeni__seriove_cislo__icontains=q) | Q(zarizeni__typ__icontains=q)).distinct().order_by("-datum_vytvoreni")[:30]
    ids = request.session.get("recent", []); by = Zakazka.objects.select_related("zakaznik", "stav").in_bulk(ids)
    return R(request, "plocha_home", sec="plocha", q=q, res=res, recent=[by[i] for i in ids if i in by],
        otevrene=Zakazka.objects.exclude(stav__nazev__in=CLOSED).select_related("zakaznik", "stav").order_by("-datum_vytvoreni")[:15],
        dnes=KalendarUdalost.objects.filter(datum__date=timezone.localdate()).order_by("datum"))

def hlavni_akce(z, ma_praci, ma_nabidku, ma_fakturu):
    """Jeden doporučený další krok podle stavu zakázky; na stránce je zvýrazněn jako hlavní tlačítko."""
    n = z.stav.nazev if z.stav else "Nová"
    if n in CLOSED: return None
    if n in ("Opraveno", "Připraveno k vyzvednutí"):
        if not ma_fakturu: return "faktura" if ma_nabidku or n == "Připraveno k vyzvednutí" else "nabidka"
        return None
    if n == "Čeká na schválení": return None if ma_nabidku else "nabidka"
    if n == "Nová" and not ma_praci: return "list"
    return "prace"
def zapojeni_zamestnanci(z):
    """Všichni zaměstnanci, kteří mají se zakázkou něco společného, a u každého co na ní dělal.
    Přiřazení k zakázce (kdo ji převzal), provedené práce, události v kalendáři a to, co nahrál nebo vystavil přes svůj účet."""
    lide = {}  # klíč -> dict(e=zaměstnanec nebo účet, pozice, cinnosti)
    def pridej(e, cinnost, pocet=1):
        if e is None: return
        if isinstance(e, User):  # účet bez karty zaměstnance se ukáže jménem z účtu
            zam = Zamestnanec.objects.filter(uzivatel=e).first()
            if zam is None:
                klic = ("u", e.pk); jmeno = e.get_full_name() or e.username
                o = lide.setdefault(klic, dict(e=jmeno, pk=None, pozice="", cinnosti={}))
                o["cinnosti"][cinnost] = o["cinnosti"].get(cinnost, 0) + pocet; return
            e = zam
        o = lide.setdefault(("z", e.pk), dict(e=e, pk=e.pk, pozice=e.pracovni_pozice, cinnosti={}))
        o["cinnosti"][cinnost] = o["cinnosti"].get(cinnost, 0) + pocet
    for e in z.zamestnanci.all(): pridej(e, "přiřazen(a) k zakázce")
    for u in z.provedenyukon_set.select_related("typ_ukonu").prefetch_related("zamestnanci"):
        for e in u.zamestnanci.all(): pridej(e, f"práce: {u.typ_ukonu}" if u.typ_ukonu else "práce")
    for k in KalendarUdalost.objects.filter(zakazka=z).prefetch_related("zamestnanci"):
        for e in k.zamestnanci.all(): pridej(e, f"kalendář: {k.typ}")
    for f in z.fotografie_set.select_related("nahral"): pridej(f.nahral, "nahrál(a) fotografii")
    for p in z.priloha_set.select_related("nahral"): pridej(p.nahral, "nahrál(a) přílohu")
    for n in z.nabidka_set.select_related("vypracoval"): pridej(n.vypracoval, "vypracoval(a) nabídku")
    for f in z.faktura_set.select_related("vystavil"): pridej(f.vystavil, "vystavil(a) fakturu")
    out = []
    for o in lide.values():
        o["cinnosti"] = [f"{c} ({n}×)" if n > 1 else c for c, n in o["cinnosti"].items()]; out.append(o)
    return out

def plocha(request, pk):
    z = get_object_or_404(Zakazka.objects.select_related("zakaznik", "stav"), pk=pk); back = f"?next={request.path}"
    items = []
    def add(group, title, kind, url, **k):
        it = dict(i=len(items), group=group, title=str(title)[:60], kind=kind, url=url, dl=url, **k); items.append(it); return it
    foto = [add("Fotografie", f.popis[:40] or f"Foto {f.pk}", "img", f.soubor.url, delete=reverse("delete", args=["fotografie", f.pk]) + back) for f in z.fotografie_set.all()]
    pril = [add("Přílohy", p.nazev, kind_of(p.soubor.name), p.soubor.url, delete=reverse("delete", args=["priloha", p.pk]) + back) for p in z.priloha_set.all()]
    dok = []
    def dok_add(group, typ, o, title=None):  # zobrazí se ve výchozí šabloně, stažení = PDF
        it = add(group, title or o, "html", reverse("dokument_obsah", args=[typ, o.pk])); it["dl"] = reverse("dokument_pdf", args=[typ, o.pk]); dok.append(it)
    dok_add("Zakázkový list", "zakazkovy_list", z, f"Zakázkový list {z.cislo_zakazky}")
    pr = P.prava(request.user)  # doklady vidí jen ten, kdo s nimi smí pracovat
    for n in (z.nabidka_set.all() if P.NABIDKY in pr else ()): dok_add("Nabídky", "nabidka", n)
    for f in (z.faktura_set.all() if P.FAKTURY in pr else ()): dok_add("Faktury", "faktura", f)
    for o in (z.objednavka_set.select_related("priloha") if P.NABIDKY in pr else ()):
        if o.priloha and o.priloha.soubor: dok.append(add("Objednávky", o, kind_of(o.priloha.soubor.name), o.priloha.soubor.url))
        else: dok.append(dict(group="Objednávky", title=str(o), kind="link", url=reverse("detail", args=["objednavka", o.pk])))
    ukony = z.provedenyukon_set.select_related("typ_ukonu").prefetch_related("zamestnanci"); mat = z.pouzitymaterial_set.select_related("material")
    sum_u = sum((u.cena or 0) for u in ukony); sum_m = sum(m.mnozstvi * (m.jednotkova_cena or 0) for m in mat)
    platby = Platba.objects.filter(Q(zakazka=z) | Q(faktura__zakazky=z)).distinct() if P.FAKTURY in pr else Platba.objects.none()
    request.session["recent"] = ([pk] + [x for x in request.session.get("recent", []) if x != pk])[:8]
    tabs = [("info", "Přehled"), ("prace", "Práce"), ("mat", "Materiál"), ("foto", f"Fotografie ({len(foto)})"), ("pril", f"Přílohy ({len(pril)})"),
            ("dok", f"Dokumenty ({len(dok)})"), ("kont", "Kontakty"), ("zar", "Zařízení"), ("zam", "Zaměstnanci"), ("hist", "Historie změn")]
    hist = HistorieZmen.objects.filter(typ_objektu="zakazka", id_objektu=pk)[:60]
    hlavni = hlavni_akce(z, ukony.exists(), z.nabidka_set.exists(), z.faktura_set.exists())
    return R(request, "plocha", **stav_ctx(request, z), hlavni=hlavni, sec="zakazky", crumbs=[("📋 Zakázky", reverse("list", args=["zakazka"])), (str(z), None)], tabs=tabs, pril=pril, hist=hist, z=z, items=items, foto=foto, dok=dok, nxt=request.path, zarizeni=z.zarizeni.all(),
             kontakty=z.zakazkakontakt_set.select_related("kontakt"), zam=zapojeni_zamestnanci(z), ukony=ukony, mat=mat, sum_u=sum_u, sum_m=sum_m, platby=platby)

# ---------------- Nabídka ze zakázky ----------------
def nabidka_polozky(z):
    """Položky nabídky z provedených úkonů a použitého materiálu zakázky (ceny i DPH se berou ze zakázky)."""
    ns = NastaveniFirmy.objects.first(); dph0 = ns.vychozi_dph if ns and ns.vychozi_dph is not None else Decimal(21); out = []
    def add(popis, mn, j, cena, dph):
        cena = cena or Decimal(0); dph = dph if dph is not None else dph0; bez = round(mn * cena, 2)
        out.append(dict(popis=popis[:300], mnozstvi=mn, jednotka=j, cena=cena, dph=dph, bez=bez, s=round(bez * (1 + dph / 100), 2)))
    for u in z.provedenyukon_set.select_related("typ_ukonu"):
        add(u.typ_ukonu.nazev, Decimal(1), "ks", u.cena, u.sazba_dph)
    for m in z.pouzitymaterial_set.select_related("material"): add(m.material.nazev, m.mnozstvi, m.material.jednotka or "ks", m.jednotkova_cena, m.sazba_dph)
    return out
def nahled_ctx(z):
    p = nabidka_polozky(z); b = sum(x["bez"] for x in p); s = sum(x["s"] for x in p)
    return {"z": z, "polozky": p, "sum_bez": b, "sum_s": s, "sum_dph": s - b}

class NabidkaForm(forms.Form):
    zakazka = ZakazkaChoice(Zakazka.objects.select_related("zakaznik").order_by("-datum_vytvoreni"), label="Zakázka", empty_label="— vyberte zakázku —")
    datum = forms.DateTimeField(label="Datum vystavení", input_formats=["%Y-%m-%dT%H:%M"],
                                widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}, format="%Y-%m-%dT%H:%M"))
    poznamka = forms.CharField(label="Poznámka (nepovinné)", required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["zakazka"].widget.attrs.update({"class": "form-select", "hx-get": reverse("nabidka_nahled"), "hx-target": "#nahled", "hx-trigger": "change"})

def nahled_noveho(request, typ, pk):
    """Po vytvoření dokladu rovnou jeho náhled; `nove=1` místo tlačítka Zpět nabídne Pokračovat (doklad už existuje)."""
    q = {"nove": 1}; nx = safe_next(request)
    if nx: q["next"] = nx
    return reverse("dokument", args=[typ, pk]) + "?" + urlencode(q)

def nabidka_nova(request):
    z0 = Zakazka.objects.filter(pk=request.GET.get("zakazka") or 0).first()
    form = NabidkaForm(request.POST or None, initial={"zakazka": z0, "datum": timezone.localtime().strftime("%Y-%m-%dT%H:%M")})
    if request.method == "POST" and form.is_valid():
        z = form.cleaned_data["zakazka"]
        with transaction.atomic():
            n = Nabidka.objects.create(cislo_nabidky=Nabidka.cislo_ze_zakazky(z), zakaznik=z.zakaznik, datum_vystaveni=form.cleaned_data["datum"], vypracoval=request.user,
                identifikacni_cislo=z.identifikacni_cislo, sekundarni_cislo=z.sekundarni_cislo, poznamka=form.cleaned_data["poznamka"])
            n.zakazky.add(z)
            for p in nabidka_polozky(z):
                PolozkaNabidky.objects.create(nabidka=n, zakazka=z, popis=p["popis"], mnozstvi=p["mnozstvi"], jednotka=p["jednotka"], jednotkova_cena=p["cena"], sazba_dph=p["dph"])
            log(request, n, "Vytvoření", popis_z=z)
        if z.stav and z.stav.nazev == "Nová": set_stav(request, z, "Čeká na schválení")  # nabídka čeká na schválení zákazníkem
        messages.success(request, f"Nabídka {n.cislo_nabidky} vytvořena ze zakázky {z.cislo_zakazky}.")
        return redirect(nahled_noveho(request, "nabidka", n.pk))
    z = form["zakazka"].value() and Zakazka.objects.filter(pk=form["zakazka"].value()).first()
    return R(request, "nabidka_nova", sec="dokumenty", form=form, nahled=nahled_ctx(z) if z else None)

# ---------------- Faktura ze zakázky ----------------
SPLATNOST_DNI = 14
class FakturaForm(forms.Form):
    zakazka = ZakazkaChoice(Zakazka.objects.select_related("zakaznik").order_by("-datum_vytvoreni"), label="Zakázka", empty_label="— vyberte zakázku —")
    datum = forms.DateField(label="Datum vystavení", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"))
    duzp = forms.DateField(label="DUZP", required=False, help_text="Prázdné = datum vystavení", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"))
    splatnost = forms.DateField(label="Datum splatnosti", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"))
    poznamka = forms.CharField(label="Poznámka (nepovinné)", required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["zakazka"].widget.attrs.update({"class": "form-select", "hx-get": reverse("nabidka_nahled"), "hx-vals": '{"doklad": "faktura"}', "hx-target": "#nahled", "hx-trigger": "change"})
    def clean(self):
        c = super().clean()
        if c.get("datum") and c.get("splatnost") and c["splatnost"] < c["datum"]: self.add_error("splatnost", "Splatnost nemůže být dřív než datum vystavení.")
        return c

def faktura_nova(request):
    z0 = Zakazka.objects.filter(pk=request.GET.get("zakazka") or 0).first(); dnes = timezone.localdate()
    form = FakturaForm(request.POST or None, initial={"zakazka": z0, "datum": dnes, "splatnost": dnes + timedelta(days=SPLATNOST_DNI)})
    if request.method == "POST" and form.is_valid():
        z = form.cleaned_data["zakazka"]; d = form.cleaned_data["datum"]
        with transaction.atomic():
            f = Faktura.objects.create(zakaznik=z.zakaznik, datum_vystaveni=d, datum_zdanitelneho_plneni=form.cleaned_data["duzp"] or d,
                datum_splatnosti=form.cleaned_data["splatnost"], vystavil=request.user,
                identifikacni_cislo=z.identifikacni_cislo, sekundarni_cislo=z.sekundarni_cislo, poznamka=form.cleaned_data["poznamka"])
            f.zakazky.add(z)
            for p in nabidka_polozky(z):
                PolozkaFaktury.objects.create(faktura=f, zakazka=z, popis=p["popis"], mnozstvi=p["mnozstvi"], jednotka=p["jednotka"], jednotkova_cena=p["cena"], sazba_dph=p["dph"])
            f.refresh_from_db(); Platba.objects.create(faktura=f, zakazka=z, stav="Čeká na zaplacení", castka=f.cena_s_dph)  # vystavená faktura čeká na zaplacení
            log(request, f, "Vytvoření", popis_z=z)
        messages.success(request, f"Faktura {f.cislo_faktury} vytvořena ze zakázky {z.cislo_zakazky}.")
        return redirect(nahled_noveho(request, "faktura", f.pk))
    z = form["zakazka"].value() and Zakazka.objects.filter(pk=form["zakazka"].value()).first()
    return R(request, "faktura_nova", sec="dokumenty", form=form, nahled=dict(nahled_ctx(z), doklad="faktura") if z else None)

class ZakazkaSelect(forms.Select):
    """Výběr zakázky, kde každá volba nese id zákazníka (data-zakaznik) – formulář pak nabízí jen zakázky vybraného zákazníka."""
    def create_option(self, name, value, *a, **k):
        o = super().create_option(name, value, *a, **k); inst = getattr(value, "instance", None)
        if inst is not None: o["attrs"]["data-zakaznik"] = inst.zakaznik_id
        return o

# ---------------- Přijatá objednávka od zákazníka (aplikace objednávky nevystavuje) ----------------
class ObjednavkaForm(forms.Form):
    zakaznik = forms.ModelChoiceField(Zakaznik.objects.filter(aktivni=True), label="Zákazník", empty_label="— od koho objednávka přišla —",
                                      widget=forms.Select(attrs={"class": "form-select"}))
    zakazka = ZakazkaChoice(Zakazka.objects.select_related("zakaznik").order_by("-datum_vytvoreni"), label="Zakázka", empty_label="— ke které zakázce patří —",
                            widget=ZakazkaSelect(attrs={"class": "form-select"}))
    cislo = forms.CharField(label="Číslo objednávky", max_length=50, help_text="Číslo, pod kterým zákazník objednávku vystavil.", widget=forms.TextInput(attrs={"class": "form-control"}))
    datum = forms.DateField(label="Datum vystavení", required=False, help_text="Datum uvedené na objednávce.", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"))
    stredisko = forms.CharField(label="Středisko", max_length=100, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    predmet = forms.CharField(label="Předmět objednávky", max_length=200, help_text="Stručně, o co se jedná, např. „Oprava elektronického zařízení“.", widget=forms.TextInput(attrs={"class": "form-control"}))
    text = forms.CharField(label="Text objednávky", required=False, help_text="Co zákazník objednává, opsané z objednávky, např. „Objednáváme opravu elektronického zařízení v hodnotě …“.",
                           widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}))
    soubor = forms.FileField(label="Soubor objednávky (nepovinné)", required=False, help_text="Např. PDF nebo sken od zákazníka. Uloží se i do příloh zakázky.",
                             widget=forms.ClearableFileInput(attrs={"class": "form-control"}))
    poznamka = forms.CharField(label="Poznámka (nepovinné)", required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    def clean(self):
        c = super().clean()
        if c.get("zakazka") and c.get("zakaznik") and c["zakazka"].zakaznik_id != c["zakaznik"].pk: self.add_error("zakazka", "Zakázka patří jinému zákazníkovi.")
        return c

def objednavka_nova(request):
    z0 = Zakazka.objects.filter(pk=request.GET.get("zakazka") or 0).first()
    k0 = z0.zakaznik if z0 else Zakaznik.objects.filter(pk=request.GET.get("zakaznik") or 0).first()
    form = ObjednavkaForm(request.POST or None, request.FILES or None, initial={"zakaznik": k0, "zakazka": z0, "datum": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data; z = c["zakazka"]
        with transaction.atomic():
            pr = None
            if c["soubor"]:
                pr = Priloha.objects.create(nazev=f"Objednávka {c['cislo']}"[:200], soubor=c["soubor"], nahral=request.user); pr.zakazky.add(z)
            o = Objednavka.objects.create(cislo_objednavky=c["cislo"], zakaznik=c["zakaznik"], datum_objednavky=c["datum"], stredisko=c["stredisko"], predmet=c["predmet"],
                                          text=c["text"], priloha=pr, poznamka=c["poznamka"])
            o.zakazky.add(z)
            log(request, o, "Vytvoření", popis_z=z)
        messages.success(request, f"Přijatá objednávka {o.cislo_objednavky} zapsána k zakázce {z.cislo_zakazky}.")
        return redirect(safe_next(request) or reverse("detail", args=["zakazka", z.pk]))
    return R(request, "objednavka_nova", sec="dokumenty", form=form)

def nabidka_nahled(request):
    z = Zakazka.objects.filter(pk=request.GET.get("zakazka") or 0).first()
    return render(request, "core/nabidka_nahled.html", dict(nahled_ctx(z) if z else {}, doklad=request.GET.get("doklad", "nabidka")))

# ---------------- Zákazníci ----------------
def zakaznik_detail(request, pk):
    z = get_object_or_404(Zakaznik, pk=pk)
    tabs = [("info", "Informace"), ("kont", "Kontaktní osoby"), ("zar", "Zařízení"), ("zak", "Zakázky"), ("dok", "Dokumenty"), ("hist", "Historie změn")]
    pr = P.prava(request.user); prazdne = Nabidka.objects.none()
    if not P.finance(request.user): tabs = [t for t in tabs if t[0] != "dok"]  # doklady a ceny jen s oprávněním Nabídky nebo Faktury
    return R(request, "zakaznik_detail", sec="zakaznici", crumbs=[("👥 Zákazníci", reverse("list", args=["zakaznik"])), (str(z), None)], z=z, tabs=tabs, nxt=request.path,
        kontakty=z.zakaznikkontakt_set.select_related("kontakt"), zarizeni=z.zarizeni_set.annotate(n=Count("zakazka")), zakazky=z.zakazka_set.select_related("stav"),
        nabidky=z.nabidka_set.all() if P.NABIDKY in pr else prazdne, objednavky=z.objednavka_set.all() if P.NABIDKY in pr else prazdne,
        faktury=z.faktura_set.all() if P.FAKTURY in pr else prazdne, hist=HistorieZmen.objects.filter(typ_objektu="zakaznik", id_objektu=pk)[:60])

# ---------------- Dokumenty ----------------
DOK_TYPY = [("nabidka", "Nabídky"), ("objednavka", "Objednávky"), ("faktura", "Faktury"), ("prijatafaktura", "Přijaté faktury")]
def dokumenty(request):
    typ = request.GET.get("typ", ""); q = request.GET.get("q", "").strip(); ql = q.lower()
    rows = [dict(typ="Nabídka", slug="nabidka", pk=n.pk, cislo=n.cislo_nabidky, zakaznik=n.zakaznik, datum=n.datum_vystaveni, castka=n.cena_s_dph) for n in Nabidka.objects.select_related("zakaznik")]
    rows += [dict(typ="Objednávka", slug="objednavka", pk=o.pk, cislo=o.cislo_objednavky, zakaznik=o.zakaznik, datum=o.datum_objednavky, castka=None) for o in Objednavka.objects.select_related("zakaznik")]
    rows += [dict(typ="Faktura", slug="faktura", pk=f.pk, cislo=f.cislo_faktury, zakaznik=f.zakaznik, datum=f.datum_vystaveni, castka=f.cena_s_dph) for f in Faktura.objects.select_related("zakaznik")]
    rows += [dict(typ="Přijatá faktura", slug="prijatafaktura", pk=f.pk, cislo=f.cislo_faktury, zakaznik=f.dodavatel, datum=f.datum_doruceni, castka=f.cena_s_dph, mena=f.mena,
                  stav="Po splatnosti" if f.po_splatnosti else f.stav) for f in PrijataFaktura.objects.select_related("dodavatel")]
    pr = P.prava(request.user); smi = {"nabidka": P.NABIDKY in pr, "objednavka": P.NABIDKY in pr, "faktura": P.FAKTURY in pr, "prijatafaktura": P.FAKTURY in pr}
    rows = [r for r in rows if smi[r["slug"]]]  # jen doklady, na které má uživatel oprávnění
    if ql: rows = [r for r in rows if ql in (r["cislo"] + " " + str(r["zakaznik"])).lower()]
    pocty = {}
    for r in rows: pocty[r["slug"]] = pocty.get(r["slug"], 0) + 1
    chips = _chips(request, "typ", [(k, l, pocty.get(k, 0), "") for k, l in DOK_TYPY if smi[k]], typ, len(rows))
    if typ: rows = [r for r in rows if r["slug"] == typ]
    rows.sort(key=lambda r: (str(r["datum"] or "")[:10], r["pk"]), reverse=True)
    # souhrn pod tabulkou (inspirace ABRA Flexi): počet a součet částek, zvlášť podle měny
    soucty = {}; nf = NastaveniFirmy.objects.first(); mf = nf.mena if nf and nf.mena else "CZK"  # vydané doklady jsou v měně firmy
    for r in rows:
        if r["castka"] is not None: m = r.get("mena") or mf; soucty[m] = soucty.get(m, 0) + r["castka"]
    soucet = [(f"{x:,.2f}".replace(",", "\u00a0").replace(".", ","), m) for m, x in sorted(soucty.items())] if typ and typ != "objednavka" else []
    return R(request, "dokumenty", sec="dokumenty", rows=rows, typ=typ, q=q, chips=chips, chips_label="Filtr podle typu dokumentu", soucet=soucet, ph="Číslo dokumentu nebo zákazník…")

# ---------------- Kalendář ----------------
MES = ["leden", "únor", "březen", "duben", "květen", "červen", "červenec", "srpen", "září", "říjen", "listopad", "prosinec"]
KCSS = {"Přijetí zakázky": "primary", "Vydání zařízení": "success", "Fakturováno": "warning text-dark", "Zaplaceno": "info text-dark",
        "Přijatá faktura": "dark", "Splatnost faktury": "danger", "Zaplaceno dodavateli": "info text-dark"}
def kalendar(request):
    from datetime import date, timedelta
    import calendar as cal
    v = request.GET.get("v", "month"); v = v if v in ("month", "week", "day") else "month"
    try: d = date.fromisoformat(request.GET.get("d", ""))
    except ValueError: d = timezone.localdate()
    typ, zam = request.GET.get("typ", ""), request.GET.get("zam", "")
    if v == "month":
        w = cal.Calendar(0).monthdatescalendar(d.year, d.month); start, end = w[0][0], w[-1][-1] + timedelta(1)
        prev = (d.replace(day=1) - timedelta(1)).replace(day=1); nxt = (d.replace(day=28) + timedelta(4)).replace(day=1); title = f"{MES[d.month - 1]} {d.year}"
    elif v == "week":
        start = d - timedelta(d.weekday()); end = start + timedelta(7); prev, nxt = d - timedelta(7), d + timedelta(7); title = f"{start:%d.%m.} – {end - timedelta(1):%d.%m.%Y}"
    else:
        start, end, prev, nxt, title = d, d + timedelta(1), d - timedelta(1), d + timedelta(1), f"{d:%d.%m.%Y}"
    qs = KalendarUdalost.objects.filter(datum__date__gte=start, datum__date__lt=end).select_related("zakazka", "faktura", "prijata_faktura")
    if typ: qs = qs.filter(typ=typ)
    if zam: qs = qs.filter(zamestnanci__pk=zam)
    by = {}
    for e in qs.distinct().order_by("datum"):
        e.css = KCSS.get(e.typ, "secondary")
        if e.typ == "Splatnost faktury" and e.prijata_faktura and e.prijata_faktura.stav == "Zaplaceno": e.css = "success"
        by.setdefault(timezone.localtime(e.datum).date(), []).append(e)
    today = timezone.localdate()
    days = [{"d": x, "ev": by.get(x, []), "today": x == today, "out": x.month != d.month} for x in (start + timedelta(i) for i in range((end - start).days))]
    qq = urlencode({k: x for k, x in (("typ", typ), ("zam", zam)) if x})
    return R(request, "kalendar", sec="kalendar", v=v, d=d, days=days, rows=[days[i:i + 7] for i in range(0, len(days), 7)] if v == "month" else None, title=title, prev=prev, nxt=nxt,
        today=today, typ=typ, zam=zam, qq=("&" + qq) if qq else "", modes=[("month", "Měsíc"), ("week", "Týden"), ("day", "Den")], wd=["Po", "Út", "St", "Čt", "Pá", "So", "Ne"],
        typy=[x[0] for x in KalendarUdalost._meta.get_field("typ").choices], zamestnanci=Zamestnanec.objects.filter(aktivni=True), nxtpath=request.get_full_path(),
        rychla=rychla_udalost(request, d))

RYCHLA_POLE = ("nazev", "datum", "typ", "popis")  # pole rychlého pop-upu; zbytek formuláře je pod „Rozšířené možnosti“
def rychla_udalost(request, d):
    """Pop-up „Nová událost“ v kalendáři: stejný formulář jako stránka + Událost, jen se nejdřív ukážou základní pole."""
    Form = modelform_factory(KalendarUdalost, form=BaseForm, fields="__all__", exclude=["vytvoril"], formfield_callback=cb)
    form = Form(initial={"datum": f"{d:%Y-%m-%d}T09:00"})
    _, sekce = sekce_formulare("kalendarudalost", form)
    zaklad = [(form[n], {"nazev": 12, "datum": 6, "typ": 6, "popis": 12}[n]) for n in RYCHLA_POLE]
    rozsirene = [(t, [(f, w) for f, w in pp if f.name not in RYCHLA_POLE]) for t, pp in sekce]
    return {"form": form, "zaklad": zaklad, "rozsirene": [x for x in rozsirene if x[1]], "url": reverse("create", args=["kalendarudalost"])}

# ---------------- Nastavení ----------------
def nastaveni(request):
    if not jen_admin_ok(request): return redirect("dashboard")
    L = lambda s: reverse("list", args=[s]); st = request.user.is_staff
    fi = NastaveniFirmy.objects.select_related("vytvoril").first()
    zal = f"Firmu založil {fi.vytvoril.get_full_name() or fi.vytvoril.username if fi.vytvoril else 'neznámý uživatel'} dne {timezone.localtime(fi.datum_vytvoreni):%d.%m.%Y %H:%M}." if fi and fi.datum_vytvoreni else ""
    g = [("Firma", [("Údaje o firmě a logo", reverse("nastaveni_firma"))], zal),
         ("DPH", [("Sazby DPH", L("sazbadph"))], "Výchozí sazba DPH se nastavuje v části Firma."),
         ("Uživatelé a oprávnění", [("Zaměstnanci", L("zamestnanec")), ("Role", L("role")), ("Oprávnění", L("opravneni"))], "Přihlašovací účet zaměstnance (jméno, heslo, administrátor) nastavíte přímo v kartě zaměstnance."),
         ("Dokumenty", [("Číslování dokladů", reverse("nastaveni_cislovani")), ("Šablony dokumentů", reverse("sablony"))],
          "Jak vypadají čísla zakázkových listů, nabídek a faktur. Změnit je můžete kdykoli, vystavené doklady si čísla nechají."),
         ("Katalogy", [("Stavy zakázek", L("stavzakazky")), ("Typy úkonů", L("typukonu")), ("Materiály", L("material")), ("Dodavatelé", L("dodavatel"))], ""),
         ("Systém", [("Historie změn", L("historiezmen")), ("Zálohování", reverse("nastaveni_zaloha"))] + ([("Obecná nastavení (Django admin)", "/admin/")] if st else []), "")]
    return R(request, "nastaveni", sec="nastaveni", groups=g)
def nastaveni_firma(request):
    if not jen_admin_ok(request): return redirect("dashboard")
    o = NastaveniFirmy.objects.first() or NastaveniFirmy.objects.create(nazev_firmy="Moje firma")
    return redirect(reverse("edit", args=["nastavenifirmy", o.pk]) + "?next=" + reverse("nastaveni"))
CISLOVANI = {  # model a pole s číslem pro každou řadu
    "zakazka": (Zakazka, "cislo_zakazky", "Napište, jak má vypadat číslo zakázkového listu, např. ZL260001 nebo ZAK0001."),
    "nabidka": (Nabidka, "cislo_nabidky", "Nabídka přebírá pořadové číslo zakázky, ze které vznikla. Nastavte předponu a rok, např. NAB260001 – místo 0001 se doplní pořadí zakázky."),
    "faktura": (Faktura, "cislo_faktury", "Napište, jak má vypadat číslo faktury, např. Fa0001 nebo FV2026001. Rok, měsíc a den se berou z data vystavení."),
}
def nastaveni_cislovani(request):
    """Nastavení → Dokumenty → Číslování dokladů: vzor čísla, jeho rozložení na části a náhled dalších čísel."""
    if not jen_admin_ok(request): return redirect("dashboard")
    dnes = timezone.localdate(); rady = []; chyby = 0
    for typ, nazev in CiselnaRada.TYPY:
        M, pole, uvod = CISLOVANI[typ]; r = CiselnaRada.pro(typ); e = {}
        if request.method == "POST":
            p = lambda k, d="": request.POST.get(f"{k}_{typ}", d).strip()
            vzor, fmt, nul = p("vzor"), p("format"), p("nulovat", "rok")
            if typ == "nabidka": nul = "rok" if "{YY" in fmt else "nikdy"  # pořadí určuje zakázka
            e["vzor"] = cislovani.over_format(fmt) or ("Vzor je příliš dlouhý." if len(vzor) > 50 else None)
            e["nulovat"] = None if e["vzor"] else cislovani.over_nulovani(fmt, nul)
            try: zac = int(p("zacit", "1") or 1); assert 1 <= zac < 10 ** 9
            except (ValueError, AssertionError): zac = r.zacit_od; e["zacit"] = "Zadejte celé kladné číslo."
            r.vzor, r.format, r.nulovat, r.zacit_od, r.zacit_od_obdobi = vzor, fmt, nul, zac, cislovani.obdobi(nul, dnes)
            chyby += sum(1 for x in e.values() if x)
        z = Zakazka.objects.order_by("-datum_vytvoreni").first()
        rady.append(dict(typ=typ, nazev=nazev, uvod=uvod, r=r, e=e,
                         dalsi=r.zacit_od if request.method == "POST" else r.dalsi_poradi(M, pole, dnes),
                         zak=dict(cislo=z.cislo_zakazky, poradi=z.poradove_cislo(), rok=_den_zakazky(z).year) if z else None))
    if request.method == "POST" and not chyby:
        with transaction.atomic():
            for x in rady:
                stara = CiselnaRada.objects.filter(typ=x["typ"]).first(); r = x["r"]
                if stara: r.pk = stara.pk
                r.save()
                if not stara or stara.vzor != r.vzor: log(request, r, "Úprava" if stara else "Vytvoření", "vzor", stara.vzor if stara else "", r.vzor)
        messages.success(request, "Číslování dokladů uloženo. Nová čísla se budou přidělovat podle nových vzorů."); return redirect("nastaveni")
    return R(request, "nastaveni_cislovani", sec="nastaveni", rady=rady, nulovani=cislovani.NULOVANI,
             dnes=dnes.isoformat(), crumbs=[("⚙ Nastavení", reverse("nastaveni")), ("Dokumenty", None), ("Číslování dokladů", None)])
def _den_zakazky(z): return timezone.localtime(z.datum_vytvoreni).date() if z.datum_vytvoreni else timezone.localdate()
def nastaveni_zaloha(request):
    if not jen_admin_ok(request): return redirect("dashboard")
    return R(request, "zaloha", sec="nastaveni", crumbs=[("⚙ Nastavení", reverse("nastaveni")), ("Systém", None), ("Zálohování", None)])

# ---------------- Zakázkový list (nová zakázka z jednoho místa) ----------------
def _dec(x):
    try: return Decimal(str(x).replace(",", ".").replace(" ", "")) if str(x).strip() else None
    except Exception: return None
def zakazka_nova(request):
    P = request.POST; err = None; ids = lambda n: [i for i in P.getlist(n) if i.isdigit()]
    if request.method == "POST":
        z = Zakaznik.objects.filter(pk=P.get("zakaznik") if (P.get("zakaznik") or "").isdigit() else 0).first()
        if not z: err = "Vyberte nebo vytvořte zákazníka."
        else:
            with transaction.atomic():
                dt = parse_datetime(P.get("datum_prijeti", "")) or timezone.now()
                o = Zakazka.objects.create(zakaznik=z, stav=stav_by_name("Nová"), popis_zavady=P.get("popis_zavady", ""),
                                           poznamka=P.get("poznamka", ""), datum_prijeti=timezone.make_aware(dt) if timezone.is_naive(dt) else dt)
                o.zarizeni.set(Zarizeni.objects.filter(pk__in=ids("zarizeni"), zakaznik=z)); o.zamestnanci.set(ids("prijal")[:1])  # kdo zařízení převzal
                k = KontaktniOsoba.objects.filter(pk__in=ids("kontakt")).first()
                if k: ZakazkaKontakt.objects.create(zakazka=o, kontakt=k, role=P.get("kontakt_role", "")); ZakaznikKontakt.objects.get_or_create(zakaznik=z, kontakt=k)
                for f in request.FILES.getlist("fotky"):
                    if f.content_type.startswith("image/"): Fotografie.objects.create(zakazka=o, soubor=f, nahral=request.user)
                for t, c, d in zip(P.getlist("ukon_typ"), P.getlist("ukon_cena"), P.getlist("ukon_dph")):
                    if t.isdigit(): ProvedenyUkon.objects.create(zakazka=o, typ_ukonu_id=t, cena=_dec(c), sazba_dph=_dec(d))
                for m, mn, c, d in zip(P.getlist("mat_id"), P.getlist("mat_mn"), P.getlist("mat_cena"), P.getlist("mat_dph")):
                    if m.isdigit(): PouzityMaterial.objects.create(zakazka=o, material_id=m, mnozstvi=_dec(mn) or Decimal(1), jednotkova_cena=_dec(c), sazba_dph=_dec(d))  # cena se uloží k použití
                log(request, o, "Vytvoření")
                if o.provedenyukon_set.exists(): prace_pridana(request, o)
            messages.success(request, f"Zakázka {o.cislo_zakazky} vytvořena.")
            return redirect(safe_next(request) or reverse("detail", args=["zakazka", o.pk]))
    W = lambda n, s, val, multi=False, dep="": LookupWidget(s, MODELS[s], multi, dep).render(n, val)
    ns = NastaveniFirmy.objects.first()
    return R(request, "zakazka_nova", sec="zakazky", crumbs=[("📋 Zakázky", reverse("list", args=["zakazka"])), ("Nová zakázka", None)], err=err, p=P,
        w_zakaznik=W("zakaznik", "zakaznik", P.get("zakaznik") or request.GET.get("zakaznik")), w_zarizeni=W("zarizeni", "zarizeni", P.getlist("zarizeni") or request.GET.getlist("zarizeni"), True, "zakaznik"),
        w_kontakt=W("kontakt", "kontaktniosoba", P.get("kontakt"), False, "zakaznik"), w_mat=W("mat_id", "material", None), typy=TypUkonu.objects.filter(aktivni=True),
        sazby=SazbaDPH.objects.filter(aktivni=True), dph0=ns.vychozi_dph if ns and ns.vychozi_dph is not None else Decimal(21), zam=Zamestnanec.objects.filter(aktivni=True),
        prijal=P.get("prijal") if request.method == "POST" else str(Zamestnanec.objects.filter(uzivatel=request.user).values_list("pk", flat=True).first() or ""),
        role=["Přinesl zařízení", "Vyzvedl zařízení", "Kontakt", "Jiné"], now=timezone.localtime().strftime("%Y-%m-%dT%H:%M"))

# ---------------- Zařízení (samostatná evidence) ----------------
ZAR_FILTRY = [("", "Všechna zařízení"), ("firma", "Na firmě (otevřená zakázka)"), ("oprava", "V opravě"), ("dil", "Čeká na díl"),
              ("zakaznik", "U zákazníka"), ("bez", "Bez zakázky"), ("neaktivni", "Neaktivní")]
ZAR_RAZENI = {"zarizeni": "Zařízení", "zakaznik": "Zákazník", "telefon": "Telefon", "stav": "Stav", "prijeti": "Datum přijetí", "akce": "Poslední akce"}
def _zar_posledni_akce(d, hist):
    t = [d.datum_vytvoreni, hist.get(d.pk)] + [z.datum_upravy for z in d.zz]
    return max((x for x in t if x), default=None)
def zarizeni_prehled(request):
    f = request.GET.get("f", ""); q = request.GET.get("q", "").strip(); o = request.GET.get("o", "-akce")
    fs = request.GET.get("st", ""); fi = request.GET.get("fi", "")  # filtr stavu a filtr „na firmě“
    key = o.lstrip("-") if o.lstrip("-") in ZAR_RAZENI else "akce"; desc = o.startswith("-")
    qs = Zarizeni.objects.select_related("zakaznik").prefetch_related(Prefetch("zakazka_set", queryset=Zakazka.objects.select_related("stav").order_by("-datum_prijeti", "-datum_vytvoreni"), to_attr="zz"))
    if f != "neaktivni": qs = qs.filter(aktivni=True)
    else: qs = qs.filter(aktivni=False)
    if q:
        for w in q.split():
            qs = qs.filter(Q(vyrobce__icontains=w) | Q(typ__icontains=w) | Q(seriove_cislo__icontains=w) | Q(popis__icontains=w) | Q(zakaznik__firma__icontains=w)
                           | Q(zakaznik__jmeno__icontains=w) | Q(zakaznik__telefon__icontains=w) | Q(zakazka__cislo_zakazky__icontains=w))
        qs = qs.distinct()
    hist = dict(HistorieZmen.objects.filter(typ_objektu="zarizeni").values_list("id_objektu").annotate(m=models.Max("datum")).values_list("id_objektu", "m"))
    rows = []; pocty = {}; celkem = 0; css = stav_css()
    for d in qs:
        z = d.zz[0] if d.zz else None; st = z.stav.nazev if z and z.stav else ""; otevrena = bool(z) and st not in CLOSED
        if not {"firma": otevrena, "oprava": st in ("Rozpracováno", "Opraveno"), "dil": st == "Čeká na díl", "zakaznik": bool(z) and not otevrena, "bez": not z}.get(f, True): continue
        stav = st or ("Bez zakázky" if not z else "–")
        if (fi == "ano" and not otevrena) or (fi == "ne" and otevrena): continue
        pocty[stav] = pocty.get(stav, 0) + 1; celkem += 1  # počty pro rychlý filtr stavu se berou před filtrem stavu
        if fs and stav != fs: continue
        rows.append(dict(d=d, z=z, stav=stav, css=css.get(st, "light text-dark border"), n=len(d.zz), firma=otevrena,
                         prijeti=z.datum_prijeti if z else None, akce=_zar_posledni_akce(d, hist)))
    far = timezone.make_aware(datetime(1900, 1, 1))
    sk = {"zarizeni": lambda r: f"{r['d'].vyrobce} {r['d'].typ}".lower(), "zakaznik": lambda r: str(r["d"].zakaznik).lower(), "telefon": lambda r: r["d"].zakaznik.telefon or "",
          "stav": lambda r: r["stav"].lower(), "prijeti": lambda r: r["prijeti"] or far, "akce": lambda r: r["akce"] or far}[key]
    rows.sort(key=sk, reverse=desc)
    sirka = {"zarizeni": 22, "zakaznik": 17, "telefon": 11, "stav": 20, "prijeti": 11, "akce": 12}  # pevné šířky sloupců (zbytek: Zakázek)
    heads = [(k, l, ("" if desc or k != key else "-") + k, ("▼" if desc else "▲") if k == key else "", sirka[k]) for k, l in ZAR_RAZENI.items()]
    stavy = list(StavZakazky.objects.filter(aktivni=True).order_by("poradi", "nazev").values_list("nazev", flat=True)) + ["Bez zakázky"]
    chips = _chips(request, "st", [(s, s, pocty.get(s, 0), css.get(s, "light")) for s in stavy], fs, celkem)
    keep = urlencode({k: x for k, x in (("q", q), ("f", f), ("st", fs), ("fi", fi)) if x})
    pohled, pohledy = _pohled(request, "zarizeni")
    return R(request, "zarizeni_prehled", sec="zarizeni", crumbs=None, rows=rows, f=f, q=q, o=o, heads=heads, filtry=ZAR_FILTRY, fs=fs, fi=fi, keep=keep,
             chips=chips, pohled=pohled, pohledy=pohledy, celkem=celkem, ph="Výrobce, typ, S/N, zákazník, telefon, č. zakázky…")
def zarizeni_detail(request, pk):
    d = get_object_or_404(Zarizeni.objects.select_related("zakaznik"), pk=pk)
    zak = list(d.zakazka_set.select_related("stav").prefetch_related("zamestnanci", Prefetch("provedenyukon_set", queryset=ProvedenyUkon.objects.select_related("typ_ukonu").prefetch_related("zamestnanci")),
               Prefetch("pouzitymaterial_set", queryset=PouzityMaterial.objects.select_related("material")), "zakazkakontakt_set__kontakt").order_by("-datum_prijeti", "-datum_vytvoreni"))
    for z in zak:
        z.css = f"stav-{z.stav.pk}" if z.stav else "light text-dark border"; z.otevrena = not (z.stav and z.stav.nazev in CLOSED)
        z.cena_prace = sum((u.cena or 0) for u in z.provedenyukon_set.all())
        z.cena_mat = sum((m.jednotkova_cena or 0) * m.mnozstvi for m in z.pouzitymaterial_set.all())
    akt = next((z for z in zak if z.otevrena), None)
    hist = HistorieZmen.objects.filter(typ_objektu="zarizeni", id_objektu=pk).select_related("uzivatel")[:60]
    posl = max([x for x in [d.datum_vytvoreni, hist[0].datum if hist else None] + [z.datum_upravy for z in zak] if x], default=None)
    return R(request, "zarizeni_detail", sec="zarizeni", crumbs=[("🔧 Zařízení", reverse("zarizeni_prehled")), (str(d) or "Zařízení", None)],
             d=d, zak=zak, akt=akt, hist=hist, posl=posl, nxt=request.path)

# ---------------- Stav zakázky (workflow) ----------------
# Stav zakázky je samostatný od stavu nabídek, faktur a plateb – nic z toho se navzájem neovlivňuje.
CLOSED = ("Vydáno", "Zrušeno", "Vydaná", "Zrušená")
ACTIONS = {"zahajit": ("Zahájit práci", "Rozpracováno", "primary"), "cekat_schv": ("Čeká na schválení", "Čeká na schválení", "warning"), "cekat_dil": ("Čeká na díl", "Čeká na díl", "warning"),
           "dokoncit": ("Dokončit opravu", "Opraveno", "success"), "pripravit": ("Připravit k vyzvednutí", "Připraveno k vyzvednutí", "success"),
           "vydat": ("Vydat zákazníkovi", "Vydáno", "success"), "zrusit": ("Zrušit zakázku", "Zrušeno", "outline-danger"),
           "otevrit": ("Znovu otevřít", "Rozpracováno", "outline-secondary"), "obnovit": ("Obnovit zakázku", "Nová", "outline-secondary")}
FLOW = {"Nová": ["zahajit", "cekat_schv", "cekat_dil", "zrusit"], "Rozpracováno": ["dokoncit", "cekat_dil", "cekat_schv", "zrusit"], "Čeká na schválení": ["zahajit", "zrusit"],
        "Čeká na díl": ["zahajit", "zrusit"], "Opraveno": ["pripravit", "zahajit"], "Připraveno k vyzvednutí": ["vydat", "zahajit"], "Vydáno": ["otevrit"], "Zrušeno": ["obnovit"]}
def stav_css():
    """Třída štítku pro každý stav: bg-stav-<pk>. Barvu určuje uživatel v Nastavení → Stavy zakázek (styly vypisuje {% barvy_stavu %} v base.html)."""
    return {s.nazev: f"stav-{s.pk}" for s in StavZakazky.objects.order_by("aktivni", "-poradi", "-pk")}  # při shodném názvu vyhrává aktivní stav
def stav_by_name(n): return StavZakazky.objects.filter(nazev=n).first() or StavZakazky.objects.create(nazev=n, poradi=99)
def can_set_stav(user): return P.ma(user, P.STAV)
def stav_ctx(request, z):
    n = z.stav.nazev if z.stav else ""; akce = []
    for k in FLOW.get(n, ["zahajit", "zrusit"]):
        l, _, s = ACTIONS[k]; akce.append((k, {("Čeká na schválení", "zahajit"): "Schváleno – zahájit práci", ("Čeká na díl", "zahajit"): "Díl dorazil – zahájit práci"}.get((n, k), l), s))
    return dict(akce=akce, moze_stav=can_set_stav(request.user), stavy=StavZakazky.objects.filter(aktivni=True), stav_css=f"stav-{z.stav.pk}" if z.stav else "light text-dark border")
def prace_pridana(request, z):
    """Přidáním práce se na zakázce začalo pracovat: nová zakázka přejde do stavu Rozpracováno (změna se zapíše do historie). Jiné stavy se nemění."""
    if z and z.stav and z.stav.nazev == "Nová": set_stav(request, z, "Rozpracováno")
def set_stav(request, z, nazev):
    stary = z.stav; novy = stav_by_name(nazev)
    if stary and stary.pk == novy.pk: return
    z.stav = novy; e = Zamestnanec.objects.filter(uzivatel=request.user).first()
    if nazev == "Vydáno": z.datum_vydani = timezone.now()
    elif stary and stary.nazev == "Vydáno": z.datum_vydani = None
    z.save(); log(request, z, "Změna stavu", "stav", stary.nazev if stary else "–", novy.nazev)
    if nazev == "Vydáno":
        who = str(e) if e else request.user.get_username()
        log(request, z, "Vydání", "datum_vydani", "", f"{timezone.localtime(z.datum_vydani):%d.%m.%Y %H:%M} – vydal: {who}")
        u = KalendarUdalost.objects.create(nazev=f"Vydáno {z}", datum=z.datum_vydani, typ="Vydání zařízení", automaticka=True, zakazka=z, popis=f"Vydal: {who}", vytvoril=request.user)
        if e: u.zamestnanci.add(e)
    messages.success(request, f"Stav zakázky: {novy.nazev}.")
def stav_akce(request, pk):
    z = get_object_or_404(Zakazka.objects.select_related("stav"), pk=pk); a = request.POST.get("akce", ""); n = z.stav.nazev if z.stav else ""
    if request.method == "POST":
        if a == "rucne":
            s = request.POST.get("stav", ""); novy = StavZakazky.objects.filter(pk=s).first() if s.isdigit() else None
            if not can_set_stav(request.user): messages.error(request, "Ruční změna stavu vyžaduje oprávnění.")
            elif novy: set_stav(request, z, novy.nazev)
        elif a in FLOW.get(n, ["zahajit", "zrusit"]): set_stav(request, z, ACTIONS[a][1])
        else: messages.error(request, f"Akce není ve stavu „{n}“ dostupná.")
    return redirect(reverse("detail", args=["zakazka", pk]))

# ---------------- Přijaté faktury ----------------
class ImportISDOCForm(forms.Form):
    soubor = forms.FileField(label="Soubor faktury ISDOC (.isdoc nebo .isdocx)", widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".isdoc,.isdocx,.xml"}))
    zakazka = ZakazkaChoice(Zakazka.objects.select_related("zakaznik").order_by("-datum_vytvoreni"), label="Zakázka (nepovinné, např. materiál pro konkrétní opravu)",
                            required=False, empty_label="— bez zakázky —", widget=forms.Select(attrs={"class": "form-select"}))

def prijata_faktura_import(request):
    """Nahrání faktury od dodavatele ve formátu ISDOC: dodavatel se najde podle IČO (nebo založí) a faktura se uloží jako nezaplacená."""
    from .sablony import isdoc
    form = ImportISDOCForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        f = form.cleaned_data["soubor"]; obsah = f.read()
        try:
            d = isdoc.nacti(obsah)
        except isdoc.ChybaImportu as e:
            form.add_error("soubor", str(e))
        else:
            dd = d["dodavatel"]
            dod = (Dodavatel.objects.filter(ico=dd["ico"]).first() if dd["ico"] else None) or Dodavatel.objects.filter(nazev__iexact=dd["nazev"]).first()
            dup = dod and PrijataFaktura.objects.filter(dodavatel=dod, cislo_faktury=d["cislo_faktury"]).first()
            if dup:
                messages.warning(request, f"Faktura {dup.cislo_faktury} od dodavatele {dod} už je v evidenci, znovu se nenahrála.")
                return redirect("detail", slug="prijatafaktura", pk=dup.pk)
            with transaction.atomic():
                if not dod:
                    dod = Dodavatel.objects.create(**dd); log(request, dod, "Vytvoření")
                else:  # doplnit chybějící údaje dodavatele, vyplněné se nepřepisují
                    zmeny = [k for k, v in dd.items() if v and not getattr(dod, k)]
                    for k in zmeny: setattr(dod, k, dd[k])
                    if zmeny: dod.save(update_fields=zmeny)
                pozn = "\n".join(x for x in (d["poznamka"], ("Položky: " + "; ".join(d["polozky"])) if d["polozky"] else "") if x)
                if d["druh"] != "faktura": pozn = f"Druh dokladu: {d['druh']}\n{pozn}".strip()
                pf = PrijataFaktura(dodavatel=dod, zakazka=form.cleaned_data["zakazka"], vytvoril=request.user, poznamka=pozn[:5000],
                                    **{k: d[k] for k in ("cislo_faktury", "variabilni_symbol", "datum_vystaveni", "datum_zdanitelneho_plneni", "datum_splatnosti",
                                                         "cena_bez_dph", "dph", "cena_s_dph", "mena", "cislo_uctu")})
                pf.soubor.save(f.name, ContentFile(obsah), save=False); pf.save(); log(request, pf, "Vytvoření (import ISDOC)")
            fi = NastaveniFirmy.objects.first()
            if fi and fi.ico and d["odberatel_ico"] and d["odberatel_ico"] != fi.ico:
                messages.warning(request, f"Pozor: faktura je vystavena na IČO {d['odberatel_ico']}, ne na vaši firmu ({fi.ico}).")
            messages.success(request, f"Faktura {pf.cislo_faktury} od dodavatele {dod} byla nahrána a zapsána do kalendáře. Zkontrolujte prosím údaje.")
            return redirect("detail", slug="prijatafaktura", pk=pf.pk)
    return R(request, "prijata_faktura_import", sec="dokumenty", form=form,
             crumbs=[("📄 Dokumenty", reverse("dokumenty")), ("Přijaté faktury", reverse("list", args=["prijatafaktura"])), ("Import ISDOC", None)])

PF_POLE = ["dodavatel", "cislo_faktury", "variabilni_symbol", "datum_vystaveni", "datum_doruceni", "datum_zdanitelneho_plneni", "datum_splatnosti",
           "cena_bez_dph", "dph", "cena_s_dph", "mena", "cislo_uctu", "zakazka", "soubor", "poznamka"]
def prijata_faktura_rucne(request):
    """Ruční zápis faktury od dodavatele (když není k dispozici ISDOC). Nová faktura je vždy nezaplacená."""
    Form = modelform_factory(PrijataFaktura, form=BaseForm, fields=PF_POLE, formfield_callback=cb)
    Form.base_fields["zakazka"].queryset = Zakazka.objects.select_related("zakaznik").order_by("-datum_vytvoreni")
    Form.base_fields["zakazka"].label_from_instance = lambda z: f"{z.cislo_zakazky} – {z.zakaznik}"
    form = Form(request.POST or None, request.FILES or None, initial={"zakazka": request.GET.get("zakazka"), "dodavatel": request.GET.get("dodavatel")})
    if request.method == "POST" and form.is_valid():
        pf = form.save(commit=False); pf.vytvoril = request.user
        if pf.cena_s_dph is None and pf.cena_bez_dph is not None and pf.dph is not None: pf.cena_s_dph = pf.cena_bez_dph + pf.dph
        pf.save(); log(request, pf, "Vytvoření")
        messages.success(request, f"Faktura {pf.cislo_faktury} od dodavatele {pf.dodavatel} byla zapsána do evidence i do kalendáře.")
        return redirect(safe_next(request) or reverse("detail", args=["prijatafaktura", pf.pk]))
    return R(request, "prijata_faktura_rucne", sec="dokumenty", form=form,
             crumbs=[("📄 Dokumenty", reverse("dokumenty")), ("Přijaté faktury", reverse("list", args=["prijatafaktura"])), ("Zadat ručně", None)])

@require_POST
def faktura_zaplaceno(request, pk):
    """Vystavená faktura → Zaplaceno: platba faktury se označí jako zaplacená (u starších faktur bez platby se založí) a zapíše se do kalendáře."""
    f = get_object_or_404(Faktura, pk=pk)
    p = f.platba_set.filter(~Q(stav="Zaplaceno")).first()
    if p or not f.platba_set.filter(stav="Zaplaceno").exists():
        p = p or Platba(faktura=f, zakazka=f.zakazky.first())
        p.stav = "Zaplaceno"; p.datum_zaplaceni = timezone.now(); p.castka = p.castka if p.castka is not None else f.cena_s_dph; p.save()
        log(request, f, "Úprava", "stav platby", "Čeká na zaplacení", "Zaplaceno"); messages.success(request, f"Faktura {f.cislo_faktury} je označena jako zaplacená.")
    return redirect(safe_next(request) or reverse("detail", args=["faktura", pk]))

@require_POST
def prijata_faktura_zaplaceno(request, pk):
    pf = get_object_or_404(PrijataFaktura, pk=pk)
    if pf.stav != "Zaplaceno":
        pf.stav = "Zaplaceno"; pf.save(); log(request, pf, "Úprava", "stav", "Nezaplaceno", "Zaplaceno")
        messages.success(request, f"Faktura {pf.cislo_faktury} je označena jako zaplacená.")
    return redirect(safe_next(request) or reverse("detail", args=["prijatafaktura", pk]))
