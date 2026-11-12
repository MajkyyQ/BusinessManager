# BusinessManager (Django 5.2 + PostgreSQL 17 + Docker)

Webová aplikace pro malou servisní firmu: evidence zákazníků, zařízení a servisních zakázek a tvorba zakázkových listů,
nabídek a faktur (PDF i ISDOC) z uložených dat.

**Dokumentace:** [docs/](docs/README.md) – [popis aplikace](docs/01-popis-aplikace.md), [funkce](docs/02-funkce.md),
[technologie](docs/03-technologie.md), [architektura](docs/04-architektura.md), [databáze](docs/07-databaze.md),
[šablony dokumentů, PDF a ISDOC](docs/08-sablony-dokumentu.md), [vývoj a testování](docs/09-vyvoj-a-testovani.md).
Instalace: níže a podrobně v [INSTALACE.md](INSTALACE.md).

## Rychlá instalace (Windows)
1. Nainstalujte a spusťte **Docker Desktop**: https://www.docker.com/products/docker-desktop/
   V jeho nastavení zapněte *Start Docker Desktop when you sign in to your computer*.
   Docker bude při první instalaci vyžadovat **WSL** a zapnutou **virtualizaci** procesoru. Sám napíše, co a jak zapnout
   (virtualizace se zapíná v BIOSu, na firemním PC případně požádejte správce IT).
2. Stáhněte aplikaci: zelené tlačítko **Code → Download ZIP**, rozbalte do `C:\BusinessManager`.
3. Dvakrát klikněte na **`instalace.bat`**. Aplikace si sama vytvoří nastavení s hesly, spustí se a otevře prohlížeč
   (poprvé 5–15 minut). Žádná hesla nikam nezadáváte.
4. V prohlížeči založte v průvodci účet administrátora a firmu. Hotovo: http://127.0.0.1:8080

**Po restartu PC není potřeba nic spouštět.** Docker Desktop se spustí po přihlášení do Windows a aplikaci zapne sám.
Kdyby se aplikace nenačetla, otevřete ručně Docker Desktop a chvíli počkejte.

Zálohy: dvojklik na `zaloha.bat`.

**Aktualizace na novou verzi:** dvojklik na `aktualizace.bat`. Udělá zálohu, stáhne nejnovější verzi z GitHubu,
přepíše jí soubory aplikace a spustí ji. Data i nastavení (`.env`) zůstanou. Zda vyšla nová verze, sledujte
na GitHubu (stránka repozitáře, případně **Watch → Custom → Releases**). Složku aplikace před aktualizací nemažte,
přišli byste o `.env` s heslem k databázi. Přístup z ostatních PC, zálohy, obnova a řešení potíží: [INSTALACE.md](INSTALACE.md).

### Po prvním spuštění
Průvodce založí jen účet administrátora a název firmy. Administrátor pak musí nastavit **údaje o firmě, role, zaměstnance
a typy úkonů**, volitelně i číslování dokladů a šablony. Seznam s odkazy je v aplikaci (**Nastavení → První nastavení aplikace**)
a v [docs/10-prvni-nastaveni.md](docs/10-prvni-nastaveni.md).

## A) Docker ručně (pro pokročilé)
Podrobný postup čisté instalace na Windows krok za krokem (Docker Desktop, `.env`, první spuštění,
přístup z ostatních PC, zálohy a obnova) je v **[INSTALACE.md](INSTALACE.md)**.
Nejjednodušší je dvojklik na `instalace.bat` (vytvoří `.env` s náhodnými hesly a spustí aplikaci). Ručně:

    copy .env.example .env      (upravte hesla a ALLOWED_HOSTS)
    docker compose up -d --build
    -> http://127.0.0.1:8080
Při prvním otevření se spustí průvodce: založíte účet administrátora a vyplníte údaje o firmě (povinný je jen název).
Databáze je po instalaci prázdná; testovací data (`seed_data`) jsou jen pro vývoj.
Data: volume `pgdata` (databáze) a `media` (fotky, přílohy). Přežijí restart i aktualizaci kontejnerů.
POZOR: `docker compose down -v` volumes SMAŽE. Bez `-v` je `down` bezpečné.
Aktualizace aplikace: `git pull` ; `docker compose up -d --build` (migrace proběhnou samy).
Záloha (databáze + soubory): `zaloha.bat` (vytvoří složku `zalohy\RRRR-MM-DD_HHMM`). Ručně v cmd (ne v PowerShellu):

    docker compose exec -T db pg_dump -U businessmanager businessmanager > zaloha.sql
    docker compose cp web:/app/media zaloha-media
