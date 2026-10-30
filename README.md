# BusinessManager (Django 5.2 + PostgreSQL 17 + Docker)

## A) Docker (doporučeno pro firemní PC)
    copy .env.example .env      (upravte hesla a ALLOWED_HOSTS)
    docker compose up -d --build
    docker compose exec web python manage.py createsuperuser
    -> http://localhost:8080
Data: volume `pgdata` (databáze) a `media` (fotky, přílohy). Přežijí restart i aktualizaci kontejnerů.
POZOR: `docker compose down -v` volumes SMAŽE. Bez `-v` je `down` bezpečné.
Aktualizace aplikace: `git pull` ; `docker compose up -d --build` (migrace proběhnou samy).
Záloha DB:   docker compose exec -T db pg_dump -U businessmanager businessmanager > zaloha.sql
Obnova DB:   docker compose exec -T db psql -U businessmanager businessmanager < zaloha.sql
Záloha fotek: docker run --rm -v businessmanager_media:/m -v "%cd%":/b alpine tar czf /b/media.tgz -C /m .

## B) Vývoj ve VS Code bez Dockeru (SQLite)
    python -m venv .venv ; .venv\Scripts\activate ; pip install -r requirements.txt
    python manage.py migrate ; python manage.py createsuperuser ; python manage.py runserver 8080
Vývoj proti Postgresu v Dockeru: `docker compose up -d db`, v compose dočasně přidat `ports: ["5432:5432"]`
a spustit runserver s DB_ENGINE=postgres DB_HOST=localhost DB_NAME/USER/PASSWORD z .env.

## Šablony dokumentů (zakázkový list, nabídka, faktura)
Nastavení → Dokumenty → Šablony dokumentů. Každý typ dokumentu může mít více šablon (Excel .xlsx nebo HTML), jedna je výchozí.
Náhled dokumentu: v zakázce tlačítko Zakázkový list, u nabídky/faktury Náhled / PDF / tisk. V náhledu lze dočasně zvolit jinou šablonu (výchozí se tím nemění).

Faktura ISDOC: v náhledu faktury tlačítko **Stáhnout ISDOC** (nebo **ISDOC** v detailu faktury) stáhne fakturu jako soubor `.isdoc` (ISDOC 6.0.2) pro import do účetního programu. Soubor se vždy ověří proti oficiálnímu schématu `core/sablony/schemata/isdoc-invoice-6.0.2.xsd`. Testy: `python manage.py test core`.

Pro PDF a náhledy Excelových šablon je potřeba **LibreOffice**:
- Docker: je součástí obrazu, nic se neinstaluje.
- Windows bez Dockeru: nainstalujte LibreOffice z https://www.libreoffice.org/download/ (aplikace ho najde v `C:\Program Files\LibreOffice`),
  jinou cestu lze zadat proměnnou prostředí `LIBREOFFICE`.
Vlastní Excel: do buněk napište značky, např. `{{dokument.cislo}}`, řádek položek `{{polozka.popis}}` … (seznam v aplikaci: Značky pro vlastní šablony).
Bez značek se pole zkusí rozpoznat podle popisků. Vestavěné vzory se generují příkazem `python manage.py vytvor_vzory_sablon`.
