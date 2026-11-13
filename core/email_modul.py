"""Modul Odesílání e-mailů: dokumenty, fotografie a přílohy zakázky odeslané e-mailem přímo z aplikace.

Modul je volitelný a jako jediná část aplikace potřebuje připojení k internetu. Bez vyplněného
Nastavení → E-mail se nic neodesílá a zbytek aplikace funguje dál bez internetu.

Postup: zaměstnanec vybere zakázku, aplikace nabídne všechno, co k ní patří (zakázkový list, nabídky, faktury
jako PDF podle výchozí šablony, faktury i ve formátu ISDOC, fotografie a přílohy), zaměstnanec zaškrtne, co chce
poslat, napíše příjemce, předmět a text, aplikace připojí podpis firmy a e-mail odešle přes SMTP server firmy.
Odeslání se zapíše do tabulky OdeslanyEmail a do historie zakázky."""
import mimetypes
import re
import smtplib
import socket
from pathlib import Path

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.shortcuts import redirect
from django.urls import reverse

from . import prava as P
from .models import (Faktura, Fotografie, HistorieZmen, Nabidka, NastaveniEmailu, NastaveniFirmy, OdeslanyEmail, Priloha, Zakazka,
                     Zamestnanec, formatuj_telefon)

MAX_VELIKOST = 18 * 1024 * 1024  # součet příloh; běžné schránky berou 20–25 MB a kódování příloh přidá zhruba třetinu
TIMEOUT = 20  # sekund na spojení se serverem, aby stránka bez internetu nečekala dlouho


class ChybaOdeslani(Exception):
    """Srozumitelná chyba pro uživatele (bez technických podrobností)."""


# ======================================================== Podpis
def _zamestnanec(user): return Zamestnanec.objects.filter(uzivatel=user).first() if user and user.is_authenticated else None


def hodnoty_podpisu(user):
    f = NastaveniFirmy.objects.first(); z = _zamestnanec(user)
    jmeno = (str(z) if z else "") or (user.get_full_name() if user else "") or (user.username if user else "")
    return {"pracovnik": jmeno, "pozice": z.pracovni_pozice if z else "",
            "firma": f.nazev_firmy if f else "", "adresa": f.adresa if f else "", "web": f.web if f else "", "ico": f.ico if f else "",
            "telefon": formatuj_telefon((z.telefon if z else "") or (f.telefon if f else "")),
            "email": (z.email if z else "") or (f.email if f else "")}


def podpis(n, user):
    """Podpis e-mailu s doplněnými značkami {pracovnik}, {firma}… Řádky, ve kterých zůstala jen prázdná hodnota, se vynechají."""
    sablona = (n.podpis if n and n.podpis else NastaveniEmailu.VYCHOZI_PODPIS).replace("\r\n", "\n")
    h = hodnoty_podpisu(user); out = []
    for radek in sablona.split("\n"):
        znacky = re.findall(r"\{(\w+)\}", radek)
        vyplneny = re.sub(r"\{(\w+)\}", lambda m: h.get(m.group(1), m.group(0)), radek)
        if znacky and all(not h.get(k) for k in znacky if k in h) and any(k in h for k in znacky):
            continue  # např. „Tel.: {telefon}“ bez telefonu
        out.append(vyplneny)
    return "\n".join(out).strip("\n")


# ======================================================== Co lze k zakázce přiložit
def _velikost(soubor):
    try: return soubor.size
    except (OSError, ValueError): return None


