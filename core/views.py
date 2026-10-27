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
from datetime import datetime, date
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
from django.urls import reverse
from .models import (Zarizeni, KontaktniOsoba, Material, ZakaznikKontakt, ZakazkaKontakt, StavZakazky, TypUkonu, SazbaDPH, Fotografie, ProvedenyUkon, PouzityMaterial,
                     KalendarUdalost, Zamestnanec, Objednavka, Zakaznik, PolozkaNabidky, HistorieZmen, Zakazka, Nabidka, Faktura, NastaveniFirmy, Platba)

MODELS = {m._meta.model_name: m for m in apps.get_app_config("core").get_models()}
READONLY = {"historiezmen"}
SECT = [("plocha", "🖥 Pracovní plocha", "dashboard", []), ("zakazky", "📋 Zakázky", "list", ["zakazka"]), ("zakaznici", "👥 Zákazníci", "list", ["zakaznik"]),
        ("zarizeni", "🔧 Zařízení", "zarizeni_prehled", []),
        ("dokumenty", "📄 Dokumenty", "dokumenty", []), ("kalendar", "📅 Kalendář", "kalendar", []), ("nastaveni", "⚙ Nastavení", "nastaveni", [])]
SEC = {}   # slug modelu -> (sekce aplikace, skupina nastavení); tabulka NENÍ položka menu, jen se zobrazí v kontextu sekce
for _s in ("zakazka", "zakazkakontakt", "provedenyukon", "pouzitymaterial", "fotografie", "priloha"): SEC[_s] = ("zakazky", None)
for _s in ("zakaznik", "kontaktniosoba", "zakaznikkontakt"): SEC[_s] = ("zakaznici", None)
SEC["zarizeni"] = ("zarizeni", None)
for _s in ("nabidka", "polozkanabidky", "objednavka", "faktura", "polozkafaktury", "platba"): SEC[_s] = ("dokumenty", None)
SEC["kalendarudalost"] = ("kalendar", None)
for _s, _g in (("nastavenifirmy", "Firma"), ("sazbadph", "DPH"), ("zamestnanec", "Uživatelé a oprávnění"), ("role", "Uživatelé a oprávnění"),
               ("opravneni", "Uživatelé a oprávnění"), ("stavzakazky", "Katalogy"), ("typukonu", "Katalogy"), ("material", "Katalogy"), ("historiezmen", "Systém"), ("sablonadokumentu", "Dokumenty")): SEC[_s] = ("nastaveni", _g)

def safe_next(request):
    n = request.GET.get("next", "")
    return n if n.startswith("/") and not n.startswith("//") else None
def get(slug):
    if slug not in MODELS: raise Http404
    return MODELS[slug]
def R(request, tpl, sec=None, crumbs=None, **c):
    if "M" in c: c["vn"], c["vnp"] = c["M"]._meta.verbose_name, c["M"]._meta.verbose_name_plural
    nav = [(k, l, reverse(u, args=a)) for k, l, u, a in SECT]; sl = {k: (l, u) for k, l, u in nav}; g = None; slug = c.get("slug")
    if slug in SEC and not sec: sec, g = SEC[slug]
    if crumbs is None and slug in SEC:
        crumbs = [(sl[sec][0], sl[sec][1])] + ([(g, reverse("nastaveni"))] if g else []) + [(c["vnp"], None if tpl == "list" else reverse("list", args=[slug]))]
        if not g and sl[sec][0].split(" ", 1)[-1] == c["vnp"]:  # sekce a tabulka se jmenují stejně (Zakázky › Zakázky) -> bez duplicity
            crumbs = None if tpl == "list" else crumbs[:1]
    navx = [(k, *(l.split(" ", 1) if " " in l else ("", l)), u) for k, l, u in nav]  # (klíč, ikona, název, url) pro levou lištu
    return render(request, f"core/{tpl}.html", {"nav": nav, "navx": navx, "sec": sec, "crumbs": crumbs, **c})

