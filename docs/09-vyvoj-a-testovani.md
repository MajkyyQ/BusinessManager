# Vývoj a testování

Tato stránka je pro toho, kdo chce aplikaci upravovat nebo ověřit, že funguje. Instalaci pro běžný provoz ve firmě popisuje [README](../README.md#rychlá-instalace-windows) a podrobně [INSTALACE.md](../INSTALACE.md).

## Spuštění pro vývoj (bez Dockeru, SQLite)

Potřeba je Python 3.12 nebo novější. Ve složce projektu:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
echo DEBUG=1> .env
python manage.py migrate
python manage.py runserver 8080
```

Řádek `DEBUG=1` v souboru `.env` zapne ladicí režim (podrobné chybové stránky); bez něj aplikace běží v provozním režimu. Na Linuxu a macOS se prostředí aktivuje příkazem `source .venv/bin/activate`. Aplikace pak běží na <http://127.0.0.1:8080>. Při prvním otevření se spustí průvodce, ve kterém založíte účet administrátora a firmu.

- **Testovací data:** `python manage.py seed_data` vytvoří ukázkové zákazníky, zařízení, zakázky, zaměstnance, práce a materiál. Je určen jen pro vývoj a předvádění, ne pro ostrou databázi.
- **PDF a náhledy Excelových šablon** potřebují LibreOffice. Ve Windows ho aplikace najde v `C:\Program Files\LibreOffice`, jinou cestu lze zadat proměnnou prostředí `LIBREOFFICE`. Bez LibreOffice fungují HTML šablony.
- **Vestavěné Excelové šablony** se znovu vygenerují příkazem `python manage.py vytvor_vzory_sablon`.
- **Vývoj proti PostgreSQL:** `docker compose up -d db`, v `docker-compose.yml` dočasně přidat k službě `db` řádek `ports: ["5432:5432"]` a spustit `runserver` s proměnnými `DB_ENGINE=postgres`, `DB_HOST=localhost` a `DB_NAME`, `DB_USER`, `DB_PASSWORD` podle `.env`.

## Konfigurace (proměnné prostředí)

Nastavení se čte z proměnných prostředí a ze souboru `.env` ve složce aplikace, v Dockeru i při spuštění bez něj (vzor je v `.env.example`, skutečný `.env` se do repozitáře nikdy neukládá). Proměnná nastavená v systému má přednost před `.env`.

| Proměnná | Význam | Výchozí hodnota |
|:--|:--|:--|
| `SECRET_KEY` | tajný klíč Django (dlouhý náhodný řetězec) | vygeneruje se náhodně a uloží do souboru `.secret_key` |
| `DEBUG` | `1` = ladicí režim (jen pro vývoj), `0` = provoz | `0` |
| `HTTPS` | `1`, když aplikace běží za HTTPS (např. Caddy nebo nginx); cookies se pak posílají jen šifrovaně | `0` |
| `MAX_VELIKOST_SOUBORU_MB` | největší velikost jednoho nahrávaného souboru v MB | `50` |
| `MAX_VELIKOST_NAHRAVANI_MB` | největší velikost jednoho nahrání (např. víc fotek najednou) v MB | `500` |
| `ZALOHA_KOPIE` | kam `zaloha.bat` zkopíruje poslední zálohu (jiný disk nebo sdílená složka jiného PC, drží se 2 poslední) | prázdné |
| `ZALOHA_PONECHAT` | kolik záloh nechat ve složce `zalohy` na serverovém PC | `7` |
| `ALLOWED_HOSTS` | adresy, na kterých aplikace odpovídá (čárkami) | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | adresy včetně `http://` a portu, ze kterých se odesílají formuláře | prázdné |
| `DB_ENGINE` | `postgres` = PostgreSQL, jinak SQLite | SQLite |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | připojení k PostgreSQL | `businessmanager`, `localhost`, `5432` |
| `LIBREOFFICE` | cesta k programu LibreOffice, pokud není ve standardním umístění | hledá se automaticky |
| `LIBREOFFICE_LIMIT` | kolik sekund smí trvat jeden převod v LibreOffice, než se zkusí znovu | 180 |

## Automatické testy

Testy jsou v souboru `core/tests.py` a spouští se příkazem:

```bat
python manage.py test core
```

Každý test si vytvoří vlastní prázdnou databázi, takže výsledek nezávisí na datech v aplikaci. Testy pokrývají části, ve kterých by chyba měla největší následky: správnost dokladů, integritu dat, oprávnění a bezpečnost. Spouští se po každé změně jako regresní testy.

| Třída testů | Počet | Co ověřuje |
|:--|--:|:--|
| `RozdeleniAdresyTest` | 4 | rozdělení adresy na ulici, číslo, PSČ a město a rozpoznání čísla účtu pro export ISDOC |
| `ExportISDOCTest` | 4 | export faktury do ISDOC: platnost podle oficiálního schématu, správné částky, stabilní UUID, stažení přes adresu |
| `PrijateFakturyTest` | 3 | import přijaté faktury z ISDOC/ISDOCX, zápis do kalendáře, označení zaplacení, chybný soubor |
| `IntegritniOmezeniTest` | 4 | integritní omezení databáze (jméno nebo firma, unikátní kontakt, povolené hodnoty výčtů) a jejich hlášení ve formuláři |
| `UdalostiKalendareTest` | 2 | automatické události kalendáře a jejich posun při změně zakázky nebo faktury |
| `HlavniAkceZakazkyTest` | 1 | zvýraznění doporučeného dalšího kroku na stránce zakázky podle jejího stavu |
| `ZamestnanciZakazkyTest` | 1 | karta Zaměstnanci u zakázky ukazuje všechny zapojené, nejen toho, kdo zakázku převzal |
| `PoznamkaPraceTest` | 1 | interní poznámka k práci se nepropisuje do zakázkového listu ani do nabídky |
| `OpravneniNastaveniTest` | 3 | Nastavení včetně šablon dokumentů vidí jen uživatel s oprávněním Nastavení; styly se nenačítají z internetu |
| `PruvodcePrvnimSpustenimTest` | 2 | průvodce prvním spuštěním: založení administrátora a firmy |
| `SQLInjectionTest` | 5 | odolnost přihlášení, vyhledávání a řazení proti SQL injection |
| `JednotneSeznamyTest` | 4 | seznamy: filtr stavů s počty, přepínač tabulka / kanban, jednotná hlavička, souhrn dokladů |
| `TvorbaDokladuZeZakazkyTest` | 7 | objednávka a faktura se zakládají ze zakázky; kontrola zákazníka a zakázky; tlačítka Pokračovat po vytvoření dokladu |
| `PrijataFakturaRucneTest` | 3 | ruční zápis přijaté faktury: dopočet částky, zákaz duplicity |
| `NovyVzhledFormularuTest` | 4 | formuláře se sekcemi (zákazník, událost, zakázka) a rychlá událost v kalendáři |
| `UcetZamestnanceTest` | 6 | přihlašovací účet zaměstnance: založení, heslo, vypnutí, ochrana vlastního účtu |
| `CislovaniDokladuTest` | 7 | vlastní číslování zakázek, nabídek a faktur, výchozí čísla, přeskočení obsazeného čísla, rok a pořadí na zakázkovém listu, další nabídka s příponou |
| `OpravyZProchazeniTest` | 9 | opravy z procházení aplikace: telefony, více fotek, práce více zaměstnanců, platby, tlačítka Zpět |
| `TmavyRezimTest` | 2 | přepínač vzhledu v horní liště, tmavý režim i na přihlašovací stránce |
| `PrevodLibreOfficeTest` | 5 | převod přes LibreOffice: opakování po nepovedeném pokusu a rozlišení chyb (chybí LibreOffice / převod se nepovedl) |
| `KontrolaEmailuATelefonuTest` | 5 | česká hláška ze serveru u špatného e-mailu a telefonu místo anglické bubliny prohlížeče |
| `RoleAOpravneniTest` | 10 | role a oprávnění: technik bez dokladů, administrativa s doklady, mazání, úprava zákazníka, vlastní události, účet bez role |
| `CitelnaHistorieTest` | 2 | historie změn zapisuje vybrané zaměstnance a jiné vazby jménem, ne jako QuerySet |
| `PolozkyDokladuBezPridaniTest` | 2 | položky faktury a nabídky se ručně nepřidávají, vznikají jen ze zakázky |
| `PracePrepinaStavZakazkyTest` | 3 | přidání práce přepne novou zakázku na Rozpracováno a zapíše to do historie; jiné stavy se nemění |
| `VicePolozekNajednouTest` | 4 | tlačítko Přidat ve formuláři práce a materiálu: víc položek najednou, nevyplněná kopie se přeskočí |
| `BarvaStavuTest` | 4 | barva stavu zakázky nastavená v Nastavení se použije ve všech štítcích stavu |
| `PoradiStavuTest` | 3 | nový stav dostane pořadí jako další v řadě, obsazené pořadí posune ostatní stavy |
| `NovaRoleVeFormulariZamestnanceTest` | 3 | založení nové role v okně formuláře zaměstnance bez jeho opuštění |
| `PrvniNastaveniTest` | 4 | seznam prvního nastavení pro administrátora a upozornění na pracovní ploše |
| `SystemModuluTest` | 5 | volitelné moduly: nalezení ve složce `moduly/`, zápis do Nastavení, tlačítka, obrázek v okně platby na místě (`platba_na_miste`) a oprávnění stránek modulu |
| `BezpecneNastaveniTest` | 2 | bez `.env` se vygeneruje náhodný `SECRET_KEY`, `.env` se načte i bez Dockeru a proměnné prostředí mají přednost |
| `BezpecnostTest` | 9 | opravy z bezpečnostního auditu: nahrávání a odesílání souborů, mazání cizích souborů, přesměrování, soubory podle oprávnění, účet hlavního administrátora (viz [Bezpečnost](12-bezpecnost.md)) |
| `LimitVelikostiSouboruTest` | 3 | příliš velká příloha ani fotka se neuloží (srozumitelná hláška s limitem), příliš velké nahrání najednou se odmítne hned (413) |
| `PlatbaNaMisteTest` | 6 | vydání zakázky se zaplacením na místě bez faktury (hotově, QR kódem, kartou): předvyplněná částka, chybná částka zakázku nevydá, dodatečný zápis platby, výchozí volba u zakázky s fakturou |
| **Celkem** | **142** | |

### Výsledky

Všech 142 testů prošlo v databázi SQLite, ve které se aplikace vyvíjí. Původních 117 testů (stav před doplněním testů pro moduly, bezpečnostní audit a zpevnění po něm) prošlo i v databázi PostgreSQL, nad kterou aplikace běží v Dockeru ve firmě. Aplikace k databázi přistupuje jen přes ORM Django, takže stejný kód funguje nad oběma systémy; spuštění nad PostgreSQL ověřuje rozdíly mezi nimi, např. v kontrole integritních omezení nebo v porovnávání textu.

Testy nad PostgreSQL se spustí stejně jako vývoj proti PostgreSQL (viz výše), jen místo `runserver` příkazem `python manage.py test core`.

### Testy modulů

Volitelné moduly ([BusinessManager-moduly](https://github.com/MajkyyQ/BusinessManager-moduly)) mají vlastní testy ve své složce. Modul Odesílání e-mailů má 16 testů, modul QR platba 10 testů (převod čísla účtu na IBAN, částka, řetězec QR Platby, QR kód v okně Vydat zákazníkovi, stránka pro zákazníka, oprávnění nastavení). Po zkopírování modulu do složky `moduly/` se spouští příkazem:

```bat
python manage.py test moduly.email
python manage.py test moduly.qr_platba
```

## Úprava databáze

Databázové schéma se mění úpravou modelů v `core/models.py` a vytvořením migrace:

```bat
python manage.py makemigrations core
python manage.py migrate
```

V provozu v Dockeru proběhnou migrace samy při spuštění kontejneru. Po změně modelů je dobré obnovit i [přehled tabulek](databaze-tabulky.md) příkazem `python docs/generuj_prehled_databaze.py`.
