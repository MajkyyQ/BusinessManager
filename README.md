# BusinessManager (Django 5.2 + PostgreSQL 17 + Docker)

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

Zálohy: dvojklik na `zaloha.bat`. Přístup z ostatních PC, zálohy, obnova a řešení potíží: [INSTALACE.md](INSTALACE.md).

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
- **Nastavení** (údaje o firmě, DPH, zaměstnanci a role, katalogy, historie změn, zálohování) vidí a mění jen administrátor
  (uživatel s příznakem *Staff* nebo *Superuser*). Ostatním se položka v menu nezobrazí a přímý odkaz je vrátí na plochu.
- **Šablony dokumentů** jsou v sekci Dokumenty a upravovat je může každý přihlášený uživatel.

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
