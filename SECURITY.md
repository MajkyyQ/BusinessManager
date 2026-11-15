# Bezpečnost

## Nahlášení zranitelnosti

Bezpečnostní chybu prosím **nehlaste veřejným issue**. Použijte soukromé hlášení na GitHubu:
záložka **Security → Report a vulnerability** v tomto repozitáři. Popište, co chyba umožňuje, jak ji zopakovat
a které verze se týká. Odpověď obvykle přijde do několika dnů.

## Podporované verze

Opravy vychází jen pro nejnovější verzi ve větvi `main`. Aktualizaci provede `aktualizace.bat`
(nebo `git pull` a `docker compose up -d --build`).

## Jak je aplikace zabezpečená

Bezpečnostní opatření, výsledky bezpečnostního auditu a doporučení pro provoz popisuje
[docs/12-bezpecnost.md](docs/12-bezpecnost.md).
