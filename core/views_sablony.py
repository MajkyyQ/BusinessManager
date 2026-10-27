"""Šablony dokumentů: správa v Nastavení, náhled dokumentu, výběr šablony, PDF a tisk."""
from pathlib import Path
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from .models import SablonaDokumentu as S
from .sablony import prevod, renderery, typy
from .views import R, log, safe_next

CRUMBS = [("⚙ Nastavení", "/nastaveni/"), ("Dokumenty", None)]


def _typ(kod):
    t = typy.typ(kod)
    if not t: raise Http404
    return t


def vychozi_sablona(kod):
    q = S.objects.filter(typ_dokumentu=kod, aktivni=True)
    return q.filter(vychozi=True).first() or q.first()


def vyber_sablonu(request, kod):
    """Šablona z adresy (?sablona=), jinak výchozí. Volba v náhledu NEMĚNÍ výchozí šablonu."""
    pk = request.GET.get("sablona") or request.POST.get("sablona")
    s = S.objects.filter(pk=pk, typ_dokumentu=kod).first() if pk and str(pk).isdigit() else None
    return s or vychozi_sablona(kod)


def zajisti_miniaturu(s):
    """Miniatura šablony s ukázkovými daty (vytvoří se jednou pro každou verzi šablony)."""
    st = s.nahled.storage
    if s.nahled and st.exists(s.nahled.name): return True
    t = typy.typ(s.typ_dokumentu)
    if not t: return False
    try:
        png = prevod.miniatura(renderery.renderer(s).pdf(s, t, t.ukazka()))
    except Exception:
        return False
    if not png: return False
    jmeno = st.save(f"sablony/nahledy/sablona_{s.pk}_v{s.verze}.png", ContentFile(png))
    S.objects.filter(pk=s.pk).update(nahled=jmeno); s.nahled.name = jmeno
    return True


def _znovu_analyzovat(s):
    t = typy.typ(s.typ_dokumentu); r = renderery.renderer(s)
    s.mapovani = r.analyzuj(s, t) if t else {}
    if s.nahled:
        s.nahled.delete(save=False)
    s.nahled = ""


# ======================================================== Nastavení → Dokumenty
def sablony_seznam(request):
    kod = request.GET.get("typ", "")
    q = S.objects.all()
    if kod: q = q.filter(typ_dokumentu=kod)
    if not request.GET.get("vse"): q = q.filter(aktivni=True)
    skupiny = []
    for k, t in typy.REGISTR.items():
        if kod and k != kod: continue
        skupiny.append((t, [s for s in q if s.typ_dokumentu == k]))
    tabs = [("Vše", "?", not kod)] + [(t.nazev_mn, f"?typ={k}", kod == k) for k, t in typy.REGISTR.items()]
    return R(request, "sablony/seznam", sec="nastaveni", crumbs=CRUMBS + [("Šablony dokumentů", None)], skupiny=skupiny, kod=kod,
             subtabs=[(l, u + ("&vse=1" if request.GET.get("vse") else ""), a) for l, u, a in tabs], vse=request.GET.get("vse"),
             lo=bool(prevod.soffice()))