# ---------- Vyhledávací pole s inline vytvářením (místo <select>) ----------
LOOKUP = {  # slug -> pole pro hledání, závislost (filtr podle zákazníka), pole formuláře "Nový ..."
    "zakaznik": dict(f=["jmeno", "firma", "telefon", "email", "ico"], dep=None, new=["typ_zakaznika", "jmeno", "firma", "telefon", "email", "adresa", "ico", "dic"]),
    "zarizeni": dict(f=["vyrobce", "typ", "seriove_cislo", "popis", "zakaznik__firma", "zakaznik__jmeno"], dep="zakaznik", new=["vyrobce", "typ", "seriove_cislo", "popis"]),
    "material": dict(f=["nazev"], dep=None, new=["nazev", "jednotka", "posledni_cena"]),
    "kontaktniosoba": dict(f=["jmeno", "telefon", "email"], dep="zakaznik", new=["jmeno", "telefon", "email", "poznamka"]),
}
def lk_item(slug, o):
    if slug == "zarizeni": return dict(id=o.pk, label=f"{o.vyrobce} {o.typ}".strip() or "Zařízení", sub=f"S/N: {o.seriove_cislo or '–'} · {o.zakaznik} · zakázek: {getattr(o, 'n', 0)}")
    if slug == "material": return dict(id=o.pk, label=o.nazev, sub=f"{o.jednotka} · {o.posledni_cena if o.posledni_cena is not None else '–'} Kč", price=None if o.posledni_cena is None else str(o.posledni_cena))
    return dict(id=o.pk, label=str(o), sub=" · ".join(x for x in (o.telefon, o.email, getattr(o, "adresa", "")) if x))

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

def lookup_new(request, slug):
    c = LOOKUP.get(slug)
    if not c: raise Http404
    M = MODELS[slug]; dep = request.GET.get("dep") or request.POST.get("dep") or ""
    form = modelform_factory(M, form=BaseForm, fields=c["new"], formfield_callback=cb)(request.POST or None)
    ctx = {"form": form, "slug": slug, "dep": dep, "title": "Nový záznam: " + M._meta.verbose_name}
    if request.method == "POST":
        if slug == "zarizeni" and not dep.isdigit(): form.add_error(None, "Nejdřív vyberte zákazníka.")
        elif form.is_valid():
            cd = form.cleaned_data; dup = None
            if slug == "zarizeni" and cd["seriove_cislo"]: dup = Zarizeni.objects.filter(zakaznik_id=dep, seriove_cislo__iexact=cd["seriove_cislo"]).first()
            elif slug == "material": dup = Material.objects.filter(nazev__iexact=cd["nazev"]).first()
            elif slug == "zakaznik":
                if not (cd["jmeno"] or cd["firma"]): form.add_error(None, "Vyplňte jméno nebo firmu.")
                elif cd["ico"]: dup = Zakaznik.objects.filter(ico=cd["ico"]).first()
            if dup: form.add_error(None, f"Takový záznam už existuje ({dup}) – vyberte ho ze seznamu, nevytváří se duplicita.")
            if not form.errors:
                o = form.save(commit=False)
                if slug == "zarizeni": o.zakaznik_id = dep
                o.save(); log(request, o, "Vytvoření")
                if slug == "kontaktniosoba" and dep.isdigit(): ZakaznikKontakt.objects.create(zakaznik_id=dep, kontakt=o)
                return JsonResponse(lk_item(slug, o))
        return render(request, "core/lookup_form.html", ctx, status=400)
    return render(request, "core/lookup_form.html", ctx)

class BaseForm(forms.ModelForm):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for n, f in self.fields.items():
            t = getattr(getattr(f, "queryset", None), "model", None); s = t and t._meta.model_name
            if s in LOOKUP:
                d = LOOKUP[s]["dep"]; f.widget = LookupWidget(s, t, isinstance(f, forms.ModelMultipleChoiceField), d if d in self.fields else ""); continue
            w = f.widget; c = "form-check-input" if isinstance(w, forms.CheckboxInput) else "form-select" if isinstance(w, forms.Select) else "form-control"
            w.attrs["class"] = c
            if isinstance(w, forms.Textarea): w.attrs["rows"] = 3
def cb(f, **k):
    ff = f.formfield(**k)
    if ff and isinstance(f, models.DateTimeField): ff.widget = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
    elif ff and isinstance(f, models.DateField): ff.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    return ff

