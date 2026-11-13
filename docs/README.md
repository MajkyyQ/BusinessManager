# Dokumentace BusinessManager

BusinessManager je webová aplikace pro malou servisní firmu: eviduje zákazníky, jejich zařízení a servisní zakázky a z uložených údajů vytváří zakázkové listy, cenové nabídky a faktury (PDF i elektronická faktura ISDOC). Běží na jednom firemním počítači a zaměstnanci s ní pracují v prohlížeči.

## Instalace a spuštění

- **[Rychlá instalace na Windows](../README.md#rychlá-instalace-windows)** – čtyři kroky: Docker Desktop, stažení, dvojklik na `instalace.bat`, průvodce v prohlížeči.
- **[Podrobný návod k instalaci (INSTALACE.md)](../INSTALACE.md)** – čistá instalace krok za krokem, přístup z ostatních PC, [zálohování](../INSTALACE.md#8-zálohování), [obnova ze zálohy](../INSTALACE.md#obnova-ze-zálohy-např-na-nový-pc) a [řešení potíží](../INSTALACE.md#10-když-něco-nefunguje).
- **Aktualizace na novou verzi** – dvojklik na `aktualizace.bat` (záloha, stažení nové verze z GitHubu, spuštění; data i `.env` zůstanou), viz [README](../README.md).
- **[Vývoj a testování](09-vyvoj-a-testovani.md)** – spuštění bez Dockeru, konfigurace, testovací data, automatické testy.

## Obsah dokumentace

| Kapitola | O čem je |
|:--|:--|
| [1. Popis aplikace](01-popis-aplikace.md) | k čemu aplikace slouží, pro koho je a jak vypadá typický průběh zakázky |
| [2. Funkce aplikace](02-funkce.md) | všechny funkce z pohledu uživatele i toho, co se děje na pozadí |
| [3. Použité technologie](03-technologie.md) | Python, Django, PostgreSQL, Bootstrap, htmx, openpyxl, LibreOffice, Docker a proč byly zvoleny |
| [4. Architektura](04-architektura.md) | vrstvy aplikace, práce se soubory, zabezpečení, nasazení v Dockeru |
| [5. Struktura projektu](05-struktura-projektu.md) | co je ve kterém souboru a složce |
| [6. Tok dat](06-tok-dat.md) | cesta údajů od přijetí zakázky po hotový dokument |
| [7. Databáze](07-databaze.md) | databázové schéma (ER diagramy), popis všech tabulek a vazeb |
| [Přehled tabulek a sloupců](databaze-tabulky.md) | úplný seznam sloupců, datových typů a integritních omezení (generuje se z modelů) |
| [8. Šablony dokumentů, PDF a ISDOC](08-sablony-dokumentu.md) | Excelové a HTML šablony, značky, editor šablon, převod do PDF, export a import ISDOC |
| [9. Vývoj a testování](09-vyvoj-a-testovani.md) | spuštění pro vývoj, proměnné prostředí, automatické testy, úprava databáze |
| [10. První nastavení po instalaci](10-prvni-nastaveni.md) | co musí administrátor nastavit po prvním spuštění: údaje o firmě, role, zaměstnanci, typy úkonů a volitelné kroky |
| [11. Volitelné moduly](11-moduly.md) | rozšíření, která nejsou součástí aplikace (např. odesílání e-mailů): jak modul přidat, aktualizovat, vypnout a jak napsat nový |

## Rychlá orientace

- **Chci aplikaci nainstalovat:** [README](../README.md#rychlá-instalace-windows), potom [INSTALACE.md](../INSTALACE.md).
- **Mám nainstalováno, co dál?** [První nastavení po instalaci](10-prvni-nastaveni.md): firma, role, zaměstnanci, typy úkonů.
- **Chci vědět, co aplikace umí:** [Popis aplikace](01-popis-aplikace.md) a [Funkce aplikace](02-funkce.md).
- **Chci si udělat vlastní šablonu faktury:** [Šablony dokumentů](08-sablony-dokumentu.md); seznam značek je i přímo v aplikaci (Dokumenty → Šablony dokumentů → Značky pro vlastní šablony).
- **Chci přidat modul (např. odesílání e-mailů):** [Volitelné moduly](11-moduly.md).
- **Chci upravit kód:** [Architektura](04-architektura.md), [Struktura projektu](05-struktura-projektu.md), [Databáze](07-databaze.md) a [Vývoj a testování](09-vyvoj-a-testovani.md).

Aplikace je open source pod licencí [MIT](../LICENSE).