class SablonaForm(forms.ModelForm):
    class Meta:
        model = S; fields = ["nazev", "typ_dokumentu", "soubor", "popis", "vychozi", "aktivni"]
        labels = {"vychozi": "Nastavit jako výchozí šablonu pro tento typ dokumentu", "aktivni": "Aktivní (nabízí se při výběru šablony)"}
        widgets = {"popis": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["typ_dokumentu"] = forms.ChoiceField(label="Typ dokumentu", choices=typy.volby())
        pr = ", ".join("." + p for r in renderery.REGISTR.values() for p in r.pripony)
        self.fields["soubor"].help_text = f"Podporované formáty: {pr}. Excel může obsahovat značky {{{{...}}}}, jinak se pole zkusí rozpoznat podle popisků."
        if self.instance.pk and self.instance.vestavena:
            del self.fields["soubor"]
            self.fields["typ_dokumentu"].disabled = True
        elif not self.instance.pk:
            self.fields["soubor"].required = True; del self.fields["aktivni"]
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-check-input" if isinstance(f.widget, forms.CheckboxInput) else "form-control")
        if "typ_dokumentu" in self.fields: self.fields["typ_dokumentu"].widget.attrs["class"] = "form-select"

    def clean_soubor(self):
        f = self.cleaned_data.get("soubor")
        if f and hasattr(f, "name") and "soubor" in self.changed_data and not renderery.podle_pripony(f.name):
            raise forms.ValidationError("Tento formát šablony zatím není podporován.")
        return f


def sablona_edit(request, pk=None):
    s = get_object_or_404(S, pk=pk) if pk else None
    init = {"typ_dokumentu": request.GET.get("typ")} if not s else None
    form = SablonaForm(request.POST or None, request.FILES or None, instance=s, initial=init)
    if request.method == "POST" and form.is_valid():
        o = form.save(commit=False)
        novy_soubor = "soubor" in form.changed_data or (s and "typ_dokumentu" in form.changed_data)
        if novy_soubor:
            if o.soubor: o.format = renderery.podle_pripony(o.soubor.name).kod
            if s: o.verze += 1
        o.save()
        if novy_soubor and o.soubor and o.soubor.name.lower().endswith(".xls"):  # starý Excel -> .xlsx (openpyxl umí jen nový formát)
            try:
                data = prevod.na_xlsx(o.soubor.path); stary = o.soubor.name
                o.soubor.save(Path(stary).stem + ".xlsx", ContentFile(data), save=True); o.soubor.storage.delete(stary)
                messages.info(request, "Soubor ve starém formátu .xls byl převeden na .xlsx.")
            except Exception as e:
                messages.error(request, f"Soubor .xls se nepodařilo převést na .xlsx ({e}). Uložte ho v Excelu jako .xlsx a nahrajte znovu.")
        if novy_soubor:
            try:
                _znovu_analyzovat(o); o.save()
            except Exception as e:
                messages.error(request, f"Soubor se nepodařilo načíst: {e}")
        log(request, o, "Vytvoření" if not s else "Úprava")
        messages.success(request, "Šablona uložena." + (" Zkontrolujte rozpoznaná pole." if novy_soubor else ""))
        return redirect("sablona_detail", pk=o.pk)
    t = "Nová šablona" if not s else f"Upravit: {s}"
    return R(request, "sablony/form", sec="nastaveni", crumbs=CRUMBS + [("Šablony dokumentů", reverse("sablony")), (t, None)], form=form, s=s, titulek=t)


def sablona_detail(request, pk):
    s = get_object_or_404(S, pk=pk); t = typy.typ(s.typ_dokumentu)
    pd = t.pole_dict() if t else {}
    m = s.mapovani or {}
    znacky = [(z, pd.get(z["pole"])) for z in m.get("znacky", [])]
    pole = [(f, pd.get(f["pole"])) for f in m.get("pole", [])]
    tabulky = [(x, [(c, pd.get(k)) for c, k in sorted(x.get("sloupce", {}).items())]) for x in m.get("tabulky", [])]
    return R(request, "sablony/detail", sec="nastaveni", crumbs=CRUMBS + [("Šablony dokumentů", reverse("sablony")), (str(s), None)],
             s=s, typ=t, znacky=znacky, pole=pole, tabulky=tabulky, nezname=m.get("nezname_znacky", []), listy=m.get("listy", []),
             renderer=renderery.renderer(s), lo=bool(prevod.soffice()))


@require_POST
def sablona_akce(request, pk, akce):
    s = get_object_or_404(S, pk=pk)
    if akce == "vychozi":
        s.vychozi = True; s.aktivni = True; s.save(); messages.success(request, f"„{s}“ je nyní výchozí šablona ({typy.typ(s.typ_dokumentu).nazev}).")
    elif akce == "deaktivovat":
        s.aktivni = False; s.vychozi = False; s.save(); messages.success(request, f"Šablona „{s}“ byla deaktivována.")
        if not vychozi_sablona(s.typ_dokumentu): messages.warning(request, "Pro tento typ dokumentu nezbyla žádná aktivní šablona.")
        elif not S.objects.filter(typ_dokumentu=s.typ_dokumentu, aktivni=True, vychozi=True).exists():
            n = vychozi_sablona(s.typ_dokumentu); n.vychozi = True; n.save(); messages.info(request, f"Výchozí šablonou se stala „{n}“.")
    elif akce == "aktivovat":
        s.aktivni = True; s.save(); messages.success(request, f"Šablona „{s}“ je opět aktivní.")
    elif akce == "analyzovat":
        _znovu_analyzovat(s); s.save(); messages.success(request, "Šablona byla znovu načtena a pole znovu rozpoznána.")
    elif akce == "kopie":
        n = S.objects.create(nazev=f"{s.nazev} (kopie)", typ_dokumentu=s.typ_dokumentu, format=s.format, vestavena=s.vestavena,
                             mapovani=s.mapovani, popis=s.popis)
        if s.soubor:
            n.soubor.save(Path(s.soubor.name).name, ContentFile(s.soubor.read()), save=True)
        messages.success(request, "Vytvořena kopie šablony."); return redirect("sablona_detail", pk=n.pk)
    else:
        raise Http404
    log(request, s, "Úprava", "šablona", "", akce)
    return redirect(safe_next(request) or reverse("sablona_detail", args=[s.pk]))


def sablona_miniatura(request, pk):
    s = get_object_or_404(S, pk=pk)
    if zajisti_miniaturu(s):
        r = HttpResponse(s.nahled.read(), content_type="image/png"); r["Cache-Control"] = "private, max-age=86400"; return r
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="420" height="594"><rect width="100%" height="100%" fill="#f8f9fa" stroke="#ccc"/>'
           '<text x="50%" y="48%" text-anchor="middle" font-family="Arial" font-size="20" fill="#888">Náhled není k dispozici</text>'
           '<text x="50%" y="54%" text-anchor="middle" font-family="Arial" font-size="14" fill="#aaa">(chybí LibreOffice)</text></svg>')
    return HttpResponse(svg, content_type="image/svg+xml")