def prilohy_zakazky(z, user):
    """Seznam souborů, které lze k zakázce poslat. Doklady vidí jen ten, kdo s nimi smí pracovat (stejně jako na pracovní ploše)."""
    pr = P.prava(user); out = []
    def add(skupina, klic, nazev, velikost=None, poznamka=""):
        out.append(dict(skupina=skupina, klic=klic, nazev=nazev, velikost=velikost, poznamka=poznamka))
    add("Dokumenty", f"dok:zakazkovy_list:{z.pk}", f"Zakázkový list {z.cislo_zakazky} (PDF)")
    if P.NABIDKY in pr:
        for n in z.nabidka_set.order_by("pk"): add("Dokumenty", f"dok:nabidka:{n.pk}", f"Nabídka {n.cislo_nabidky} (PDF)")
    if P.FAKTURY in pr:
        for f in z.faktura_set.order_by("pk"):
            add("Dokumenty", f"dok:faktura:{f.pk}", f"Faktura {f.cislo_faktury} (PDF)")
            add("Dokumenty", f"isdoc:faktura:{f.pk}", f"Faktura {f.cislo_faktury} (ISDOC pro účetní program)")
    if P.NABIDKY in pr:
        for o in z.objednavka_set.select_related("priloha"):
            if o.priloha and o.priloha.soubor: add("Dokumenty", f"pril:{o.priloha.pk}", f"{o} – {Path(o.priloha.soubor.name).name}", _velikost(o.priloha.soubor))
    for f in z.fotografie_set.order_by("pk"):
        add("Fotografie", f"foto:{f.pk}", f.popis[:60] or Path(f.soubor.name).name, _velikost(f.soubor))
    for p in z.priloha_set.order_by("pk"):
        if not any(x["klic"] == f"pril:{p.pk}" for x in out): add("Přílohy", f"pril:{p.pk}", p.nazev, _velikost(p.soubor))
    return out


def _pdf(typ, obj):
    from .sablony import prevod, renderery, typy
    from .views_sablony import vychozi_sablona
    t = typy.typ(typ); s = vychozi_sablona(typ)
    if not s: raise ChybaOdeslani(f"Pro dokument „{t.nazev}“ není žádná aktivní šablona (Dokumenty → Šablony dokumentů).")
    try:
        return f"{t.nazev_souboru(obj) or typ}.pdf", renderery.renderer(s).pdf(s, t, t.data(obj)), "application/pdf"
    except prevod.ChybiLibreOffice:
        raise ChybaOdeslani(f"{t.titulek(obj)}: PDF nejde vytvořit, protože chybí LibreOffice. Zvolte jako výchozí šablonu HTML, nebo dokument neposílejte.")
    except Exception as e:
        raise ChybaOdeslani(f"{t.titulek(obj)}: PDF se nepodařilo vytvořit ({e}).")


def _soubor(f, nazev=None):
    try:
        with f.open("rb") as h: data = h.read()
    except (OSError, ValueError):
        raise ChybaOdeslani(f"Soubor {Path(f.name).name} se nepodařilo načíst, na disku chybí.")
    jmeno = Path(f.name).name
    if nazev:  # název přílohy z aplikace + původní přípona
        jmeno = re.sub(r'[\\/:*?"<>|]+', "_", nazev).strip() or jmeno
        if not Path(jmeno).suffix: jmeno += Path(f.name).suffix
    return jmeno, data, mimetypes.guess_type(f.name)[0] or "application/octet-stream"


def nacti(klic, z, user):
    """Soubor přílohy podle klíče z formuláře: (název, obsah, typ). Klíč musí patřit k zakázce a uživatel musí mít oprávnění."""
    povolene = {x["klic"] for x in prilohy_zakazky(z, user)}
    if klic not in povolene: raise ChybaOdeslani("Vybraný soubor k této zakázce nepatří.")
    druh, _, zbytek = klic.partition(":")
    if druh == "dok":
        typ, _, pk = zbytek.partition(":")
        obj = {"zakazkovy_list": Zakazka, "nabidka": Nabidka, "faktura": Faktura}[typ].objects.get(pk=pk)
        return _pdf(typ, obj)
    if druh == "isdoc":
        from .sablony import isdoc
        f = Faktura.objects.get(pk=zbytek.partition(":")[2])
        try: return f"{f.cislo_faktury}.isdoc".replace("/", "_"), isdoc.faktura_isdoc(f), "application/xml"
        except isdoc.NeplatneISDOC as e: raise ChybaOdeslani(f"Fakturu {f.cislo_faktury} nejde převést do ISDOC: {e}")
    if druh == "foto": return _soubor(Fotografie.objects.get(pk=zbytek).soubor)
    if druh == "pril":
        p = Priloha.objects.get(pk=zbytek); return _soubor(p.soubor, p.nazev)
    raise ChybaOdeslani("Neznámý typ přílohy.")