def log(request, obj, akce, pole="", old="", new="", popis_z=None):
    HistorieZmen.objects.create(uzivatel=request.user, typ_objektu=obj._meta.model_name, id_objektu=obj.pk, akce=akce,
                                pole=pole, puvodni_hodnota=str(old), nova_hodnota=str(new), popis=(str(obj) + (f" ze zakázky {popis_z.cislo_zakazky}" if popis_z else ""))[:200])
def val(o, f):
    if f.choices: return o._get_FIELD_display(f) or "–"
    v = getattr(o, f.name)
    return "–" if v in (None, "") else "✓" if v is True else "✗" if v is False else v

def dashboard(request):
    return R(request, "dashboard", groups=[(g, [(s, MODELS[s]._meta.verbose_name_plural, MODELS[s].objects.count()) for s in ss]) for g, ss in GROUPS])

TYP_ZKR = {"Firma": ("F", "Firma"), "Soukromá osoba": ("SO", "Soukromá osoba")}
ZAK_RAZENI = {"cislo": "cislo_zakazky", "prijeti": "datum_prijeti", "vydani": "datum_vydani"}  # sloupce zakázek, podle kterých jde řadit
def _dt(v): return timezone.localtime(v).strftime("%d.%m.%Y %H:%M") if v else "–"
def lst(request, slug):
    M = get(slug); q = request.GET.get("q", ""); qs = M.objects.all(); flt = {}; o = ""
    if q:
        f = Q()
        for x in M._meta.fields:
            if isinstance(x, (models.CharField, models.TextField)): f |= Q(**{x.name + "__icontains": q})
        if slug == "zakazka": f |= Q(zakaznik__firma__icontains=q) | Q(zakaznik__jmeno__icontains=q)
        qs = qs.filter(f)
    if slug == "zakazka":
        st = request.GET.get("st", "")
        if st: flt["st"] = st; qs = qs.filter(stav__nazev=st)
        o = request.GET.get("o", "-cislo"); key = o.lstrip("-") if o.lstrip("-") in ZAK_RAZENI else "cislo"; desc = o.startswith("-"); o = ("-" if desc else "") + key
        pole = models.F(ZAK_RAZENI[key]); qs = qs.select_related("zakaznik", "stav").order_by(pole.desc(nulls_last=True) if desc else pole.asc(nulls_last=True), "-pk")
    if slug == "zakaznik":
        h = HistorieZmen.objects.filter(typ_objektu="zakaznik", id_objektu=OuterRef("pk")).order_by("-datum").values("datum")[:1]
        qs = qs.annotate(posl=Coalesce(Subquery(h), "datum_vytvoreni"))
    page = Paginator(qs if qs.ordered else qs.order_by("pk"), 50).get_page(request.GET.get("page"))
    if slug == "zakaznik":
        heads = [dict(l=x) for x in ["Jméno", "Firma", "Adresa", "Telefon", "E-mail", "Poslední změna"]]
        rows = [(o, [o.jmeno or o.firma or str(o), o.firma or "–", o.adresa or "–", o.telefon or "–", o.email or "–", _dt(o.posl)], TYP_ZKR.get(o.typ_zakaznika)) for o in page]
    elif slug == "zakazka":
        sk = {"Číslo zakázky": "cislo", "Datum přijetí": "prijeti", "Datum vydání": "vydani"}
        heads = [dict(l=x, ord=sk.get(x) and ("" if desc or sk[x] != key else "-") + sk[x], ar=(("▼" if desc else "▲") if sk.get(x) == key else ("↕" if x in sk else "")),
                      stav=x == "Stav") for x in ["Číslo zakázky", "Zákazník", "Stav", "Datum přijetí", "Datum vydání", "Identifikační číslo"]]
        rows = [(o, [o.cislo_zakazky, o.zakaznik, o.stav or "–", _dt(o.datum_prijeti), _dt(o.datum_vydani), o.identifikacni_cislo or "–"], None) for o in page]
    else:
        cols = [x for x in M._meta.fields if x.name != "id" and not isinstance(x, models.TextField) and not isinstance(x, models.FileField)][:6]
        heads = [dict(l=capfirst(c.verbose_name)) for c in cols]; rows = [(o, [val(o, c) for c in cols], None) for o in page]
    keep = urlencode({k: x for k, x in {"q": q, **flt}.items() if x})
    stavy = StavZakazky.objects.filter(aktivni=True).values_list("nazev", flat=True) if slug == "zakazka" else []
    return R(request, "list", slug=slug, M=M, q=q, page=page, heads=heads, rows=rows, ro=slug in READONLY, flt=flt, keep=keep, o=o,
             keep_o=urlencode({k: x for k, x in {"q": q, **flt, "o": o}.items() if x}), stavy=stavy)

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
        if r.related_model._meta.model_name in MODELS and (r.one_to_many or r.many_to_many):
            rel.append((r.related_model._meta.verbose_name_plural, r.related_model._meta.model_name, list(getattr(o, r.get_accessor_name()).all()[:50]),
                        r.field.name if r.one_to_many else None))
    hist = HistorieZmen.objects.filter(typ_objektu=slug, id_objektu=pk)[:30]
    return R(request, "detail", slug=slug, M=M, o=o, fields=fields, rel=rel, hist=hist, ro=slug in READONLY)

