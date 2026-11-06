# Struktura projektu

Zdrojový kód aplikace je uspořádán podle konvencí frameworku Django. Projekt tvoří konfigurační balíček `config` a jediná aplikace `core`, která obsahuje veškerou funkcionalitu. Rozdělení do více aplikací Django nebylo pro rozsah projektu potřebné; logické části jsou místo toho odděleny do modulů a podsložek. Struktura hlavních složek a souborů je následující:

```
BusinessManager/
|-- README.md                 rychlá instalace, přehled, licence
|-- INSTALACE.md              podrobný návod k instalaci, záloze a obnově
|-- LICENSE                   licence MIT
|-- docs/                     tato dokumentace
|-- instalace.bat, .ps1       instalace ve Windows dvojklikem
|-- aktualizace.bat, .ps1     aktualizace na novou verzi z GitHubu dvojklikem
|-- zaloha.bat                záloha databáze a souborů
|-- manage.py                 spouštění příkazů Django
|-- requirements.txt          knihovny jazyka Python
|-- Dockerfile                sestavení obrazu aplikace
|-- docker-compose.yml        kontejnery web + db
|-- docker-entrypoint.sh      migrace, statické soubory, Gunicorn
|-- .env.example              vzor konfigurace prostředí
|-- config/                   konfigurace projektu
|   |-- settings.py           nastavení (databáze, middleware, media)
|   |-- urls.py               hlavní URL, přihlášení, soubory media
|   `-- wsgi.py               vstupní bod pro Gunicorn
`-- core/                     aplikace BusinessManager
    |-- models.py             datový model (tabulky databáze)
    |-- views.py              pohledy evidence
    |-- views_sablony.py      pohledy šablon a dokumentů
    |-- pruvodce.py           průvodce prvním spuštěním
    |-- cislovani.py          číselné řady dokladů
    |-- navigace.py           tlačítka Zpět a Zrušit
    |-- urls.py               URL adresy aplikace
    |-- apps.py               výchozí data po migraci
    |-- admin.py              registrace modelů v administraci
    |-- tests.py              automatické testy
    |-- migrations/           migrace databázového schématu
    |-- management/commands/  vlastní příkazy manage.py
    |-- templatetags/         vlastní filtry šablon
    |-- static/vendor/        přibalený Bootstrap a htmx
    |-- sablony/              systém šablon dokumentů
    |   |-- typy.py           typy dokumentů a jejich pole
    |   |-- renderery.py      formáty šablon (Excel, HTML)
    |   |-- excel.py          analýza a vyplnění Excelu
    |   |-- kresby.py         zachování tvarů v Excelu
    |   |-- prevod.py         LibreOffice, PDF, miniatury
    |   |-- isdoc.py          export a import faktur ISDOC (XML)
    |   |-- schemata/         schéma XSD formátu ISDOC 6.0.2
    |   `-- vzory/            vestavěné Excelové šablony
    `-- templates/
        |-- core/             HTML šablony obrazovek
        |   `-- sablony/      obrazovky správy šablon a editor
        |-- registration/     přihlašovací stránka
        `-- sablony_vestavene/ vestavěná HTML šablona dokumentu
```

Data konkrétní instalace nejsou součástí repozitáře: databáze `db.sqlite3` (jen bez Dockeru), složka `media/` s nahranými soubory a soubor `.env` s hesly.

## Konfigurace projektu

Složka `config/` obsahuje nastavení celého projektu. Soubor `settings.py` načítá konfiguraci z proměnných prostředí (tajný klíč, režim ladění, povolené adresy serveru, typ a přístupové údaje databáze), takže stejný kód lze provozovat při vývoji i v produkci bez úprav. Dále definuje seznam middleware, české národní prostředí (`LANGUAGE_CODE = "cs"`, časové pásmo `Europe/Prague`), umístění statických souborů a složky `media` a adresy pro přihlášení a odhlášení. Soubor `urls.py` připojuje administraci Django, přihlašovací a odhlašovací stránku, obsluhu souborů `media` a adresy aplikace `core`. Soubor `wsgi.py` je vstupním bodem, přes který aplikaci spouští server Gunicorn.

## Backend aplikace (core)

- `models.py` – obsahuje všechny modely, tedy definici tabulek databáze včetně validátorů (IČO, DIČ, telefon), automatického číslování dokladů a signálů pro kalendář. Na konci souboru je model šablony dokumentu.
- `views.py` – obsahuje pohledy evidenční části: obecné pohledy seznamu, detailu, formuláře a mazání pro libovolnou tabulku, vyhledávání s našeptávačem, pracovní plochu, formulář nové zakázky, tvorbu nabídky, faktury a přijaté objednávky ze zakázky, číslování dokladů, evidenci přijatých faktur s importem ze souboru ISDOC, přehled zařízení, detail zákazníka, kalendář, nastavení a řízení stavů zakázky. Na začátku souboru je definována struktura hlavní nabídky a přiřazení tabulek k sekcím aplikace, ze kterého se sestavuje navigace.
- `views_sablony.py` – obsahuje pohledy pro správu šablon, náhled dokumentu, výběr šablony, export do PDF a do formátu ISDOC, miniatury šablon a editor Excelových šablon.
- `urls.py` – mapuje adresy na pohledy. Specifické adresy (např. `/zakazka/nova/`, `/dokument/<typ>/<id>/pdf/`) jsou uvedeny před obecnými adresami `/<tabulka>/...`, aby měly přednost.
- `apps.py` – po každé migraci doplní výchozí data (stavy zakázek, oprávnění, sazby DPH, vestavěné šablony).
- `pruvodce.py` – průvodce prvním spuštěním (účet administrátora a firma) a middleware, který na něj přesměruje.
- `cislovani.py` – číselné řady: převod vzoru čísla (např. `ZL260001`) na formát se značkami a výpočet dalšího volného čísla.
- `navigace.py` – middleware, který si pamatuje navštívené stránky, aby tlačítka Zpět a Zrušit vedla tam, odkud uživatel přišel.
- `tests.py` – automatické testy (68 testů, viz [Testování](09-vyvoj-a-testovani.md)).
- `admin.py` – automaticky zaregistruje všechny modely do administračního rozhraní.
- `migrations/` – obsahuje migrace, které postupně vytvářejí a upravují databázové schéma (například počáteční schéma, automatické číslování nabídek a faktur, délky polí a validace, šablony dokumentů, přijaté faktury, integritní omezení, číselné řady, vlastní události a platby vystavených faktur).
- `management/commands/` – obsahuje vlastní příkazy: `seed_data` vytvoří testovací data a `vytvor_vzory_sablon` vygeneruje vestavěné Excelové šablony.