# ======================================================== Odeslání
def pripojeni(n):
    return get_connection(host=n.smtp_server, port=n.port, username=n.uzivatel or None, password=n.heslo or None,
                          use_tls=n.sifrovani == "tls", use_ssl=n.sifrovani == "ssl", timeout=TIMEOUT)


def odesilatel(n):
    jmeno = n.odesilatel_jmeno or (NastaveniFirmy.objects.first() or NastaveniFirmy()).nazev_firmy
    jmeno = jmeno.replace('"', "'")
    return f'"{jmeno}" <{n.odesilatel_email}>' if jmeno else n.odesilatel_email


def srozumitelna_chyba(e):
    """Technická chyba SMTP jako věta pro uživatele: co se stalo a co s tím."""
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return "Server odmítl přihlášení. Zkontrolujte jméno a heslo v Nastavení → E-mail (u Gmailu a Microsoftu 365 je potřeba heslo aplikace)."
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "Server odmítl adresu příjemce. Zkontrolujte, že je e-mail příjemce napsaný správně."
    if isinstance(e, smtplib.SMTPSenderRefused):
        return "Server odmítl adresu odesílatele. E-mail odesílatele musí patřit k přihlašovacímu účtu."
    if isinstance(e, smtplib.SMTPDataError) and e.smtp_code == 552:
        return "Server e-mail odmítl, protože je příliš velký. Pošlete méně příloh nebo menší fotografie."
    if isinstance(e, (socket.gaierror, ConnectionRefusedError, TimeoutError, socket.timeout, OSError)) and not isinstance(e, smtplib.SMTPException):
        return ("Nepodařilo se spojit s poštovním serverem. Je počítač s aplikací připojený k internetu? "
                "Zkontrolujte také server, port a šifrování v Nastavení → E-mail.")
    return f"E-mail se nepodařilo odeslat: {e}"


def adresy(text):
    """Seznam adres z políčka (oddělené čárkou, středníkem nebo mezerou). Neplatná adresa = ValidationError."""
    out = [a for a in re.split(r"[,;\s]+", text or "") if a]
    for a in out:
        try: validate_email(a)
        except ValidationError: raise ValidationError(f"„{a}“ není platný e-mail.")
    return out


def odeslat(n, user, komu, kopie, predmet, text, soubory, z=None):
    """Sestaví a odešle e-mail. soubory = [(název, obsah, typ)]. Vrací záznam OdeslanyEmail, při chybě ChybaOdeslani."""
    bcc = [n.odesilatel_email] if n.kopie_odesilateli else []
    telo = text.rstrip() + "\n\n" + podpis(n, user)
    m = EmailMessage(subject=predmet, body=telo, from_email=odesilatel(n), to=komu, cc=kopie, bcc=bcc, connection=pripojeni(n))
    zam = _zamestnanec(user)
    if zam and zam.email: m.reply_to = [zam.email]  # odpověď zákazníka přijde přímo pracovníkovi
    for jmeno, data, typ in soubory: m.attach(jmeno, data, typ)
    try:
        m.send()
    except Exception as e:
        raise ChybaOdeslani(srozumitelna_chyba(e))
    zaznam = OdeslanyEmail.objects.create(zakazka=z, komu=", ".join(komu), kopie=", ".join(kopie), predmet=predmet[:200], text=telo,
                                          prilohy="\n".join(s[0] for s in soubory), odeslal=user)
    if z:
        HistorieZmen.objects.create(uzivatel=user, typ_objektu="zakazka", id_objektu=z.pk, akce="odeslán e-mail", pole="e-mail",
                                    nova_hodnota=f"{', '.join(komu)}: {predmet}" + (f" ({len(soubory)} příloh)" if soubory else ""),
                                    popis=str(z)[:200])
    return zaznam


