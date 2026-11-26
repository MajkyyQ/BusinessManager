# 5. ABRA (ABRA Flexi / ABRA Aiva)

*Údaje ověřeny 2. 11. 2026 na oficiálním webu (zdroje dole). ABRA dnes nabízí dva produkty: **ABRA Flexi** (dříve FlexiBee) pro malé a střední firmy a **ABRA Aiva** (nástupce ABRA Gen) pro střední a velké firmy. Pro srovnání s BM je relevantní hlavně Flexi.*

| Kritérium | Zjištění |
|---|---|
| Název | ABRA Flexi; ABRA Aiva |
| Společnost | ABRA Software s.r.o., Praha (IČO 25097563); cca 35 let na trhu, 7 300+ firem, 33 000+ uživatelů [1] |
| Typ aplikace | Flexi: webová aplikace + desktopový klient pro Windows, Linux i macOS [2]. Aiva: ERP klient/server [3] |
| Hostování | Flexi: primárně cloud ABRA (AWS); vlastní server možný jen s placenou rozšířenou podporou [2]. Aiva: cloud i on-premise [1][3] |
| Licence | Proprietární, předplatné bez vstupního poplatku za licenci [1] |
| Cena | **Flexi** (za pojmenovaného uživatele/měs., měsíční · roční platba): Basic 425 · 390 Kč, Business 1 055 · 967 Kč, Premium 1 375 · 1 260 Kč; uživatelé jen pro čtení zdarma; minimum 2 050 Kč/rok; servisní práce 2 250 Kč/h. Web neuvádí, zda jde o ceny s DPH (u B2B nabídky se předpokládá bez DPH) [2]. **Aiva**: cena jen na poptávku, nasazení „stovky tisíc až jednotky milionů korun“ [3] |
| Free trial | Flexi: 30 dní všech tarifů bez karty [2]. Aiva: jen demo na vyžádání [1] |

## Pokrytí modulů BusinessManageru (ABRA Flexi)

| Modul | ABRA Flexi | Poznámka |
|---|---|---|
| Zákazníci | ✓ | Adresář firem s kontaktními osobami (napojení na ARES je standard českých systémů, v trialu ověř) |
| Zařízení + historie | ◐ | Výrobní (sériová) čísla na skladu; evidence zařízení zákazníka se servisní historií není [2] |
| Zakázky | ◐ | Modul Zakázky (od Business) slouží hlavně jako analytické středisko pro náklady/výnosy; stavy a pracovní postup jako v BM nemá [2] |
| Práce | ✗ | Evidence provedených úkonů chybí (jen položky dokladů) |
| Materiál | ✓ | Ceník, sklad (průměrné ceny), výrobní čísla; šarže, rezervace, FIFO ve vyšších tarifech [2] |
| Dokumenty | ✓ | Nabídky, poptávky, objednávky (od Business), faktury, zálohy, přílohy [2] |
| PDF / šablony | ◐ | Tisk s tlačítkem **Náhled** (náhled sestavy → tisk/PDF/e-mail), uživatelské tiskové sestavy, konfigurovatelné reporty bez programování (zatím jen faktura vydaná a objednávka přijatá) [4][5] |
| Platby | ✓ | Banka, pokladna, párování plateb, platební terminál (od Business) [2] |
| Kalendář | ✗ | Neobsahuje |
| Uživatelé / role | ✓ | Standardní role (administrátor, účetní, obchodník, skladník, jen čtení…) + vlastní role; pokročilá práva a viditelnost dat v Premium [2][6] |
| Historie / audit | ◐ | Zamykání dokladů a období; ucelený audit log dokumentace nepopisuje [6] |
| Import / export | ✓ | ISDOC a e-faktura ve všech tarifech, import z Excelu (od Business), PDF, REST API (placený přístup), EDI (Premium) [2] |

✓ = ano · ◐ = částečně / jen vyšší tarif · ✗ = ne

## UI (ověř v trialu)
Klasický „účetní“ systém: modulové menu (Adresář, Ceník, Sklad, Prodej, Nákup, Účetnictví), seznamy záznamů v tabulkách a formuláře s mnoha záložkami. Webové rozhraní i desktop jsou funkčně silné, ale hustší a méně moderní než Fakturoid nebo Odoo; předpokládá uživatele se znalostí účetnictví.

## Výhody
- Plnohodnotné české účetnictví a legislativa (DPH, ISDOC, mzdy) v jednom systému.
- Náhled tiskové sestavy před tiskem/odesláním, konfigurovatelné reporty.
- Desktopový klient pro všechny tři platformy i webový přístup; uživatelé pro čtení zdarma.
- Transparentní veřejný ceník (u Flexi) a 30denní trial.

## Nevýhody vůči potřebám BusinessManageru
- Chybí servisní část: zařízení s historií, evidence práce, zakázkový list s postupem, kalendář.
- Nabídky, objednávky a zakázky až v tarifu Business (1 055 Kč/uživatel/měs.), tedy výrazně dražší než fakturační nástroje.
- UI je orientované na účetní, ne na technika v terénu.
- Vlastní server jen s placenou podporou, uzavřený kód; Aiva je pro malou firmu cenově mimo.

## Vhodnost pro malé firmy
ABRA Flexi Basic je vhodná pro malou firmu, která chce vést kompletní účetnictví sama. Pro servisní firmu s potřebou nabídek a zakázek vychází Business pro 3 uživatele na cca 3 000+ Kč měsíčně, a servisní evidenci stejně nepokryje. ABRA Aiva je určená středním a velkým firmám.

## Zdroje
1. ABRA Software: Úvodní stránka. https://www.abra.eu/ [cit. 2026-11-02]
2. ABRA Software: ABRA Flexi – Ceník. https://www.abra.eu/flexi/cenik/ [cit. 2026-11-02]
3. ABRA Software: ABRA Aiva – Cena systému. https://www.abra.eu/erp-system-abra-aiva/cena-systemu/ [cit. 2026-11-02]
4. ABRA Flexi podpora: Tisky. https://intercom.help/podpora-flexi/cs/articles/4541963-tisky [cit. 2026-11-02]
5. ABRA Flexi podpora: Konfigurovatelné reporty. https://intercom.help/podpora-flexi/cs/articles/7064138-konfigurovatelne-reporty [cit. 2026-11-02]
6. ABRA Flexi podpora: Uživatelské role. https://intercom.help/podpora-flexi/cs/articles/4552520-uzivatelske-role [cit. 2026-11-02]

## Co si vyzkoušet a nafotit (30denní trial ABRA Flexi, zvol tarif Business)
1. Hlavní obrazovka a modulové menu (navigace, hustota UI).
2. Faktura vydaná → **Náhled** tiskové sestavy (srovnání s náhledem v BM a Fakturoidu).
3. Editor konfigurovatelných reportů.
4. Nabídka → objednávka → faktura (návaznost dokladů).
5. Modul Zakázky: co přesně eviduje.
6. Nastavení uživatelských rolí.
