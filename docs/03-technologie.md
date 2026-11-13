# Použité technologie

Při výběru technologií byla rozhodující tři kritéria. Aplikace musí běžet na jednom firemním počítači bez placených licencí, musí být udržovatelná jedním vývojářem a musí umět pracovat se stávajícími Excelovými formuláři firmy. Všechny použité technologie jsou proto open-source, rozšířené a dobře zdokumentované. Tabulka na konci této stránky shrnuje, jakou roli má každá z nich v aplikaci; v následujících odstavcích jsou popsány podrobně.

## Python

**Co to je.** Python je interpretovaný, dynamicky typovaný programovací jazyk pro obecné použití. Je známý čitelnou syntaxí a rozsáhlou standardní knihovnou a patří k nejpoužívanějším jazykům pro vývoj webových aplikací, automatizaci a zpracování dat.

**Proč byl zvolen.** Python je jazykem frameworku Django a knihovny openpyxl, které tvoří jádro aplikace. Pro práci s Excelovými soubory, PDF a XML má Python zralé knihovny a celá aplikace tak může být napsaná v jednom jazyce.

**Jak je v aplikaci použit.** Python je hlavním programovacím jazykem aplikace a zajišťuje veškerou serverovou logiku: definici datového modelu, zpracování požadavků z prohlížeče, výpočty cen a DPH, automatické číslování zakázek a dokladů, řízení stavů zakázky, sestavení dat pro dokumenty i vyplňování Excelových šablon. Aplikace běží na verzi Python 3.12 (verze použitá v obrazu Dockeru). Kromě frameworku Django a knihoven popsaných dále využívá aplikace standardní knihovnu jazyka, zejména modul `decimal` pro přesné peněžní výpočty bez zaokrouhlovacích chyb typu `float`, moduly `datetime` a `calendar` pro práci s daty a kalendářem, `re` pro rozpoznávání značek v šablonách, `zipfile` pro práci s vnitřní strukturou souborů `.xlsx`, `subprocess` pro spouštění LibreOffice a `hashlib` pro vyrovnávací paměť hotových PDF. Seznam knihoven třetích stran je uveden v souboru `requirements.txt`.

## Django

**Co to je.** Django je webový framework pro jazyk Python, který vychází z principu „batteries included“: kromě zpracování HTTP požadavků obsahuje vlastní objektově relační mapování (ORM), systém šablon, formuláře s validací, správu uživatelů a přihlašování, administrační rozhraní, migrace databázového schématu a ochranu proti běžným útokům (CSRF, XSS, SQL injection). Architektonicky se řídí vzorem *Model–View–Template* (MVT), který je variantou známého vzoru MVC.

**Proč byl zvolen.** Aplikace je svou povahou převážně evidenční: obsahuje desítky provázaných tabulek, formulářů a seznamů. Pro takový typ aplikace je Django vhodnější než minimalistické frameworky, jako je například Flask, protože většinu potřebných součástí (ORM, migrace, přihlašování, administraci, formuláře) poskytuje přímo a nebylo nutné je skládat z jednotlivých rozšíření. Díky ORM je navíc aplikace nezávislá na konkrétním databázovém systému a může stejným kódem pracovat s SQLite i PostgreSQL. Aplikace používá verzi Django 5.2, která je verzí s dlouhodobou podporou (LTS).

**Jak je v aplikaci použit.** Django tvoří celý backend aplikace:

- *Modely* (`core/models.py`) popisují všechny tabulky databáze jako třídy jazyka Python. Kromě struktury obsahují i doménovou logiku, například automatické přidělení čísla zakázky v metodě `save()`, přepočet součtů dokladu nebo kopírování údajů zákazníka do dokladu.

- *Pohledy* (`core/views.py` a `core/views_sablony.py`) jsou funkce, které zpracují požadavek z prohlížeče, načtou nebo uloží data pomocí ORM a vrátí HTML stránku, data ve formátu JSON nebo soubor PDF.

- *URL směrování* (`config/urls.py` a `core/urls.py`) přiřazuje adresám v prohlížeči odpovídající pohledy.

- *Šablonovací jazyk Django* generuje HTML stránky uživatelského rozhraní a zároveň slouží jako jazyk HTML šablon dokumentů.