@xframe_options_sameorigin
def sablona_ukazka(request, pk):
    """Šablona vyplněná ukázkovými daty (pro kontrolu v Nastavení)."""
    s = get_object_or_404(S, pk=pk); t = _typ(s.typ_dokumentu)
    return _obsah(s, t, t.ukazka(), request.GET.get("pdf"))


def sablona_stahnout(request, pk):
    s = get_object_or_404(S, pk=pk); p = renderery.cesta_souboru(s)
    if not p or not p.exists(): raise Http404
    r = HttpResponse(p.read_bytes(), content_type="application/octet-stream")
    r["Content-Disposition"] = f'attachment; filename="{slugify(s.nazev) or "sablona"}{p.suffix}"'; return r


def sablony_znacky(request):
    """Nápověda: seznam značek pro vlastní šablony + ke stažení vestavěné vzory."""
    kod = request.GET.get("typ") or next(iter(typy.REGISTR))
    t = _typ(kod); skupiny = {}
    for p in t.pole(): skupiny.setdefault(p.skupina, []).append(p)
    vzory = S.objects.filter(typ_dokumentu=kod, format="excel").exclude(vestavena="")
    return R(request, "sablony/znacky", sec="nastaveni", crumbs=CRUMBS + [("Šablony dokumentů", reverse("sablony")), ("Značky pro vlastní šablony", None)],
             typ=t, skupiny=skupiny.items(), vzory=vzory, subtabs=[(x.nazev, f"?typ={k}", k == kod) for k, x in typy.REGISTR.items()])