# ======================================================== Stránky
class NastaveniEmailuForm(forms.ModelForm):
    class Meta:
        model = NastaveniEmailu
        fields = ["odesilatel_email", "odesilatel_jmeno", "smtp_server", "port", "sifrovani", "uzivatel", "heslo", "kopie_odesilateli", "podpis"]
        widgets = {"heslo": forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
                   "podpis": forms.Textarea(attrs={"rows": 9, "class": "font-monospace"})}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-check-input" if isinstance(f.widget, forms.CheckboxInput) else "form-select" if isinstance(f.widget, forms.Select) else "form-control")
        if self.instance.pk and self.instance.heslo:
            self.fields["heslo"].help_text = "Heslo je uložené. Nové napište jen tehdy, když ho chcete změnit."

    def clean_heslo(self):  # prázdné políčko = ponechat uložené heslo
        return self.cleaned_data.get("heslo") or (self.instance.heslo if self.instance.pk else "")

    def clean(self):
        c = super().clean()
        if c.get("smtp_server") and not c.get("odesilatel_email"): self.add_error("odesilatel_email", "Vyplňte e-mail odesílatele.")
        if c.get("odesilatel_email") and not c.get("smtp_server"): self.add_error("smtp_server", "Vyplňte server odchozí pošty.")
        return c


def nastaveni_email(request):
    """Nastavení → Moduly → E-mail: schránka, ze které se odesílá, a podpis."""
    from .views import R, jen_admin_ok, log
    if not jen_admin_ok(request): return redirect("dashboard")
    n = NastaveniEmailu.aktualni() or NastaveniEmailu()
    if not n.pk and not n.podpis: n.podpis = NastaveniEmailu.VYCHOZI_PODPIS
    form = NastaveniEmailuForm(request.POST or None, instance=n)
    if request.method == "POST" and form.is_valid():
        n = form.save(); log(request, n, "upraveno", popis_z=None)
        if request.POST.get("zkouska"):
            if not n.je_nastaveno():
                messages.error(request, "Zkušební e-mail nejde odeslat, vyplňte server a e-mail odesílatele.")
            else:
                try:
                    odeslat(n, request.user, [n.odesilatel_email], [], "Zkušební e-mail z aplikace BusinessManager",
                            "Dobrý den,\n\ntoto je zkušební e-mail. Odesílání e-mailů z aplikace funguje.", [])
                    messages.success(request, f"Nastavení je uložené a zkušební e-mail byl odeslán na {n.odesilatel_email}.")
                except ChybaOdeslani as e:
                    messages.error(request, f"Nastavení je uložené, ale zkušební e-mail se nepodařilo odeslat. {e}")
                return redirect("nastaveni_email")
        else:
            messages.success(request, "Nastavení e-mailu je uložené.")
        return redirect("nastaveni_email")
    return R(request, "email_nastaveni", sec="nastaveni", crumbs=[("⚙ Nastavení", reverse("nastaveni")), ("Moduly", None), ("E-mail", None)],
             form=form, n=n, znacky=NastaveniEmailu.ZNACKY, ukazka=podpis(n, request.user))


def _velikost_text(b):
    if b is None: return ""
    return f"{b / 1024 / 1024:.1f} MB" if b >= 1024 * 1024 else f"{max(1, round(b / 1024))} kB"