- *Formuláře* (`ModelForm`) se pro většinu tabulek vytvářejí automaticky z definice modelu funkcí `modelform_factory`, včetně validace (například kontrolního součtu IČO nebo formátu DIČ).

- *Autentizace* zajišťuje přihlašování uživatelů; middleware `LoginRequiredMiddleware` vyžaduje přihlášení na všech stránkách aplikace.

- *Migrace* (`core/migrations/`) převádějí změny modelů do databázového schématu a umožňují bezpečně aktualizovat aplikaci bez ztráty dat.

- *Signály* (`post_save`, `post_migrate`) automaticky zapisují události do kalendáře a po instalaci naplní výchozí číselníky.

- *Administrační rozhraní* (Django admin) slouží správci jako záložní nástroj pro přímou úpravu libovolné tabulky a pro správu uživatelských účtů.

## Databázové systémy SQLite a PostgreSQL

**Co to je.** SQLite je odlehčený relační databázový systém, který ukládá celou databázi do jediného souboru a nevyžaduje samostatný databázový server. PostgreSQL je plnohodnotný open-source relační databázový server s podporou transakcí, souběžného přístupu mnoha uživatelů a důsledné kontroly datových typů.

**Proč byly zvoleny.** Aplikace podporuje oba systémy a mezi nimi se přepíná pouze proměnnou prostředí `DB_ENGINE` v souboru `config/settings.py`. SQLite je výchozí volbou pro vývoj a pro spuštění aplikace bez Dockeru: nic se neinstaluje a databáze je jeden soubor `db.sqlite3`. PostgreSQL 17 se používá při nasazení ve firmě v Dockeru, protože lépe zvládá současnou práci více zaměstnanců, hlídá maximální délky textových polí a umožňuje standardní zálohování nástrojem `pg_dump`. Pro připojení k PostgreSQL využívá Django ovladač `psycopg`.

**Jak jsou v aplikaci použity.** Databáze uchovává veškerá data aplikace kromě samotných souborů (fotografií, příloh, šablon), u kterých ukládá pouze cestu. Aplikace s databází nikdy nekomunikuje přímo jazykem SQL, ale vždy přes ORM frameworku Django. Podrobný popis databáze je v kapitole [Databáze](07-databaze.md).

## HTML, CSS a šablonovací jazyk Django

**Co to je.** HTML je značkovací jazyk pro popis struktury webových stránek, CSS určuje jejich vzhled. Šablonovací jazyk Django umožňuje do HTML vkládat proměnné (`{{ z.cislo_zakazky }}`), podmínky a cykly (`{% for … %}`) a dědit společné rozvržení stránek.

**Jak jsou v aplikaci použity.** Všechny obrazovky aplikace se generují na serveru ze šablon ve složce `core/templates/core/`. Společné rozvržení stránky (horní lišta, levá nabídka, drobečková navigace a zprávy pro uživatele) definuje šablona `base.html`, ze které ostatní šablony dědí. Server tak posílá prohlížeči hotové HTML stránky a většina logiky zůstává na straně serveru, což zjednodušuje vývoj i údržbu. Šablonovací jazyk Django se kromě uživatelského rozhraní používá i pro HTML šablony dokumentů (kapitola [Šablony dokumentů](08-sablony-dokumentu.md)).

## Bootstrap

**Co to je.** Bootstrap je CSS framework s připravenými komponentami uživatelského rozhraní (tlačítka, formuláře, tabulky, záložky, upozornění) a mřížkou pro responzivní rozvržení stránky.

**Proč byl zvolen a jak je použit.** Bootstrap umožnil vytvořit jednotné a přehledné rozhraní bez nutnosti psát vlastní rozsáhlé styly. Aplikace používá Bootstrap ve verzi 5.3, který je přibalený přímo v aplikaci (složka `core/static/vendor/`), takže rozhraní funguje i bez připojení k internetu. Třídy Bootstrapu se přiřazují i automaticky generovaným formulářům (třída `BaseForm` v `core/views.py`), takže všechny formuláře vypadají stejně. Vlastní CSS je použito jen pro specifické prvky, například zasouvací levou lištu, prohlížeč dokumentů na pracovní ploše nebo mřížku editoru šablon.

## JavaScript a htmx

