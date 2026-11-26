# 4. ERPNext

*Údaje ověřeny 2. 11. 2026 na oficiálním webu a ve zdrojovém kódu (zdroje dole).*

| Kritérium | Zjištění |
|---|---|
| Název | ERPNext |
| Společnost | Frappe Technologies Pvt. Ltd. (Indie, Mumbai) + komunita; původní autor Rushabh Mehta; první verze 2010 [1] |
| Typ aplikace | Webová aplikace (Python / Frappe Framework, MariaDB), responzivní pro mobil [1][2] |
| Hostování | Obojí: vlastní server zdarma (instalační skripty, Docker) nebo Frappe Cloud [3] |
| Licence | Open-source, GNU GPL v3; žádné funkce za paywallem [1][2][4] |
| Cena | Software zdarma. Frappe Cloud podle výkonu, **ne za uživatele**: sdílený web od 5 USD/měs., server od 20 USD/měs., dedikovaný od 125 USD/měs.; Enterprise na poptávku [3] |
| Free trial | Ano: 14 dní na Frappe Cloud; veřejné demo [3] |

## Pokrytí modulů BusinessManageru

| Modul | ERPNext | Poznámka |
|---|---|---|
| Zákazníci | ✓ | Zákazník, kontakty, adresy, skupiny zákazníků, CRM (leady, příležitosti) [2] |
| Zařízení + historie | ✓ | **Sériová čísla** s vazbou na zákazníka a záruku, **Warranty Claim** (reklamace), **Maintenance Schedule / Visit** (plán a záznam servisních návštěv u zákazníka); historie se dá dohledat přes sériové číslo [4] |
| Zakázky | ◐ | Maintenance Visit se stavem dokončení, Issue (tikety se SLA), Projekty a úkoly; samostatný „zakázkový list“ jako v BM není, skládá se z více dokumentů [2][4] |
| Práce | ✓ | Timesheety (výkazy práce) navázané na projekt/úkol, fakturovatelné [2][4] |
| Materiál | ✓ | Sklad, položky, sklady, šarže a sériová čísla, skladová kniha [2] |
| Dokumenty | ✓ | Nabídky, prodejní a nákupní objednávky, faktury, přílohy u každého dokumentu [2] |
| PDF / šablony | ✓ | Print Formats: vestavěný editor tiskových šablon a vlastní HTML/Jinja šablony bez placené licence; **náhled tisku je dostupný i u konceptu (Draft) před potvrzením (Submit)** [2] |
| Platby | ✓ | Payment Entry, bankovní odsouhlasení (párování) [2] |
| Kalendář | ✓ | Kalendářové zobrazení u dokumentů s datem (úkoly, servisní návštěvy, události) |
| Uživatelé / role | ✓ | Role a oprávnění až na úroveň polí a dokumentů (Role Permission Manager) |
| Historie / audit | ✓ | Frappe ukládá verze každé změny dokumentu (doctype Version), časová osa u dokumentu [5] |
| Import / export | ◐ | Data Import / Export pro CSV a XLSX u každého typu dokumentu, PDF, REST API; **ISDOC ani česká lokalizace (DPH výkazy) nejsou** – oficiální regionální modul pro ČR neexistuje, jen český překlad UI [4][6] |

✓ = ano · ◐ = částečně · ✗ = ne

## UI (ověř v demu / trialu)
„Desk“ rozhraní: postranní panel s moduly (Workspaces), seznamy s filtry a přepínáním zobrazení (seznam, report, kanban, kalendář, galerie), formuláře se sekcemi a časovou osou změn dole. Stavy dokumentu Draft → Submitted → Cancelled. Funkčně velmi bohaté, vizuálně spíš „technické“ a husté; nováček se v množství polí a pojmů (doctype, submit, amend) ztrácí.

## Výhody
- Plně open-source bez placených modulů, včetně servisní části (sériová čísla, záruky, servisní návštěvy) – nejbližší funkční obdoba BM ze srovnávaných řešení.
- Vlastní tiskové šablony zdarma, náhled tisku u konceptu.
- Kompletní historie verzí dokumentů, jemná oprávnění.
- Levný cloud bez poplatků za uživatele, nebo vlastní server zdarma.

## Nevýhody vůči potřebám BusinessManageru
- Chybí česká legislativa (ISDOC, DPH výkazy, ARES), v ČR prakticky žádní implementační partneři.
- Servisní proces je rozdrobený do několika dokumentů (sériové číslo, údržba, reklamace, projekt), chybí jeden přehledný zakázkový list.
- UI je složité a „technické“, vyžaduje zaškolení; Excel šablony se značkami jako v BM nejsou.
- Vlastní provoz vyžaduje znalost Linuxu, Pythonu a MariaDB.

## Vhodnost pro malé firmy
Cenou velmi vhodný (zdarma nebo od 5–20 USD/měs. bez ohledu na počet uživatelů), funkčně silný. Překážkou pro českou malou firmu je chybějící lokalizace a náročnost nasazení a UI. Ze všech řešení je architekturou (open-source webová aplikace v Pythonu) nejbližší BusinessManageru, což se hodí zmínit v práci.

## Zdroje
1. Wikipedia: ERPNext. https://en.wikipedia.org/wiki/ERPNext [cit. 2026-11-02]
2. Frappe Technologies: ERPNext. https://frappe.io/erpnext [cit. 2026-11-02]
3. Frappe Technologies: ERPNext Pricing. https://frappe.io/erpnext/pricing [cit. 2026-11-02]
4. Frappe Technologies: zdrojový kód ERPNext, větev develop (license.txt; doctypes serial_no, warranty_claim, maintenance_schedule, maintenance_visit, timesheet, issue). https://github.com/frappe/erpnext [cit. 2026-11-02]
5. Frappe Technologies: Frappe Framework, doctype Version. https://github.com/frappe/frappe [cit. 2026-11-02]
6. Frappe Forum: Is there a company running ERPNext in Czech Republic or Slovakia? https://discuss.frappe.io/t/is-there-a-company-that-is-running-erpnext-in-czech-republic-or-slovakia/42920 [cit. 2026-11-02]

## Co si vyzkoušet a nafotit (14denní trial Frappe Cloud)
1. Úvodní Workspace a postranní panel (navigace).
2. Sales Invoice v konceptu → **Print / náhled** před Submit.
3. Editor tiskových šablon (Print Format Builder) – srovnání se šablonami BM.
4. Serial No s historií a Maintenance Visit u zákazníka (obdoba zařízení v BM).
5. Časová osa změn dole ve formuláři (audit).
6. Seznam v kalendářovém zobrazení.