Obnova přepíše současná data, databáze se musí nejdřív vyprázdnit (postup v [INSTALACE.md](INSTALACE.md#obnova-ze-zálohy-např-na-nový-pc)).

## B) Vývoj ve VS Code bez Dockeru (SQLite)
    python -m venv .venv ; .venv\Scripts\activate ; pip install -r requirements.txt
    python manage.py migrate ; python manage.py runserver 8080      (účet a firmu založí průvodce v prohlížeči)
Vývoj proti Postgresu v Dockeru: `docker compose up -d db`, v compose dočasně přidat `ports: ["5432:5432"]`
a spustit runserver s DB_ENGINE=postgres DB_HOST=localhost DB_NAME/USER/PASSWORD z .env.

## Šablony dokumentů (zakázkový list, nabídka, faktura)
Dokumenty → **Šablony dokumentů** (může upravovat každý uživatel). Každý typ dokumentu může mít více šablon (Excel .xlsx nebo HTML), jedna je výchozí.
Náhled dokumentu: v zakázce tlačítko Zakázkový list, u nabídky/faktury Náhled / PDF / tisk. V náhledu lze dočasně zvolit jinou šablonu (výchozí se tím nemění).

Faktura ISDOC: v náhledu faktury tlačítko **Stáhnout ISDOC** (nebo **ISDOC** v detailu faktury) stáhne fakturu jako soubor `.isdoc` (ISDOC 6.0.2) pro import do účetního programu. Soubor se vždy ověří proti oficiálnímu schématu `core/sablony/schemata/isdoc-invoice-6.0.2.xsd`. Testy: `python manage.py test core`.

Přijaté faktury (od dodavatelů): Dokumenty → **Přijatá faktura z ISDOC** nahraje soubor `.isdoc`/`.isdocx`, dodavatele najde podle IČO (nebo založí) a do kalendáře zapíše doručení a splatnost. Tlačítkem **✓ Zaplaceno** v detailu se faktura označí jako zaplacená. Fakturu lze zadat i ručně, dodavatelé jsou v Nastavení → Katalogy.

Pro PDF a náhledy Excelových šablon je potřeba **LibreOffice**:
- Docker: je součástí obrazu, nic se neinstaluje.
- Windows bez Dockeru: nainstalujte LibreOffice z https://www.libreoffice.org/download/ (aplikace ho najde v `C:\Program Files\LibreOffice`),
  jinou cestu lze zadat proměnnou prostředí `LIBREOFFICE`.
Vlastní Excel: do buněk napište značky, např. `{{dokument.cislo}}`, řádek položek `{{polozka.popis}}` … (seznam v aplikaci: Značky pro vlastní šablony).
Bez značek se pole zkusí rozpoznat podle popisků. Vestavěné vzory se generují příkazem `python manage.py vytvor_vzory_sablon`.

## Oprávnění
Co kdo smí, určují **role**: zaměstnanci se v jeho kartě přiřadí role a role je svazek oprávnění (Nastavení → Role).
Tlačítka, na která uživatel nemá oprávnění, se mu nezobrazí, a server stejnou kontrolu dělá i při přímém zadání adresy (`core/prava.py`).

| Oprávnění | Co povoluje |
|---|---|
| Základní přístup | pracovní plocha, zakázky, zápis práce, materiálu a fotek, nový zákazník/zařízení, vlastní události v kalendáři |
| Ruční změna stavu zakázky | přepnutí zakázky do libovolného stavu mimo běžný postup |
| Úprava zákazníků a zařízení | úprava už založených zákazníků, kontaktů a zařízení |
| Úprava kalendáře | úprava a mazání i cizích událostí |
| Nabídky a objednávky | nabídky, přijaté objednávky, sekce Dokumenty a ceny v dokladech |
| Faktury a platby | faktury, platby, přijaté faktury, sekce Dokumenty a ceny v dokladech |
| Mazání a deaktivace | mazání a deaktivace záznamů |
| Nastavení | firma, DPH, číslování a šablony dokumentů, katalogy, zaměstnanci, role, zálohy |

Výchozí role: **Zaměstnanec** (jen základní přístup, dostane ji každý nový zaměstnanec), **Technik**, **Administrativa**
a **Administrátor** (smí všechno). Všechno smí také účet s příznakem *Staff* nebo *Superuser* (např. účet z průvodce prvním spuštěním).
Účet bez role nebo bez karty zaměstnance se přihlásí, ale uvidí jen hlášku, že nemá přístup.

## Provoz bez internetu
Bootstrap a htmx jsou přibalené v `core/static/vendor/`, aplikace se proto nenačítá z cizích serverů.
Stačí prohlížeč a přístup k serveru aplikace, např. v místní síti firmy. Internet není potřeba.

## Licence
Projekt je open source pod licencí **MIT** (soubor [LICENSE](LICENSE)).

Proč MIT: je krátká, srozumitelná a nejrozšířenější open-source licence a je schválená organizací Open Source Initiative.
Kdokoli může aplikaci zdarma používat, upravovat a šířit, i ve firmě nebo v komerčním produktu.
Jedinou podmínkou je zachovat text licence a jméno autora. To odpovídá cíli projektu, aby si jednoduchý systém
pro servisní zakázky mohla nasadit a upravit i malá firma bez licenčních poplatků a bez právních překážek.
Přísnější licence (např. GPL-3.0) by vyžadovala zveřejnit i všechny úpravy, což pro malé firmy může být překážka.
Přibalené knihovny Bootstrap (MIT) a htmx (0BSD) jsou s licencí MIT slučitelné.