def edit(request, slug, pk=None):
    M = get(slug)
    if slug in READONLY: raise Http404
    if slug == "nabidka" and not pk:  # nabídka se vždy zakládá ze zakázky
        q = {"zakazka": request.GET.get("zakazky") or request.GET.get("zakazka") or "", "next": request.GET.get("next", "")}
        return redirect(reverse("nabidka_nova") + "?" + urlencode({k: x for k, x in q.items() if x}))
    if slug == "zakazka" and not pk:  # nová zakázka = zakázkový list
        return redirect(reverse("zakazka_nova") + ("?" + request.GET.urlencode() if request.GET else ""))
    o = get_object_or_404(M, pk=pk) if pk else None
    Form = modelform_factory(M, form=BaseForm, fields="__all__", formfield_callback=cb, exclude=("stav", "datum_vydani") if slug == "zakazka" else None)  # stav se mění jen akcemi workflow
    init = {}
    if not o:
        init = request.GET.dict()
        for n in ("vypracoval", "vystavil", "nahral", "vytvoril"):
            if n in Form.base_fields: init.setdefault(n, request.user.pk)
    form = Form(request.POST or None, request.FILES or None, instance=o, initial=init or None)
    if request.method == "POST" and form.is_valid():
        changed = form.changed_data if o else []; old = {n: form.initial.get(n) for n in changed}
        o = form.save()
        if changed:
            for n in changed: log(request, o, "Úprava", n, old[n], form.cleaned_data[n])
        else: log(request, o, "Vytvoření" if not pk else "Úprava")
        messages.success(request, "Uloženo."); nx = safe_next(request)
        if slug == "faktura" and not pk: return redirect(reverse("dokument", args=["faktura", o.pk]) + ("?" + urlencode({"next": nx}) if nx else ""))  # nová faktura -> náhled
        return redirect(nx) if nx else redirect("detail", slug=slug, pk=o.pk)
    return R(request, "form", slug=slug, M=M, o=o, form=form, multipart=form.is_multipart())