# ======================================================== Náhled dokumentu
def _objekt(kod, pk):
    t = _typ(kod)
    try:
        return t, t.objekt(pk)
    except Exception:
        raise Http404


def _chyba_html(text):
    return HttpResponse(f'<!doctype html><meta charset="utf-8"><div style="font:15px Arial;padding:30px;color:#842029;background:#f8d7da">{text}</div>',
                        content_type="text/html; charset=utf-8")


def _obsah(s, t, data, jako_pdf=False):
    if not s: return _chyba_html("Pro tento typ dokumentu není žádná aktivní šablona. Přidejte ji v Nastavení → Dokumenty.")
    r = renderery.renderer(s)
    try:
        ct, body = ("application/pdf", r.pdf(s, t, data)) if jako_pdf else r.nahled(s, t, data)
    except prevod.ChybiLibreOffice as e:
        return _chyba_html(f"{e}<br><br>Mezitím můžete použít šablonu ve formátu HTML (tlačítko Změnit šablonu).")
    except Exception as e:
        return _chyba_html(f"Dokument se nepodařilo vytvořit ze šablony „{s}“: {e}")
    resp = HttpResponse(body, content_type=ct)
    if ct == "application/pdf": resp["Content-Disposition"] = "inline"
    return resp


def dokument(request, typ, pk):
    t, o = _objekt(typ, pk); s = vyber_sablonu(request, typ)
    q = f"?sablona={s.pk}" if s else ""
    nx = safe_next(request) or ""
    zpet = nx or (reverse("plocha", args=[pk]) if typ == "zakazkovy_list" else reverse("detail", args=[typ, pk]))
    ostatni = S.objects.filter(typ_dokumentu=typ, aktivni=True).count()
    return R(request, "sablony/nahled", sec="zakazky" if typ == "zakazkovy_list" else "dokumenty", crumbs=[(t.titulek(o), zpet), ("Náhled", None)],
             t=t, o=o, s=s, typ=typ, pk=pk, q=q, zpet=zpet, nx=nx, titulek=t.titulek(o), ostatni=ostatni,
             je_pdf=bool(s) and renderery.renderer(s).nahled_typ == "application/pdf")


@xframe_options_sameorigin
def dokument_obsah(request, typ, pk):
    t, o = _objekt(typ, pk)
    return _obsah(vyber_sablonu(request, typ), t, t.data(o))


def dokument_pdf(request, typ, pk):
    t, o = _objekt(typ, pk); s = vyber_sablonu(request, typ)
    r = _obsah(s, t, t.data(o), jako_pdf=True)
    if r["Content-Type"] == "application/pdf":
        r["Content-Disposition"] = f'attachment; filename="{t.nazev_souboru(o) or "dokument"}.pdf"'
    return r


def dokument_sablony(request, typ, pk):
    """Výběr šablony: miniatury vedle sebe, zvětšení, kliknutím se šablona použije (jen pro tento náhled)."""
    t, o = _objekt(typ, pk); akt = vyber_sablonu(request, typ)
    nx = safe_next(request) or ""
    sab = list(S.objects.filter(typ_dokumentu=typ, aktivni=True).order_by("-vychozi", "nazev"))
    zpet = reverse("dokument", args=[typ, pk]) + "?" + urlencode({k: v for k, v in (("sablona", akt.pk if akt else ""), ("next", nx)) if v})
    return R(request, "sablony/vyber", sec="zakazky" if typ == "zakazkovy_list" else "dokumenty",
             crumbs=[(t.titulek(o), zpet), ("Změnit šablonu", None)], t=t, o=o, typ=typ, pk=pk, sab=sab, akt=akt, zpet=zpet, nx=nx, titulek=t.titulek(o))
