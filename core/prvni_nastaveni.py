"""Co má administrátor nastavit po prvním spuštění (Nastavení → První nastavení a upozornění na pracovní ploše).

Průvodce prvním spuštěním (core/pruvodce.py) založí jen účet administrátora a název firmy. Aby šlo s aplikací běžně pracovat,
je potřeba doplnit ještě údaje o firmě, role, zaměstnance a typy úkonů. U každého kroku se podle databáze pozná, jestli je hotový
(None = nejde poznat, jen doporučení). Stejný seznam je popsaný v docs/10-prvni-nastaveni.md."""
from django.urls import reverse

from .models import CiselnaRada, HistorieZmen, Material, NastaveniFirmy, Role, TypUkonu, Zamestnanec


def kroky(user):
    """Seznam kroků: dict(nazev, popis, url, odkaz, hotovo, povinny)."""
    L = lambda s: reverse("list", args=[s])
    f = NastaveniFirmy.objects.first()
    ostatni = Zamestnanec.objects.filter(aktivni=True).exclude(uzivatel=user)  # zaměstnanci kromě přihlášeného administrátora
    role_upravene = (HistorieZmen.objects.filter(typ_objektu="role").exists()
                     or Role.objects.exclude(nazev="Zaměstnanec").filter(zamestnanec__in=ostatni).exists())  # někomu přidělena jiná než základní role
    k = [
        ("Údaje o firmě", "IČ, DIČ, adresa, číslo účtu a logo se tisknou na zakázkové listy, nabídky a faktury; bez čísla účtu nemá faktura kam platit. "
                          "Tady se nastavuje i výchozí sazba DPH a měna.",
         reverse("nastaveni_firma"), "Upravit údaje o firmě", bool(f and f.ico and f.adresa and f.cislo_uctu), True),
        ("Role", "Role určují, co kdo v aplikaci smí. Připravené jsou Zaměstnanec, Technik, Administrativa a Administrátor. "
                 "Zkontrolujte, co která role smí, upravte je nebo přidejte vlastní (např. Skladník).",
         L("role"), "Otevřít role", role_upravene, True),
        ("Zaměstnanci", "Každému, kdo bude s aplikací pracovat, založte kartu zaměstnance, zaškrtněte „Může se přihlásit do aplikace“, "
                        "zadejte mu přihlašovací jméno a heslo a přiřaďte roli. Bez karty a role se zaměstnanec přihlásí, ale nic neuvidí.",
         L("zamestnanec"), "Otevřít zaměstnance", ostatni.filter(uzivatel__isnull=False).exists(), True),
        ("Typy úkonů", "Druhy prací, ze kterých technik vybírá při zápisu práce na zakázce (např. Diagnostika, Výměna displeje, Čištění). "
                       "Dokud žádný není, nejde na zakázku zapsat práci.",
         L("typukonu"), "Otevřít typy úkonů", TypUkonu.objects.filter(aktivni=True).exists(), True),
        ("Číslování dokladů", "Jak vypadají čísla zakázkových listů, nabídek a faktur (např. ZL260001, FV2026001). "
                              "Výchozí číslování funguje i bez úprav.",
         reverse("nastaveni_cislovani"), "Nastavit číslování", CiselnaRada.objects.exists(), False),
        ("Šablony dokumentů", "Vzhled zakázkového listu, nabídky a faktury. Vyberte výchozí šablonu nebo nahrajte vlastní Excel.",
         reverse("sablony"), "Otevřít šablony", None, False),
        ("Stavy zakázek", "Stavy, kterými zakázka prochází, jsou připravené. Můžete změnit jejich pořadí, barvu nebo přidat vlastní.",
         L("stavzakazky"), "Otevřít stavy zakázek", None, False),
        ("Materiály a dodavatelé", "Katalog materiálu a náhradních dílů s cenou usnadní zápis materiálu na zakázku. Jde ho doplňovat i průběžně.",
         L("material"), "Otevřít materiály", Material.objects.exists(), False),
        ("Zálohování", "Nastavte pravidelnou zálohu databáze a souborů, ať o data nepřijdete při poruše počítače.",
         reverse("nastaveni_zaloha"), "Jak zálohovat", None, False),
    ]
    return [dict(nazev=n, popis=p, url=u, odkaz=o, hotovo=h, povinny=pv) for n, p, u, o, h, pv in k]


def souhrn(user):
    """Kroky a počty pro šablonu: povinných celkem / hotových, zda je vše povinné hotové a zda je upozornění skryté."""
    k = kroky(user); pov = [x for x in k if x["povinny"]]; hot = sum(1 for x in pov if x["hotovo"])
    f = NastaveniFirmy.objects.first()
    return dict(kroky=k, povinne=pov, volitelne=[x for x in k if not x["povinny"]], pocet=len(pov), hotovo=hot,
                vse=hot == len(pov), skryto=bool(f and f.prvni_nastaveni_skryto))