def delete(request, slug, pk):
    M = get(slug); o = get_object_or_404(M, pk=pk)
    if slug in READONLY: raise Http404
    if request.method == "POST":
        if hasattr(o, "aktivni"):
            o.aktivni = False; o.save(); log(request, o, "Deaktivace", "aktivni", True, False); messages.success(request, "Záznam byl deaktivován (smazání se u záznamů s historií neprovádí).")
        else:
            try: log(request, o, "Smazání"); o.delete(); messages.success(request, "Smazáno.")
            except ProtectedError: messages.error(request, "Záznam nelze smazat, je na něj navázán jiný záznam."); return redirect(safe_next(request) or reverse("detail", args=[slug, pk]))
        return redirect(safe_next(request) or reverse("list", args=[slug]))
    return R(request, "delete", slug=slug, M=M, o=o)

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
    for n in z.nabidka_set.all(): dok_add("Nabídky", "nabidka", n)
    for f in z.faktura_set.all(): dok_add("Faktury", "faktura", f)
    for o in z.objednavka_set.select_related("priloha"):
        if o.priloha and o.priloha.soubor: dok.append(add("Objednávky", o, kind_of(o.priloha.soubor.name), o.priloha.soubor.url))
        else: dok.append(dict(group="Objednávky", title=str(o), kind="link", url=reverse("detail", args=["objednavka", o.pk])))
    ukony = z.provedenyukon_set.select_related("typ_ukonu").prefetch_related("zamestnanci"); mat = z.pouzitymaterial_set.select_related("material")
    sum_u = sum((u.cena or 0) for u in ukony); sum_m = sum(m.mnozstvi * (m.jednotkova_cena or 0) for m in mat)
    platby = Platba.objects.filter(Q(zakazka=z) | Q(faktura__zakazky=z)).distinct()
    request.session["recent"] = ([pk] + [x for x in request.session.get("recent", []) if x != pk])[:8]
    tabs = [("info", "Přehled"), ("prace", "Práce"), ("mat", "Materiál"), ("foto", f"Fotografie ({len(foto)})"), ("pril", f"Přílohy ({len(pril)})"),
            ("dok", f"Dokumenty ({len(dok)})"), ("kont", "Kontakty"), ("zar", "Zařízení"), ("zam", "Zaměstnanci"), ("hist", "Historie")]
    hist = HistorieZmen.objects.filter(typ_objektu="zakazka", id_objektu=pk)[:60]
    return R(request, "plocha", **stav_ctx(request, z), sec="zakazky", crumbs=[("📋 Zakázky", reverse("list", args=["zakazka"])), (str(z), None)], tabs=tabs, pril=pril, hist=hist, z=z, items=items, foto=foto, dok=dok, nxt=request.path, zarizeni=z.zarizeni.all(),
             kontakty=z.zakazkakontakt_set.select_related("kontakt"), zam=z.zamestnanci.all(), ukony=ukony, mat=mat, sum_u=sum_u, sum_m=sum_m, platby=platby)

# ---------------- Nabídka ze zakázky ----------------
def nabidka_polozky(z):
    """Položky nabídky z provedených úkonů a použitého materiálu zakázky (ceny i DPH se berou ze zakázky)."""
    ns = NastaveniFirmy.objects.first(); dph0 = ns.vychozi_dph if ns and ns.vychozi_dph is not None else Decimal(21); out = []
    def add(popis, mn, j, cena, dph):
        cena = cena or Decimal(0); dph = dph if dph is not None else dph0; bez = round(mn * cena, 2)
        out.append(dict(popis=popis[:300], mnozstvi=mn, jednotka=j, cena=cena, dph=dph, bez=bez, s=round(bez * (1 + dph / 100), 2)))
    for u in z.provedenyukon_set.select_related("typ_ukonu"):
        add(u.typ_ukonu.nazev + (" – " + u.poznamka.splitlines()[0] if u.poznamka.strip() else ""), Decimal(1), "ks", u.cena, u.sazba_dph)
    for m in z.pouzitymaterial_set.select_related("material"): add(m.material.nazev, m.mnozstvi, m.material.jednotka or "ks", m.jednotkova_cena, m.sazba_dph)
    return out
def nahled_ctx(z):
    p = nabidka_polozky(z); b = sum(x["bez"] for x in p); s = sum(x["s"] for x in p)
    return {"z": z, "polozky": p, "sum_bez": b, "sum_s": s, "sum_dph": s - b}

class ZakazkaChoice(forms.ModelChoiceField):
    def label_from_instance(self, z): return f"{z.cislo_zakazky} – {z.zakaznik}"
