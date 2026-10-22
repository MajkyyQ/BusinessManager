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
