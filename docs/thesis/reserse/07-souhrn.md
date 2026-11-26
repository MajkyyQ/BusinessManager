# Souhrnné srovnání (stav 2. 11. 2026)

| Řešení | Společnost | Typ | Hostování | Licence | Cena / měsíc | Malá firma |
|---|---|---|---|---|---|---|
| Fakturoid | Fakturoid s.r.o. (CZ) | web + mobil | cloud | proprietární | 0–519 Kč s DPH | vysoká (jen fakturace) |
| iDoklad | Seyfor, a.s. (CZ) | web + mobil | cloud | proprietární | 0–750 Kč bez DPH | vysoká (jen fakturace) |
| Odoo | Odoo S.A. (BE) | web + mobil | cloud i vlastní server | LGPLv3 / proprietární | Community 0; 19,90–35 €/uživatel | střední |
| ERPNext | Frappe Technologies (IN) | web | cloud i vlastní server | GPLv3 | 0; cloud od 5 USD | střední (bez CZ lokalizace) |
| ABRA Flexi | ABRA Software s.r.o. (CZ) | web + desktop | cloud (vlastní server s příplatkem) | proprietární | 390–1 375 Kč/uživatel | střední |
| HELIOS iNuvio | Asseco Solutions, a.s. (CZ) | desktop Windows | vlastní server, cloud u partnerů | proprietární | na poptávku | nízká |
| **BusinessManager** | vlastní | web | vlastní server / PC | open-source | 0 | cíl |


## Závěr v jedné větě
Fakturační nástroje jsou levné a přehledné, ale nemají servisní část; ERP systémy ji mají, ale jsou složité a drahé (nebo bez české lokalizace). Žádné řešení nespojuje servis + vlastní šablony + ISDOC + jednoduché UI + provoz zdarma na vlastním PC, a to je mezera, kterou řeší BusinessManager.

## Inspirace převzaté do BM - vše píši v dokumentu Rešerše řešení
- iDoklad - sekce pokladna jako možné extension (modul na přidání)
- iDoklad - upozornění a upomínky
- Abra - tabulka filtrování pro stav zakázky
- Abra - detail celkového počtu faktur + jejich společná cena
- Odoo - namísto tabulkového zobrazení, možnost zobrazit zákazníky, zařízení atd jako kanban

Podrobnosti a zdroje: soubory 01–06 v této složce. LaTeX kapitola: `thesis-dokumentace/kapitoly/01-reserse.tex` + `thesis-dokumentace/reserse.bib`.
