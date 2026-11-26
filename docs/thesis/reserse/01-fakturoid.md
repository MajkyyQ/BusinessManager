# 1. Fakturoid

*Údaje ověřeny 2. 11. 2026 na oficiálním webu (zdroje dole).*

| Kritérium | Zjištění |
|---|---|
| Název | Fakturoid |
| Společnost | Fakturoid s.r.o., Praha (CZ); založili Lukáš Konarovský a Jan Korbel, v provozu od 12/2009 [1] |
| Typ aplikace | Webová aplikace (responzivní) + mobilní aplikace iOS/Android [2][3] |
| Hostování | Pouze cloud (SaaS provozovaný výrobcem), vlastní server ani lokální instalace nejsou možné |
| Licence | Proprietární, předplatné |
| Cena (ceny s DPH, měsíční platba; roční platba cca o 8 % levnější) | Zdarma 0 Kč (1 uživatel, max. 5 odběratelů) · Na lehko 199 Kč/měs. · Na každý den 279 Kč/měs. · Na maximum 519 Kč/měs. · další uživatel 120 Kč/měs. · 50% sleva první rok pro začínající podnikatele · 30 dní zkušební verze [2][4][5] |
| Free trial / demo | Ano: 30 dní všech funkcí + 3 veřejná dema bez registrace (Lite, Everyday, Max) [3] |

## Pokrytí modulů BusinessManageru

| Modul | Fakturoid | Poznámka |
|---|---|---|
| Zákazníci | ✓ | Kontakty s automatickým doplněním z registrů (ARES), kontrola DIČ ve VIES, import/export kontaktů; samostatná evidence kontaktních osob u firmy není hlavní funkcí [3] |
| Zařízení + historie | ✗ | Nic takového neobsahuje |
| Zakázky (listy, stavy, postup) | ◐ | „Obchodní případy“ s vlastními fázemi, dalšími kroky, termíny a odpovědnou osobou (jen Na maximum); nejde o zakázkový list s pracovním postupem [6] |
| Práce (provedené úkony) | ✗ | Jen položky faktury / ceník, žádná evidence úkonů |
| Materiál | ◐ | Ceník a skladové položky (Na každý den), pohyby a inventura (Na maximum) [3][7] |
| Dokumenty | ◐ | Faktury, zálohové/proforma, dobropisy, dodací listy, nabídky (Na maximum), max. 5 příloh k dokladu; objednávky chybí [3][8] |
| PDF / šablony | ◐ | 6 předdefinovaných vzhledů, logo, razítko, barva, QR platba; vlastní šablonu nahrát nelze. **Náhled faktury před vystavením** v plovoucím okně, z náhledu lze rovnou vystavit [3][9] |
| Platby | ✓ | Automatické párování plateb z banky, upomínky (od Na každý den), PayPal/GoPay (Na maximum) [3] |
| Kalendář | ✗ | Jen termíny kroků u obchodních případů, bez kalendáře |
| Uživatelé / role | ✓ | Majitel, Zápis a čtení, Čtení, Účetní + jemnější oprávnění na sekce [10] |
| Historie / audit | ◐ | Je vidět, kdo doklad vystavil/stornoval, zamykání zaúčtovaných dokladů; ucelený audit log změn web nezmiňuje [3][10] |
| Import / export | ✓ | PDF s vrstvou ISDOC, export .isdoc, import ISDOC do nákladů, export pro účetní programy (Excel, CSV, XML, Pohoda), veřejné API [3][11] |

✓ = ano · ◐ = částečně / jen ve vyšším tarifu · ✗ = ne

## UI (z dokumentace, ověř v demu)
Čisté, minimalistické rozhraní zaměřené na jeden úkol: vystavit fakturu. Levé menu (Faktury, Náklady, Kontakty, Sklad, Přehledy), tmavý režim, změna barvy menu. Workflow je velmi krátké: zákazník → položky → náhled → vystavit/odeslat. Pro rešerši je zajímavý hlavně náhled před vystavením, který řeší totéž co BusinessManager [9].

## Výhody
- Nejjednodušší a nejrychlejší vystavení faktury ze srovnávaných řešení, česká legislativa vyřešená (DPH, ISDOC, QR platba, registry).
- Náhled dokladu před vystavením, webfaktura, informace, zda klient fakturu viděl.
- Párování plateb a upomínky, nízká cena, tarif zdarma a veřejné demo.
- Nic se neinstaluje ani nespravuje.

## Nevýhody vůči potřebám BusinessManageru
- Chybí servisní část: zařízení a jejich historie, zakázkové listy s postupem, evidence práce, kalendář.
- Vzhled dokumentů jen z 6 hotových šablon, nelze použít vlastní firemní šablonu (např. Excel se značkami jako v BM).
- Nabídky, obchodní případy, číselné řady a sklad s pohyby jen v nejdražším tarifu.
- Data jsou pouze v cloudu výrobce, nelze provozovat na vlastním serveru; uzavřený kód.

## Vhodnost pro malé firmy
Velmi vhodný pro OSVČ a malé firmy, které potřebují hlavně fakturovat: nulové náklady na provoz, nízká cena, přehledné UI. Pro servisní firmu (zařízení, zakázky, práce) ale pokryje jen fakturační konec procesu a zbytek by musela vést jinde.

## Zdroje
1. Fakturoid: O Fakturoidu. https://fakturoid.cz/o-nas [cit. 2026-11-02]
2. Fakturoid: Nový ceník (blog, 26. 2. 2025). https://www.fakturoid.cz/blog/2025/02/26/nove-tarify [cit. 2026-11-02]
3. Fakturoid: Podrobné srovnání tarifů. https://www.fakturoid.cz/podrobne-srovnani-tarifu [cit. 2026-11-02]
4. Fakturoid: Ceník. https://www.fakturoid.cz/cenik [cit. 2026-11-02]
5. Fakturoid: Úvodní stránka. https://www.fakturoid.cz/ [cit. 2026-11-02]
6. Fakturoid: Obchodní případy. https://www.fakturoid.cz/obchodni-pripady [cit. 2026-11-02]
7. Fakturoid: Sklad ve Fakturoidu. https://www.fakturoid.cz/podpora/sklad/sklad-ve-fakturoidu [cit. 2026-11-02]
8. Fakturoid: Nabídky (podpora). https://www.fakturoid.cz/podpora/faktury/nabidky [cit. 2026-11-02]
9. Fakturoid: Náhled faktury (podpora). https://www.fakturoid.cz/podpora/faktury/nahled-faktury [cit. 2026-11-02]
10. Fakturoid: Uživatelé a oprávnění (podpora). https://www.fakturoid.cz/podpora/nastaveni/uzivatele-a-opravneni [cit. 2026-11-02]
11. Fakturoid: ISDOC (podpora). https://www.fakturoid.cz/podpora/faktury/isdoc [cit. 2026-11-02]

## Co si vyzkoušet a nafotit (veřejné demo „Max“, bez registrace)
1. Formulář nové faktury, celý (Obr.: formulář vystavení faktury).
2. Tlačítko a okno **Náhled** před vystavením (hlavní inspirace pro náhled v BM).
3. Výběr vzhledu faktury v nastavení (6 šablon) – pro srovnání s vlastními šablonami BM.
4. Nabídka → „Vystavit fakturu“ (převod nabídky na fakturu).
5. Obchodní případy s fázemi (nejbližší obdoba zakázek).
6. Hlavní přehled / dashboard a levé menu (navigace).