def email_odeslat(request):
    """Odeslání e-mailu se soubory zakázky. ?zakazka=<pk> vybere zakázku, ?vybrat=<klíč> předem zaškrtne soubor."""
    from .views import R, safe_next
    n = NastaveniEmailu.aktualni(); nastaveno = bool(n and n.je_nastaveno())
    src = request.POST if request.method == "POST" else request.GET
    zpk = src.get("zakazka", "")
    z = Zakazka.objects.select_related("zakaznik").filter(pk=zpk).first() if zpk.isdigit() else None
    soubory = prilohy_zakazky(z, request.user) if z else []
    for s in soubory: s["velikost_text"] = _velikost_text(s["velikost"])
    kontakty = []
    if z:
        if z.zakaznik.email: kontakty.append((str(z.zakaznik), z.zakaznik.email))
        for k in z.zakazkakontakt_set.select_related("kontakt"):
            if k.kontakt.email and k.kontakt.email not in [e for _, e in kontakty]: kontakty.append((str(k.kontakt), k.kontakt.email))
        for zk in z.zakaznik.zakaznikkontakt_set.select_related("kontakt"):
            if zk.kontakt.email and zk.kontakt.email not in [e for _, e in kontakty]: kontakty.append((str(zk.kontakt), zk.kontakt.email))
    hodnoty = {"komu": kontakty[0][1] if kontakty else "", "kopie": "", "predmet": f"Zakázka {z.cislo_zakazky}" if z else "",
               "text": "Dobrý den,\n\nv příloze Vám zasíláme dokumenty k zakázce.\n", "vybrane": request.GET.getlist("vybrat")}
    chyby = {}; nx = safe_next(request) or (reverse("plocha", args=[z.pk]) if z else reverse("dashboard"))
    if request.method == "POST" and request.POST.get("odeslat"):
        hodnoty = {k: request.POST.get(k, "").strip() for k in ("komu", "kopie", "predmet")}
        hodnoty["text"] = request.POST.get("text", ""); hodnoty["vybrane"] = request.POST.getlist("soubor")
        if not nastaveno: chyby["obecne"] = "Odesílání e-mailů není nastavené (Nastavení → E-mail)."
        if not z: chyby["zakazka"] = "Vyberte zakázku."
        try:
            komu = adresy(hodnoty["komu"])
            if not komu: chyby["komu"] = "Napište e-mail příjemce."
        except ValidationError as e: chyby["komu"] = e.messages[0]; komu = []
        try: kopie = adresy(hodnoty["kopie"])
        except ValidationError as e: chyby["kopie"] = e.messages[0]; kopie = []
        if not hodnoty["predmet"]: chyby["predmet"] = "Napište předmět e-mailu."
        if not chyby:
            try:
                prilozene = [nacti(k, z, request.user) for k in dict.fromkeys(hodnoty["vybrane"])]
                if sum(len(d) for _, d, _ in prilozene) > MAX_VELIKOST:
                    raise ChybaOdeslani(f"Přílohy mají dohromady víc než {MAX_VELIKOST // 1024 // 1024} MB, většina schránek takový e-mail nepřijme. Vyberte méně souborů.")
                odeslat(n, request.user, komu, kopie, hodnoty["predmet"], hodnoty["text"], prilozene, z)
                messages.success(request, f"E-mail byl odeslán na {', '.join(komu)}" + (f" s {len(prilozene)} přílohami." if len(prilozene) > 1 else " s 1 přílohou." if prilozene else "."))
                return redirect(nx)
            except ChybaOdeslani as e:
                chyby["obecne"] = str(e)
    zakazky = Zakazka.objects.select_related("zakaznik").order_by("-datum_vytvoreni")[:200]
    crumbs = [("📋 Zakázky", reverse("list", args=["zakazka"]))] + ([(str(z), reverse("plocha", args=[z.pk]))] if z else []) + [("Odeslat e-mailem", None)]
    return R(request, "email_odeslat", sec="zakazky", crumbs=crumbs, n=n, nastaveno=nastaveno, z=z, zakazky=zakazky, soubory=soubory,
             kontakty=kontakty, h=hodnoty, chyby=chyby, nx=nx, podpis=podpis(n, request.user) if n else "",
             odeslane=OdeslanyEmail.objects.filter(zakazka=z).select_related("odeslal")[:10] if z else [],
             admin=P.ma(request.user, P.NASTAVENI), max_mb=MAX_VELIKOST // 1024 // 1024)