## Generování dokumentů (core/sablony)

Podsložka `core/sablony/` je samostatný balíček se systémem šablon dokumentů. Jeho moduly mají jasně oddělené odpovědnosti: `typy.py` určuje, jaká data dokument obsahuje a jak se načtou z databáze; `renderery.py` určuje, jak se z šablony a dat vytvoří náhled a PDF; `excel.py` obsahuje veškerou práci s Excelovými soubory; `kresby.py` zachovává grafické tvary, které by knihovna openpyxl jinak ztratila; `prevod.py` zajišťuje spouštění LibreOffice a tvorbu miniatur; `isdoc.py` vytváří z dat faktury elektronickou fakturu ve formátu ISDOC, čte faktury ISDOC od dodavatelů a složka `schemata/` obsahuje schéma, proti kterému se ověřuje. Složka `vzory/` obsahuje vestavěné šablony dodávané s aplikací (pro každý typ dokumentu firemní a standardní variantu; jednoduchá HTML šablona je v `templates/sablony_vestavene/`). Tento balíček nezávisí na pohledech; pohledy ho pouze volají.

## Frontend (templates)

Složka `core/templates/core/` obsahuje šablony jednotlivých obrazovek. Šablona `base.html` definuje společné rozvržení, dílčí šablona `_motiv.html` přepínání světlého a tmavého režimu. Obecné šablony `list.html`, `detail.html`, `form_sekce.html` a `delete.html` (a dílčí šablony `_pole.html`, `_pohled.html`, `_stavy.html`, `_hledat.html`) slouží všem tabulkám, které nemají vlastní obrazovku. Specializované šablony odpovídají hlavním obrazovkám aplikace, například `zakazka_nova.html` (přijetí zakázky), `plocha.html` (pracovní plocha zakázky s prohlížečem dokumentů), `zarizeni_prehled.html`, `zakaznik_detail.html`, `kalendar.html`, `nabidka_nova.html`, `faktura_nova.html`, `objednavka_nova.html`, `prijata_faktura_import.html` (nahrání přijaté faktury), `prijata_faktura_rucne.html`, `nastaveni_cislovani.html` a `pruvodce.html`. Podsložka `sablony/` obsahuje obrazovky správy šablon, výběru šablony, náhledu dokumentu a editoru šablon. Složka `templates/sablony_vestavene/` obsahuje vestavěnou HTML šablonu dokumentu, která se nepoužívá k zobrazení obrazovky, ale k tvorbě dokumentu.

Knihovny frontendu (Bootstrap, htmx) jsou přibalené ve složce `core/static/vendor/`, takže se nic nenačítá z cizích serverů a aplikace funguje i bez internetu. Drobné vlastní styly a skripty jsou přímo v šablonách. Statické soubory připravuje příkaz `collectstatic` a v provozu je obsluhuje WhiteNoise.

## Data a spouštěcí soubory

Soubor `db.sqlite3` je databáze SQLite používaná při spuštění bez Dockeru, složka `media/` obsahuje nahrané soubory. Obě položky jsou daty konkrétní instalace, nikoli součástí zdrojového kódu. V Dockeru jsou místo nich použity svazky `pgdata` a `media`. Soubor `manage.py` je standardní nástroj Django pro spouštění příkazů (migrace, vývojový server, vlastní příkazy). Soubory `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh` a `.env.example` slouží k zabalení a spuštění aplikace, skripty `instalace.bat`/`instalace.ps1`, `aktualizace.bat`/`aktualizace.ps1` a `zaloha.bat` k instalaci, aktualizaci a záloze ve Windows. Soubor `README.md` obsahuje rychlou instalaci a `INSTALACE.md` podrobný návod včetně zálohy a obnovy.

## Vazby mezi částmi projektu

Závislosti mezi moduly směřují jedním směrem: `config` načítá `core`, adresy v `urls.py` odkazují na pohledy, pohledy používají modely a balíček `sablony` a vykreslují šablony z `templates`, balíček `sablony` čte data přes modely a na samotných pohledech nezávisí (výjimkou je sdílená funkce pro sestavení položek ze zakázky). Modely nezávisí na ničem jiném než na frameworku Django. Toto uspořádání odpovídá vrstvené architektuře popsané v kapitole [Architektura](04-architektura.md) a usnadňuje úpravy: změna vzhledu obrazovky se týká jen šablony, změna výpočtu ceny jen modelu a nový formát dokumentu jen balíčku `sablony`.