class NabidkaForm(forms.Form):
    zakazka = ZakazkaChoice(Zakazka.objects.select_related("zakaznik").order_by("-datum_vytvoreni"), label="Zakázka", empty_label="— vyberte zakázku —")
    datum = forms.DateTimeField(label="Datum vystavení", input_formats=["%Y-%m-%dT%H:%M"],
                                widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}, format="%Y-%m-%dT%H:%M"))
    poznamka = forms.CharField(label="Poznámka (nepovinné)", required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["zakazka"].widget.attrs.update({"class": "form-select", "hx-get": reverse("nabidka_nahled"), "hx-target": "#nahled", "hx-trigger": "change"})

def nabidka_nova(request):
    z0 = Zakazka.objects.filter(pk=request.GET.get("zakazka") or 0).first()
    form = NabidkaForm(request.POST or None, initial={"zakazka": z0, "datum": timezone.localtime().strftime("%Y-%m-%dT%H:%M")})
    if request.method == "POST" and form.is_valid():
        z = form.cleaned_data["zakazka"]
        with transaction.atomic():
            n = Nabidka.objects.create(zakaznik=z.zakaznik, datum_vystaveni=form.cleaned_data["datum"], vypracoval=request.user,
                identifikacni_cislo=z.identifikacni_cislo, sekundarni_cislo=z.sekundarni_cislo, poznamka=form.cleaned_data["poznamka"])
            n.zakazky.add(z)
            for p in nabidka_polozky(z):
                PolozkaNabidky.objects.create(nabidka=n, zakazka=z, popis=p["popis"], mnozstvi=p["mnozstvi"], jednotka=p["jednotka"], jednotkova_cena=p["cena"], sazba_dph=p["dph"])
            log(request, n, "Vytvoření", popis_z=z)
        if z.stav and z.stav.nazev == "Nová": set_stav(request, z, "Čeká na schválení")  # nabídka čeká na schválení zákazníkem
        messages.success(request, f"Nabídka {n.cislo_nabidky} vytvořena ze zakázky {z.cislo_zakazky}.")
        nx = safe_next(request); return redirect(reverse("dokument", args=["nabidka", n.pk]) + ("?" + urlencode({"next": nx}) if nx else ""))  # rovnou náhled dokumentu
    z = form["zakazka"].value() and Zakazka.objects.filter(pk=form["zakazka"].value()).first()
    return R(request, "nabidka_nova", sec="dokumenty", form=form, nahled=nahled_ctx(z) if z else None)

def nabidka_nahled(request):
    z = Zakazka.objects.filter(pk=request.GET.get("zakazka") or 0).first()
    return render(request, "core/nabidka_nahled.html", nahled_ctx(z) if z else {})

# ---------------- Zákazníci ----------------
def zakaznik_detail(request, pk):
    z = get_object_or_404(Zakaznik, pk=pk)
    tabs = [("info", "Informace"), ("kont", "Kontaktní osoby"), ("zar", "Zařízení"), ("zak", "Zakázky"), ("dok", "Dokumenty"), ("hist", "Historie")]
    return R(request, "zakaznik_detail", sec="zakaznici", crumbs=[("👥 Zákazníci", reverse("list", args=["zakaznik"])), (str(z), None)], z=z, tabs=tabs, nxt=request.path,
        kontakty=z.zakaznikkontakt_set.select_related("kontakt"), zarizeni=z.zarizeni_set.annotate(n=Count("zakazka")), zakazky=z.zakazka_set.select_related("stav"),
        nabidky=z.nabidka_set.all(), objednavky=z.objednavka_set.all(), faktury=z.faktura_set.all(), hist=HistorieZmen.objects.filter(typ_objektu="zakaznik", id_objektu=pk)[:60])

# ---------------- Dokumenty ----------------
def dokumenty(request):
    typ = request.GET.get("typ", ""); q = request.GET.get("q", "").lower(); rows = []
    if typ in ("", "nabidka"): rows += [dict(typ="Nabídka", slug="nabidka", pk=n.pk, cislo=n.cislo_nabidky, zakaznik=n.zakaznik, datum=n.datum_vystaveni, castka=n.cena_s_dph) for n in Nabidka.objects.select_related("zakaznik")]
    if typ in ("", "objednavka"): rows += [dict(typ="Objednávka", slug="objednavka", pk=o.pk, cislo=o.cislo_objednavky, zakaznik=o.zakaznik, datum=o.datum_objednavky, castka=None) for o in Objednavka.objects.select_related("zakaznik")]
    if typ in ("", "faktura"): rows += [dict(typ="Faktura", slug="faktura", pk=f.pk, cislo=f.cislo_faktury, zakaznik=f.zakaznik, datum=f.datum_vystaveni, castka=f.cena_s_dph) for f in Faktura.objects.select_related("zakaznik")]
    if q: rows = [r for r in rows if q in (r["cislo"] + " " + str(r["zakaznik"])).lower()]
    rows.sort(key=lambda r: (str(r["datum"] or "")[:10], r["pk"]), reverse=True)
    return R(request, "dokumenty", sec="dokumenty", rows=rows, typ=typ, q=q, tabs=[("", "Vše"), ("nabidka", "Nabídky"), ("objednavka", "Objednávky"), ("faktura", "Faktury")])

# ---------------- Kalendář ----------------
MES = ["leden", "únor", "březen", "duben", "květen", "červen", "červenec", "srpen", "září", "říjen", "listopad", "prosinec"]
KCSS = {"Přijetí zakázky": "primary", "Vydání zařízení": "success", "Fakturováno": "warning text-dark", "Zaplaceno": "info text-dark"}
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
    qs = KalendarUdalost.objects.filter(datum__date__gte=start, datum__date__lt=end).select_related("zakazka", "faktura")
    if typ: qs = qs.filter(typ=typ)
    if zam: qs = qs.filter(zamestnanci__pk=zam)
    by = {}
    for e in qs.distinct().order_by("datum"):
        e.css = KCSS.get(e.typ, "secondary"); by.setdefault(timezone.localtime(e.datum).date(), []).append(e)
    today = timezone.localdate()
    days = [{"d": x, "ev": by.get(x, []), "today": x == today, "out": x.month != d.month} for x in (start + timedelta(i) for i in range((end - start).days))]
    qq = urlencode({k: x for k, x in (("typ", typ), ("zam", zam)) if x})
    return R(request, "kalendar", sec="kalendar", v=v, d=d, days=days, rows=[days[i:i + 7] for i in range(0, len(days), 7)] if v == "month" else None, title=title, prev=prev, nxt=nxt,
        today=today, typ=typ, zam=zam, qq=("&" + qq) if qq else "", modes=[("month", "Měsíc"), ("week", "Týden"), ("day", "Den")], wd=["Po", "Út", "St", "Čt", "Pá", "So", "Ne"],
        typy=[x[0] for x in KalendarUdalost._meta.get_field("typ").choices], zamestnanci=Zamestnanec.objects.filter(aktivni=True), nxtpath=request.get_full_path())

# ---------------- Nastavení ----------------
def nastaveni(request):
    L = lambda s: reverse("list", args=[s]); st = request.user.is_staff
    g = [("Firma", [("Údaje o firmě a logo", reverse("nastaveni_firma"))], ""),
         ("Dokumenty", [("Šablony dokumentů", reverse("sablony")), ("Značky pro vlastní šablony", reverse("sablony_znacky"))], "Vzhled zakázkových listů, nabídek a faktur (Excel, HTML) a výchozí šablona pro každý typ."),
         ("DPH", [("Sazby DPH", L("sazbadph"))], "Výchozí sazba DPH se nastavuje v části Firma."),
         ("Uživatelé a oprávnění", [("Zaměstnanci", L("zamestnanec")), ("Role", L("role")), ("Oprávnění", L("opravneni"))] + ([("Uživatelské účty", "/admin/auth/user/")] if st else []), ""),
         ("Katalogy", [("Stavy zakázek", L("stavzakazky")), ("Typy úkonů", L("typukonu")), ("Materiály", L("material"))], ""),
         ("Systém", [("Historie změn", L("historiezmen")), ("Zálohování", reverse("nastaveni_zaloha"))] + ([("Obecná nastavení (Django admin)", "/admin/")] if st else []), "")]
    return R(request, "nastaveni", sec="nastaveni", groups=g)
def nastaveni_firma(request):
    o = NastaveniFirmy.objects.first() or NastaveniFirmy.objects.create(nazev_firmy="Moje firma")
    return redirect(reverse("edit", args=["nastavenifirmy", o.pk]) + "?next=" + reverse("nastaveni"))
def nastaveni_zaloha(request):
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
    rows = []
    for d in qs:
        z = d.zz[0] if d.zz else None; st = z.stav.nazev if z and z.stav else ""; otevrena = bool(z) and st not in CLOSED
        if not {"firma": otevrena, "oprava": st in ("Rozpracováno", "Opraveno"), "dil": st == "Čeká na díl", "zakaznik": bool(z) and not otevrena, "bez": not z}.get(f, True): continue
        stav = st or ("Bez zakázky" if not z else "–")
        if (fs and stav != fs) or (fi == "ano" and not otevrena) or (fi == "ne" and otevrena): continue
        rows.append(dict(d=d, z=z, stav=stav, css=STAV_CSS.get(st, "light text-dark border"), n=len(d.zz), firma=otevrena,
                         prijeti=z.datum_prijeti if z else None, akce=_zar_posledni_akce(d, hist)))
    far = timezone.make_aware(datetime(1900, 1, 1))
    sk = {"zarizeni": lambda r: f"{r['d'].vyrobce} {r['d'].typ}".lower(), "zakaznik": lambda r: str(r["d"].zakaznik).lower(), "telefon": lambda r: r["d"].zakaznik.telefon or "",
          "stav": lambda r: r["stav"].lower(), "prijeti": lambda r: r["prijeti"] or far, "akce": lambda r: r["akce"] or far}[key]
    rows.sort(key=sk, reverse=desc)
    heads = [(k, l, ("" if desc or k != key else "-") + k, ("▼" if desc else "▲") if k == key else "") for k, l in ZAR_RAZENI.items()]
    stavy = list(StavZakazky.objects.filter(aktivni=True).values_list("nazev", flat=True)) + ["Bez zakázky"]
    keep = urlencode({k: x for k, x in (("q", q), ("f", f), ("st", fs), ("fi", fi)) if x})
    return R(request, "zarizeni_prehled", sec="zarizeni", crumbs=None, rows=rows, f=f, q=q, o=o, heads=heads, filtry=ZAR_FILTRY, stavy=stavy, fs=fs, fi=fi, keep=keep)
def zarizeni_detail(request, pk):
    d = get_object_or_404(Zarizeni.objects.select_related("zakaznik"), pk=pk)
    zak = list(d.zakazka_set.select_related("stav").prefetch_related("zamestnanci", Prefetch("provedenyukon_set", queryset=ProvedenyUkon.objects.select_related("typ_ukonu").prefetch_related("zamestnanci")),
               Prefetch("pouzitymaterial_set", queryset=PouzityMaterial.objects.select_related("material")), "zakazkakontakt_set__kontakt").order_by("-datum_prijeti", "-datum_vytvoreni"))
    for z in zak:
        z.css = STAV_CSS.get(z.stav.nazev if z.stav else "", "info text-dark"); z.otevrena = not (z.stav and z.stav.nazev in CLOSED)
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
STAV_CSS = {"Nová": "secondary", "Rozpracováno": "primary", "Čeká na schválení": "warning text-dark", "Čeká na díl": "warning text-dark", "Opraveno": "success",
            "Připraveno k vyzvednutí": "success", "Vydáno": "dark", "Zrušeno": "danger"}
def stav_by_name(n): return StavZakazky.objects.filter(nazev=n).first() or StavZakazky.objects.create(nazev=n, poradi=99)
def can_set_stav(user):
    if user.is_superuser or user.is_staff: return True
    e = Zamestnanec.objects.filter(uzivatel=user).first()
    return bool(e) and e.role.filter(Q(je_administrator=True) | Q(opravneni__kod="zakazky.zmenit_stav"), aktivni=True).exists()
def stav_ctx(request, z):
    n = z.stav.nazev if z.stav else ""; akce = []
    for k in FLOW.get(n, ["zahajit", "zrusit"]):
        l, _, s = ACTIONS[k]; akce.append((k, {("Čeká na schválení", "zahajit"): "Schváleno – zahájit práci", ("Čeká na díl", "zahajit"): "Díl dorazil – zahájit práci"}.get((n, k), l), s))
    return dict(akce=akce, moze_stav=can_set_stav(request.user), stavy=StavZakazky.objects.filter(aktivni=True), stav_css=STAV_CSS.get(n, "info text-dark"))
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
