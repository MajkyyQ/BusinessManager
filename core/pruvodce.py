"""Průvodce prvním spuštěním: 1) účet administrátora, 2) základní údaje o firmě.

Účet se zakládá jako první, aby u firmy šlo uložit, kdo a kdy ji založil.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import NastaveniFirmy

VOLNE = ("/static/", "/media/", "/pruvodce/", "/logout/")  # adresy, které průvodce nepřesměrovává


def je_admin(user): return user.is_staff or user.is_superuser


def chybi_ucet(): return not User.objects.exists()


def chybi_firma(): return not NastaveniFirmy.objects.exists()


class PrvniSpusteniMiddleware:
    """Dokud není založen účet nebo firma, přesměruje na průvodce. Po dokončení už do databáze nesahá."""
    hotovo = False

    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        if not PrvniSpusteniMiddleware.hotovo and not request.path.startswith(VOLNE):
            if chybi_ucet(): return redirect("pruvodce_ucet")
            if chybi_firma():
                if request.user.is_authenticated and je_admin(request.user): return redirect("pruvodce_firma")
            else: PrvniSpusteniMiddleware.hotovo = True
        return self.get_response(request)


class UcetForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User; fields = ("username", "first_name", "last_name", "email")
        labels = {"username": "Přihlašovací jméno", "first_name": "Jméno", "last_name": "Příjmení", "email": "E-mail"}


class FirmaForm(forms.ModelForm):
    class Meta:
        model = NastaveniFirmy; fields = ("nazev_firmy", "ico", "dic", "adresa", "telefon", "email", "web")
        labels = {"nazev_firmy": "Název organizace", "ico": "IČ", "dic": "DIČ", "adresa": "Adresa", "telefon": "Telefon", "email": "E-mail", "web": "Web"}
        help_texts = {"dic": "Jen pokud je firma plátce DPH, např. CZ12345678.", "web": "Nepovinné, např. www.mojefirma.cz"}
        widgets = {"adresa": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["nazev_firmy"].required = True  # jediné povinné pole, ostatní lze doplnit později v Nastavení


def _stranka(request, krok, form):
    for f in form.fields.values(): f.widget.attrs.setdefault("class", "form-control")
    return render(request, "core/pruvodce.html", {"krok": krok, "form": form,
                  "kroky": [(1, "Účet administrátora"), (2, "Údaje o firmě")]})


@login_not_required
def ucet(request):
    if not chybi_ucet(): return redirect("pruvodce_firma" if chybi_firma() else "dashboard")
    form = UcetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        u = form.save(commit=False); u.is_staff = u.is_superuser = True; u.save()
        login(request, u, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("pruvodce_firma")
    return _stranka(request, 1, form)


@login_not_required
def firma(request):
    if chybi_ucet(): return redirect("pruvodce_ucet")
    if not chybi_firma(): return redirect("dashboard")
    if not request.user.is_authenticated: return redirect(reverse("login") + "?next=" + reverse("pruvodce_firma"))
    if not je_admin(request.user):
        messages.error(request, "Údaje o firmě může vyplnit jen administrátor."); return redirect("dashboard")
    form = FirmaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        f = form.save(commit=False); f.vychozi_dph = 21; f.vytvoril = request.user; f.datum_vytvoreni = timezone.now(); f.save()
        PrvniSpusteniMiddleware.hotovo = True
        messages.success(request, f"Vítejte! Firma {f.nazev_firmy} je založená. Další údaje (číslo účtu, logo, DPH) doplníte v Nastavení → Firma.")
        return redirect("dashboard")
    return _stranka(request, 2, form)