**Co to je.** JavaScript je programovací jazyk webových prohlížečů. Knihovna htmx umožňuje pomocí atributů HTML (například `hx-get`, `hx-target`) načíst část stránky ze serveru bez psaní vlastního JavaScriptu.

**Jak jsou v aplikaci použity.** Aplikace záměrně nepoužívá žádný velký frontendový framework (React, Vue apod.), protože rozhraní je převážně formulářové a generuje se na serveru. JavaScript je použit pouze tam, kde výrazně zrychluje práci:

- *vyhledávací pole s našeptávačem* pro výběr zákazníka, zařízení, kontaktní osoby a materiálu, které se dotazuje serveru na adrese `/lookup/<typ>/` a umožňuje nový záznam založit přímo v dialogu bez opuštění formuláře,

- *prohlížeč dokumentů* na pracovní ploše zakázky (přibližování kolečkem myši, posun tažením, přepínání šipkami, porovnání dvou dokumentů vedle sebe, tisk),

- *editor Excelových šablon*, který zobrazuje list šablony jako mřížku buněk a umožňuje přetahovat pole (kapitola [Šablony dokumentů](08-sablony-dokumentu.md)),

- *kalendář* s výběrem měsíce a roku, okno se všemi událostmi dne a okno pro rychlé přidání události,

- *potvrzovací okna* ve vzhledu aplikace místo systémových dialogů prohlížeče, *české pole pro výběr souborů* a tlačítko pro přidání další práce nebo materiálu do stejného formuláře,

- *přepínač tmavého režimu* v horní liště.

Knihovna htmx (verze 2.0, také přibalená v `core/static/vendor/`) se používá u formulářů nové nabídky a faktury: po výběru zakázky se ze serveru načte náhled položek, které budou do dokladu převzaty, a vloží se do stránky bez jejího znovunačtení.

## openpyxl

**Co to je.** openpyxl je knihovna jazyka Python pro čtení a zápis souborů aplikace Microsoft Excel ve formátu Office Open XML (`.xlsx`, `.xlsm`). Pracuje přímo se souborem, takže nepotřebuje nainstalovaný Excel.

**Proč byla zvolena.** Firma měla své formuláře v Excelu a požadovala, aby výsledné dokumenty vypadaly stejně. openpyxl umožňuje načíst existující sešit se všemi styly, sloučenými buňkami, vzorci a obrázky, změnit hodnoty vybraných buněk a sešit znovu uložit, takže vzhled navržený v Excelu zůstane zachován.

**Jak je v aplikaci použita.** openpyxl je základem systému Excelových šablon v modulu `core/sablony/excel.py`. S její pomocí aplikace:

- analyzuje nahranou šablonu, vyhledá v ní značky `{{…}}` a sloučené oblasti a případně rozpozná pole podle popisků,

- vyplní šablonu údaji z databáze, vkládá řádky tabulky položek se zachováním formátování a posouvá vzorce (například součet `SUM`) a obrázky,

- zapisuje čísla a data jako skutečné hodnoty s českým formátem, aby s nimi mohly počítat vzorce v šabloně,

- vkládá logo firmy do vyhrazené oblasti,

- připravuje podklady pro webový editor šablon a ukládá změny, které v něm uživatel provede.

Pomocí openpyxl jsou také programově vytvořeny vestavěné vzorové šablony (příkaz `vytvor_vzory_sablon`).

## lxml

**Co to je.** lxml je rychlá knihovna jazyka Python pro zpracování dokumentů XML.

