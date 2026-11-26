# 2. iDoklad

*Údaje ověřeny 2. 11. 2026 na oficiálním webu (zdroje dole).*

| Kritérium | Zjištění |
|---|---|
| Název | iDoklad |
| Společnost | Seyfor, a. s. (CZ; dříve Solitea), tedy stejná skupina jako Money S3/S4/S5 [1] |
| Typ aplikace | Webová aplikace + mobilní aplikace iOS/Android [1][3] |
| Hostování | Pouze cloud (SaaS výrobce), vlastní server ani lokální instalace nejsou možné |
| Licence | Proprietární, předplatné |
| Cena (Kč bez DPH / měsíc, roční · čtvrtletní · měsíční platba) | Zdarma 0 (1 uživatel, 5 kontaktů) · Základní 187 · 220 · 240 (2 uživatelé) · Oblíbený 358 · 397 · 430 (5 uživatelů) · Prémiový 625 · 703 · 750 (9 uživatelů) [2] |
| Free trial | Ano: 60 dní tarifu Prémiový, bez platební karty; 30denní garance vrácení peněz [2][3] |

## Pokrytí modulů BusinessManageru

| Modul | iDoklad | Poznámka |
|---|---|---|
| Zákazníci | ✓ | Adresář s doplněním z rejstříků a kontrolou spolehlivosti, výchozí sleva a splatnost na kontakt, historie fakturace klienta [3] |
| Zařízení + historie | ✗ | Neobsahuje |
| Zakázky | ◐ | „Obchodní případy“ sledují cestu nabídka → faktura → úhrada; žádný zakázkový list, stavy ani pracovní postup [3] |
| Práce | ✗ | Jen položky dokladu / ceník |
| Materiál | ◐ | Ceník a sklad (od Základní); skladové pohyby automaticky z faktur, ruční naskladnění/vyskladnění [2][4] |
| Dokumenty | ◐ | Faktury, zálohové faktury, daňové doklady k platbě, dobropisy, cenové nabídky, prodejky, pravidelné faktury; max. 5 příloh à 2 MB; objednávky chybí [5][6] |
| PDF / šablony | ◐ | Několik předdefinovaných vzhledů (např. „Reprezentativní“), barvy, logo, podpis, černobílá verze; 3 šablony v tarifu Zdarma; vlastní šablonu nahrát nelze [2][7]. **Náhled před uložením dokumentace nepopisuje**: tisk, PDF i odeslání jsou akce, které doklad nejdřív uloží [6] |
| Platby | ✓ | Propojení s bankou, automatické párování, upomínky, poděkování za úhradu (od Oblíbený) [2] |
| Kalendář | ✗ | Neobsahuje |
| Uživatelé / role | ◐ | Vlastník + sdílení uživatelé (mohou s doklady pracovat libovolně, nemohou měnit nastavení) + přístup účetní; jemnější role nejsou popsány [8] |
| Historie / audit | ✗ | Audit log změn není zdokumentován |
| Import / export | ◐ | Export XML pro Pohodu, propojení s Money S3/S4/S5 a Vario, export seznamů do XLSX/CSV, import faktur z XML (Pohoda, SuperFaktura), Inbox čte ISDOC u přijatých dokladů (od Oblíbený), API (od Oblíbený) [2][9][10][11] |

✓ = ano · ◐ = částečně / jen ve vyšším tarifu · ✗ = ne

## UI (z dokumentace, ověř v trialu)
Klasické rozhraní s horním/levým menu podle agend (Prodej, Nákup, Finance, Ceník a sklad, Kontakty), výrazné zelené tlačítko pro nový doklad, domovská stránka s přehledem cashflow v grafu. Formulář faktury je jedna dlouhá stránka, méně časté volby jsou schované pod „Zobrazit víc detailů“, položky se našeptávají z ceníku po třech znacích [6]. Působí trochu „účetněji“ a hustěji než Fakturoid.

## Výhody
- Nejdelší zkušební doba (60 dní, plná verze), tarif zdarma.
- Široká škála dokladů (prodejky, daňové doklady k platbě, pravidelné faktury) a daňová přiznání přímo v aplikaci.
- Silné napojení na účetní programy Money (stejný výrobce) a Pohodu.
- Jednoduchý sklad navázaný na faktury už v levném tarifu.

## Nevýhody vůči potřebám BusinessManageru
- Chybí zařízení, zakázkové listy, evidence práce a kalendář.
- Náhled dokladu před uložením není (dle dokumentace), na rozdíl od Fakturoidu a BM.
- Jen předdefinované vzhledy dokumentů, žádné vlastní šablony.
- Slabší řízení oprávnění, bez auditu změn.
- Pouze cloud, uzavřený kód; ceny bez DPH jsou vyšší než u Fakturoidu.

## Vhodnost pro malé firmy
Vhodný pro OSVČ a malé obchodní firmy, které chtějí fakturaci, jednoduchý sklad a návaznost na účetní (Money/Pohoda). Pro servisní firmu platí totéž co u Fakturoidu: pokryje fakturační část, ne servis a zakázky.

## Zdroje
1. iDoklad: Úvodní stránka. https://www.idoklad.cz/ [cit. 2026-11-02]
2. iDoklad: Ceník. https://www.idoklad.cz/cenik [cit. 2026-11-02]
3. iDoklad: Vlastnosti. https://www.idoklad.cz/vlastnosti [cit. 2026-11-02]
4. iDoklad: Karta Skladové pohyby (podpora). https://www.idoklad.cz/podpora/karta-skladove-pohyby [cit. 2026-11-02]
5. iDoklad: Prodej (podpora). https://www.idoklad.cz/podpora/prodej [cit. 2026-11-02]
6. iDoklad: Vystavení prvních dokladů. https://www.idoklad.cz/jak-zacit-s-idokladem/vystaveni-prvnich-dokladu [cit. 2026-11-02]
7. iDoklad: Nový vzhled faktury je tady (blog, 23. 3. 2018). https://www.idoklad.cz/blog/novy-vzhled-faktury-je-tady-k-tomu-spoustu-dalsich-novinek [cit. 2026-11-02]
8. iDoklad: Sdílený přístup více uživatelů (blog, 16. 9. 2019). https://www.idoklad.cz/?p=4070 [cit. 2026-11-02]
9. iDoklad: Komunikace s účetními systémy (podpora). https://www.idoklad.cz/podpora/komunikace-s-ucetnimi-systemy [cit. 2026-11-02]
10. iDoklad: Import faktur do iDokladu (podpora). https://www.idoklad.cz/podpora/import-faktur-do-idokladu [cit. 2026-11-02]
11. iDoklad: Inbox (podpora). https://www.idoklad.cz/podpora/inbox [cit. 2026-11-02]

## Co si vyzkoušet a nafotit (60denní trial, registrace zdarma bez karty)
1. Domovská stránka s přehledy (srovnání s dashboardem BM).
2. Celý formulář nové faktury včetně „Zobrazit víc detailů“ a našeptávání z ceníku.
3. **Ověřit, zda existuje náhled před uložením.** Pokud ne, nafotit menu „Další akce“ (tisk/PDF až po uložení) jako protipříklad k BM a Fakturoidu.
4. Nastavení → Prodej → Šablony: výběr vzhledu dokladu.
5. Cenová nabídka a její převod na fakturu, obchodní případ.
6. Ceník a sklad, karta skladových pohybů.
7. Nastavení → Uživatel → Seznam uživatelů (jak jednoduché je řízení přístupu).
