"""Omezení pokusů o přihlášení: po 3 špatných heslech se přihlášení k danému uživatelskému jménu zablokuje na 5 minut,
po dalších 3 na 10 minut (a dál vždy na 10 minut). Po úspěšném přihlášení nebo po 24 hodinách bez chybného pokusu se počítá znovu od začátku.

Pokusy se ukládají do databáze (model BlokacePrihlaseni), takže restart nebo vypnutí aplikace blokaci nezruší.
Kontrola je v autentizačním backendu, platí tedy pro přihlašovací stránku i pro /admin/. Formulář PrihlaseniForm k tomu
ukáže srozumitelnou českou hlášku (kolik pokusů zbývá, do kdy je přihlášení zablokované)."""
from datetime import timedelta

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone

POKUSY = 3                    # počet špatných hesel před blokací
BLOKACE_MINUT = (5, 10)       # 1. blokace 5 minut, 2. a každá další 10 minut
ZAPOMENOUT_PO = timedelta(hours=24)  # po této době bez chybného pokusu začíná počítání znovu (zase od 5 minut)


def klic(jmeno):
    return (jmeno or "").strip().lower()[:150]


def _zaznam(jmeno):
    from .models import BlokacePrihlaseni
    return BlokacePrihlaseni.objects.filter(uzivatelske_jmeno=klic(jmeno)).first()


def blokovano_do(jmeno):
    """Čas konce blokace, nebo None, když se uživatel může přihlásit."""
    z = _zaznam(jmeno) if jmeno else None
    return z.blokovano_do if z and z.blokovano_do and z.blokovano_do > timezone.now() else None


def zbyva_pokusu(jmeno):
    z = _zaznam(jmeno) if jmeno else None
    if not z or timezone.now() - z.posledni_pokus > ZAPOMENOUT_PO: return POKUSY
    return max(POKUSY - z.neuspesne_pokusy, 0)


def zaznamenej_neuspech(jmeno):
    from .models import BlokacePrihlaseni
    k = klic(jmeno)
    if not k: return
    ted = timezone.now()
    with transaction.atomic():
        z, _ = BlokacePrihlaseni.objects.select_for_update().get_or_create(uzivatelske_jmeno=k)
        if z.blokovano_do and z.blokovano_do > ted: return  # pokus během blokace se nepočítá (heslo se ani neověřovalo)
        if ted - z.posledni_pokus > ZAPOMENOUT_PO: z.neuspesne_pokusy = z.pocet_blokaci = 0
        z.neuspesne_pokusy += 1; z.posledni_pokus = ted
        if z.neuspesne_pokusy >= POKUSY:
            z.blokovano_do = ted + timedelta(minutes=BLOKACE_MINUT[min(z.pocet_blokaci, len(BLOKACE_MINUT) - 1)])
            z.pocet_blokaci += 1; z.neuspesne_pokusy = 0
        z.save()


@receiver(user_login_failed)
def _neuspesne_prihlaseni(sender, credentials, request=None, **kw):
    zaznamenej_neuspech(credentials.get("username"))


@receiver(user_logged_in)
def _uspesne_prihlaseni(sender, user, request=None, **kw):
    from .models import BlokacePrihlaseni
    BlokacePrihlaseni.objects.filter(uzivatelske_jmeno=klic(user.get_username())).delete()


class BlokacePrihlaseniBackend:
    """První v AUTHENTICATION_BACKENDS: zablokovaného uživatele zastaví dřív, než se ověří heslo (ani správné heslo ho nepustí).
    Záměrně nemá get_user ani oprávnění, ty dál řeší ModelBackend."""
    def authenticate(self, request, username=None, **kw):
        if username and blokovano_do(username): raise PermissionDenied
        return None


def _minut(n):
    return f"{n} minutu" if n == 1 else f"{n} minuty" if 2 <= n <= 4 else f"{n} minut"


def hlaska_blokace(do):
    minut = max(1, -(-int((do - timezone.now()).total_seconds()) // 60))  # zaokrouhlit nahoru
    return (f"Příliš mnoho neúspěšných pokusů. Přihlášení je zablokované, zkuste to znovu za {_minut(minut)} "
            f"(v {timezone.localtime(do):%H:%M}).")


class PrihlaseniForm(AuthenticationForm):
    """Přihlašovací formulář s hláškou o zbývajících pokusech a o blokaci."""
    def clean(self):
        jmeno = self.cleaned_data.get("username")
        do = blokovano_do(jmeno)
        if do: raise forms.ValidationError(hlaska_blokace(do), code="blokovano")
        try:
            return super().clean()
        except forms.ValidationError as e:
            if getattr(e, "code", None) != "invalid_login": raise
            do = blokovano_do(jmeno)
            if do: raise forms.ValidationError(hlaska_blokace(do), code="blokovano")
            n = zbyva_pokusu(jmeno)
            pokus = "pokus" if n == 1 else "pokusy"
            raise forms.ValidationError(f"Nesprávné uživatelské jméno nebo heslo. Zbývají {n} {pokus}, pak se přihlášení na chvíli zablokuje."
                                        if n > 1 else "Nesprávné uživatelské jméno nebo heslo. Zbývá poslední pokus, pak se přihlášení na chvíli zablokuje.",
                                        code="invalid_login")
