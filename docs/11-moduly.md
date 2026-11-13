# Volitelné moduly

Základní aplikace obsahuje jen to, co potřebuje každá servisní firma. Další funkce (například odesílání e-mailů) jsou **volitelné moduly**: nejsou součástí aplikace, stahují se zvlášť z repozitáře **[BusinessManager-moduly](https://github.com/MajkyyQ/BusinessManager-moduly)** a firma si přidá jen ty, které chce.

Přehled nainstalovaných modulů je v aplikaci v **Nastavení → Moduly**.

## Přidání modulu do aplikace

Postup pro aplikaci nainstalovanou podle [INSTALACE.md](../INSTALACE.md) ve složce `C:\BusinessManager`.

1. **Udělejte zálohu** (dvojklik na `zaloha.bat`). Modul přidává do databáze nové tabulky.
2. **Stáhněte moduly:** na stránce https://github.com/MajkyyQ/BusinessManager-moduly zelené tlačítko **Code → Download ZIP** a ZIP rozbalte (kamkoli, např. do Stažených souborů).
3. **Zkopírujte složku modulu** (např. `email`) do složky `moduly` aplikace, aby výsledek byl
   ```
   C:\BusinessManager\moduly\email\apps.py
   ```
   Složka modulu musí ležet přímo ve složce `moduly`, ne o úroveň hlouběji (`moduly\email\email\...` je špatně).
4. **Spusťte aplikaci znovu s novým modulem:** dvojklik na `aktualizace.bat`, nebo v příkazovém řádku
   ```
   cd C:\BusinessManager
   docker compose up -d --build
   ```
   Při startu se modul načte a jeho tabulky se v databázi vytvoří samy (migrace). Tabulek aplikace ani jiných modulů se to nedotkne.
5. V aplikaci otevřete **Nastavení → Moduly**. Modul je v seznamu s verzí a odkazy na své nastavení. Co dál nastavit, popisuje `README.md` ve složce modulu.

Při vývoji bez Dockeru stačí složku zkopírovat do `moduly/` a spustit `python manage.py migrate` a `python manage.py runserver`.

## Aktualizace modulu

Stáhněte novou verzi, nahraďte složku modulu v `C:\BusinessManager\moduly` a znovu spusťte `aktualizace.bat` (nebo `docker compose up -d --build`). Případné změny tabulek modulu provedou jeho migrace automaticky.

Aktualizace aplikace (`aktualizace.bat`) složku `moduly` nepřepisuje, nainstalované moduly zůstanou.

## Vypnutí a odebrání modulu

- **Dočasné vypnutí:** do souboru `.env` přidejte řádek `MODULY_VYPNUTE=email` (více modulů oddělte čárkou) a spusťte `docker compose up -d`. Složka i data modulu zůstanou.
- **Odebrání:** smažte složku modulu z `C:\BusinessManager\moduly` a spusťte `docker compose up -d --build`.

Po vypnutí nebo odebrání zůstanou tabulky modulu v databázi, takže po jeho vrácení se data neztratí.

## Jak systém modulů funguje

Modul je samostatná aplikace frameworku Django ve složce `moduly/<kod>/`:

```
moduly/
  __init__.py
  email/                 kód modulu = název složky (malá písmena, číslice, _)
    __init__.py
    apps.py              zapojení modulu do aplikace (povinné)
    models.py            tabulky modulu
    migrations/          migrace tabulek modulu
    urls.py              stránky modulu, dostupné na /moduly/<kod>/...
    views.py
    templates/<label>/   šablony stránek
    tests.py             testy modulu (python manage.py test moduly.email)
    requirements.txt     další knihovny Pythonu (nepovinné, nainstalují se při sestavení)
    README.md            co modul dělá a jak ho nastavit
```

1. **Nalezení.** `config/settings.py` při startu projde složku `moduly/` (funkce `najdi_moduly` v `core/moduly.py`) a každou podsložku s `apps.py` přidá do `INSTALLED_APPS`. Adresy z jejího `urls.py` připojí `config/urls.py` pod `/moduly/<kod>/`.
2. **Databáze.** Tabulky modulu mají předponu podle jeho označení (`label`, např. `modul_email_nastaveniemailu`) a vlastní migrace, které se spouštějí spolu s migracemi aplikace při každém startu kontejneru (`docker-entrypoint.sh`). Modul smí odkazovat na tabulky aplikace (např. na zakázku), aplikace na tabulky modulu nikdy, takže bez modulu funguje beze změny.
3. **Zapojení do rozhraní.** V metodě `ready()` svého `AppConfig` modul zavolá `core.moduly.registruj(Modul(...))` a řekne aplikaci:

| Pole `Modul` | K čemu |
|:--|:--|
| `kod`, `nazev`, `verze`, `popis`, `pozadavky` | zobrazí se v Nastavení → Moduly |
| `nastaveni` | odkazy v Nastavení → Moduly, seznam `(popisek, název adresy)` |
| `akce_zakazky(request, zakazka)` | tlačítka na pracovní ploše zakázky, seznam `dict(text, url, title)` |
| `akce_dokumentu(request, typ, objekt)` | tlačítka v náhledu zakázkového listu, nabídky a faktury |
| `prava` | které oprávnění potřebují stránky modulu, např. `{"modul_email:nastaveni": {"nastaveni.spravovat"}}`; bez záznamu stačí základní přístup |

4. **Oprávnění.** Stránky modulu hlídá stejný middleware jako stránky aplikace (`core/prava.py`): uživatel musí mít základní přístup a oprávnění, která modul uvedl v `prava`. Tlačítka modulu se uživateli bez oprávnění nezobrazí.
5. **Odolnost.** Chyba v kódu tlačítek modulu se zapíše do logu a stránka aplikace se zobrazí dál bez tlačítek modulu.

Základní aplikace o konkrétních modulech nic neví, zná jen tato místa pro rozšíření. Nový modul proto nevyžaduje změnu kódu aplikace.

## Nový modul

Nejrychlejší je zkopírovat modul `email` a upravit ho. Minimální `apps.py`:

```python
from django.apps import AppConfig

class SkladConfig(AppConfig):
    name = "moduly.sklad"; label = "modul_sklad"; verbose_name = "Modul Sklad"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from core import moduly
        moduly.registruj(moduly.Modul(kod="sklad", nazev="Sklad", verze="0.1", popis="Evidence materiálu na skladě.",
                                      nastaveni=[("Sklad", "modul_sklad:prehled")]))
```

Stránky modulu použijí rozvržení aplikace přes `core.views.R(request, "modul_sklad/prehled.html", sec="nastaveni", ...)` a šablona začne `{% extends "core/base.html" %}`. Tabulky se vytvoří příkazem `python manage.py makemigrations modul_sklad`.