**Proč byla zvolena a jak je použita.** Soubor `.xlsx` je ve skutečnosti archiv ZIP se soubory XML. Knihovna openpyxl při ukládání zachová obrázky, ale zahodí kresby, které obrázky nejsou (rámečky, čáry, textová pole), a ty firemní formuláře obsahují. Modul `core/sablony/kresby.py` proto po vyplnění šablony pomocí lxml přečte kresby z původního souboru, posune jejich ukotvení podle počtu vložených řádků a vrátí je do výsledného sešitu. Stejný modul zjišťuje polohu tvarů pro jejich zobrazení v editoru šablon. Druhým použitím lxml je export faktury do formátu ISDOC: modul `core/sablony/isdoc.py` knihovnou sestaví dokument XML faktury a ověří ho proti schématu XSD formátu ISDOC (část [Export do formátu ISDOC](08-sablony-dokumentu.md#export-do-formátu-isdoc)). Knihovna tak pokrývá vytvoření i kontrolu dokumentu a aplikace nepotřebuje žádnou specializovanou knihovnu pro ISDOC.

## LibreOffice

**Co to je.** LibreOffice je svobodný kancelářský balík. Kromě běžného použití s grafickým rozhraním ho lze spustit v tzv. *headless* režimu bez okna, kdy slouží jako převodník mezi formáty dokumentů.

**Proč byl zvolen.** Excelové šablony je potřeba převést do PDF tak, aby výsledek vypadal stejně jako při tisku z Excelu, tedy se zachováním sloučených buněk, ohraničení, tiskové oblasti, obrázků i výsledků vzorců. Generování PDF knihovnou typu ReportLab by vyžadovalo nakreslit každý dokument znovu v kódu a uživatel by pak nemohl vzhled dokumentu sám měnit. LibreOffice naproti tomu převede přímo vyplněný sešit, a vzhled dokumentu tak zůstává zcela určen šablonou. Microsoft Excel nebylo možné použít, protože neumožňuje spolehlivé automatizované spouštění na serveru a není dostupný v Linuxovém kontejneru.

**Jak je v aplikaci použit.** Modul `core/sablony/prevod.py` spouští LibreOffice jako samostatný proces příkazem `soffice --headless --convert-to pdf`. Aplikace mu připraví vlastní uživatelský profil s českým národním prostředím, aby se čísla a data ve výsledném PDF formátovala česky (`1 500,00` a `1. 11. 2026`), a převody řadí za sebou pomocí zámku, protože LibreOffice nesmí běžet se stejným profilem dvakrát současně. LibreOffice se používá ke třem účelům: převodu vyplněných Excelových šablon do PDF, převodu HTML šablon do PDF a převodu starších souborů `.xls` do formátu `.xlsx`, se kterým umí pracovat openpyxl. V Dockeru je LibreOffice součástí obrazu aplikace, při spuštění bez Dockeru ho aplikace vyhledá v systémové cestě nebo ve standardním instalačním umístění v systému Windows.

## pypdfium2 a Pillow

**Co to je.** pypdfium2 je rozhraní jazyka Python ke knihovně PDFium (vykreslovacímu jádru PDF z prohlížeče Chromium). Pillow je knihovna pro práci s rastrovými obrázky.

**Jak jsou v aplikaci použity.** Při výběru šablony uživatel vidí miniatury jednotlivých šablon vyplněných ukázkovými daty. Miniaturu vytváří funkce `miniatura` v modulu `prevod.py`: knihovna pypdfium2 vykreslí první stranu vytvořeného PDF a Pillow ji uloží jako obrázek PNG. Pillow zároveň vyžaduje framework Django pro pole typu `ImageField`, ve kterých se ukládají fotografie zakázek a logo firmy.

## Gunicorn a WhiteNoise

**Co to je.** Gunicorn je aplikační server, který spouští aplikace jazyka Python podle rozhraní WSGI a obsluhuje více požadavků současně pomocí několika pracovních procesů. WhiteNoise je doplněk, který umožňuje aplikaci Django přímo a efektivně obsluhovat statické soubory.

**Jak jsou v aplikaci použity.** Vývojový server Django (`runserver`) není určen pro provoz, proto se v Dockeru aplikace spouští serverem Gunicorn se třemi pracovními procesy (soubor `docker-entrypoint.sh`). WhiteNoise je zapojen jako middleware a obsluhuje statické soubory (zejména styly administračního rozhraní), takže není potřeba samostatný webový server typu Nginx.

## Docker a Docker Compose

**Co to je.** Docker je platforma pro balení aplikací do *kontejnerů*, tedy izolovaných prostředí, která obsahují aplikaci včetně všech jejích závislostí. Docker Compose popisuje v jednom souboru více spolupracujících kontejnerů a spouští je jedním příkazem.

**Proč byl zvolen.** Aplikace kromě Pythonu potřebuje i LibreOffice, písma kompatibilní s Arial a Calibri a databázový server. Docker zajišťuje, že se všechny tyto součásti nainstalují vždy ve stejných verzích a stejné konfiguraci, a instalace ve firmě se tak omezí na několik příkazů. Aktualizace aplikace pak spočívá v opětovném sestavení kontejneru, přičemž migrace databáze proběhnou automaticky.

**Jak je v aplikaci použit.** Soubor `Dockerfile` sestaví obraz aplikace z oficiálního obrazu `python:3.12-slim`, doinstaluje LibreOffice (bez grafického rozhraní), písma a knihovny ze souboru `requirements.txt`. Soubor `docker-compose.yml` definuje dvě služby: `db` s databází PostgreSQL 17 a `web` s aplikací, která je dostupná na portu 8080. Data jsou uložena v pojmenovaných svazcích (*volumes*) `pgdata` a `media`, takže přežijí restart i aktualizaci kontejnerů. Podrobněji je nasazení popsáno v kapitole [Architektura](04-architektura.md#spuštění-a-zabalení-aplikace) a postup instalace v [INSTALACE.md](../INSTALACE.md). Pro Windows jsou připraveny skripty `instalace.bat` (vytvoří `.env` s náhodnými hesly a spustí aplikaci), `aktualizace.bat` (záloha, stažení nové verze z GitHubu a nové sestavení) a `zaloha.bat` (záloha databáze a souborů).

## Git a GitHub

Zdrojový kód aplikace je veden ve verzovacím systému Git a uložen v repozitáři na službě GitHub. Každá změna aplikace je zaznamenána jako samostatný commit s popisem, což umožňuje dohledat, kdy a proč byla určitá funkce přidána, a v případě potřeby se vrátit k předchozí verzi. Ve firmě se nová verze aplikace získá dvojklikem na `aktualizace.bat`, který ji stáhne z GitHubu, případně ručně příkazem `git pull`.

## Licence

Aplikace je open source pod licencí **MIT** (soubor [LICENSE](../LICENSE)). Kdokoli ji může zdarma používat, upravovat a šířit, i ve firmě nebo v komerčním produktu; jedinou podmínkou je zachovat text licence a jméno autora. Přibalené knihovny Bootstrap (MIT) a htmx (0BSD) jsou s licencí MIT slučitelné. Zdůvodnění volby licence je v [README](../README.md#licence).

## Shrnutí použitých technologií

| **Technologie**           | **Verze** | **Role v aplikaci**                                                                          |
|:--------------------------|:----------|:---------------------------------------------------------------------------------------------|
| Python                    | 3.12      | hlavní programovací jazyk, veškerá serverová logika                                          |
| Django                    | 5.2 LTS   | webový framework: modely, pohledy, šablony, formuláře, přihlašování, migrace, administrace   |
| SQLite                    | –         | databáze pro vývoj a provoz bez Dockeru                                                      |
| PostgreSQL                | 17        | databáze při nasazení v Dockeru                                                              |
| psycopg                   | 3         | ovladač pro připojení Django k PostgreSQL                                                    |
| HTML, CSS, šablony Django | –         | generování obrazovek uživatelského rozhraní a HTML šablon dokumentů                          |
| Bootstrap                 | 5.3       | vzhled a rozvržení uživatelského rozhraní (přibalený, bez internetu)                         |
| JavaScript, htmx          | –, 2.0    | našeptávač, prohlížeč dokumentů, editor šablon, dynamický náhled položek                     |
| openpyxl                  | 3.1       | čtení, analýza a vyplňování Excelových šablon                                                |
| lxml                      | –         | zachování kreseb (tvarů) v Excelových šablonách, export faktury do ISDOC a ověření schématem |
| LibreOffice               | –         | převod vyplněných šablon do PDF, převod `.xls` na `.xlsx`                                    |
| pypdfium2, Pillow         | –         | miniatury šablon, ukládání fotografií a loga                                                 |
| Gunicorn, WhiteNoise      | –         | provozní aplikační server a obsluha statických souborů                                       |
| Docker, Docker Compose    | –         | zabalení a nasazení aplikace včetně databáze a LibreOffice                                   |
| Git, GitHub               | –         | správa verzí zdrojového kódu                                                                 |

*Přehled technologií a jejich role v aplikaci*

Pro úplnost je třeba uvést, že aplikace nepoužívá framework Flask ani knihovnu ReportLab. Místo frameworku Flask byl z důvodů popsaných výše zvolen framework Django a PDF dokumenty nevznikají kreslením v kódu, ale převodem vyplněných šablon pomocí LibreOffice.
