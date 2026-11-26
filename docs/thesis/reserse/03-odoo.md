# 3. Odoo

*Údaje ověřeny 2. 11. 2026. Ceník na odoo.com nešlo automaticky načíst (web blokuje roboty), ceny jsou proto z oficiálního oznámení přes tisk a z analýz; před odevzdáním je ověř ručně na https://www.odoo.com/cs_CZ/pricing a ceník si vyfoť.*

| Kritérium | Zjištění |
|---|---|
| Název | Odoo (dříve TinyERP / OpenERP) |
| Společnost | Odoo S.A., Belgie (Louvain-la-Neuve); zakladatel a CEO Fabien Pinckaers; cca 7 500 zaměstnanců, 28 mil. uživatelů [1][2] |
| Typ aplikace | Webová aplikace (modulární ERP, desítky aplikací) + mobilní aplikace |
| Hostování | Obojí: Odoo Online (SaaS), Odoo.sh (PaaS) nebo vlastní server / on-premise [1][3] |
| Licence | Dvojí: **Community** open-source (LGPLv3), **Enterprise** proprietární předplatné [1][4] |
| Cena | Community zdarma (platí se jen provoz a implementace). Enterprise (roční platba, za uživatele/měsíc): One App Free 0 € (jedna aplikace, neomezeně uživatelů) · Standard 19,90 € · Custom 29 € → 35 € po zdražení oznámeném 24. 9. 2026 · nový „light user“ 7,90 € [2]. Custom je nutný pro Studio, API, Odoo.sh a on-premise [3]. Měsíční platba je dražší, první rok bývá sleva. Implementace u českých partnerů pro malou firmu cca 150–400 tis. Kč [5] |
| Free trial | Ano: zkušební verze Odoo Online (obvykle 15 dní, délku ověř při registraci), Community si lze nainstalovat zdarma |

## Pokrytí modulů BusinessManageru

| Modul | Odoo | Poznámka |
|---|---|---|
| Zákazníci | ✓ | Aplikace Kontakty: firmy a kontaktní osoby pod nimi, napojení na CRM |
| Zařízení + historie | ◐ | Aplikace **Maintenance** (zařízení a požadavky na údržbu, Community) je primárně pro vlastní vybavení firmy; **Repairs** (Community) eviduje opravy produktů se sériovým číslem, záruku a náhradní díly; historie zařízení zákazníka se skládá z těchto záznamů [4] |
| Zakázky | ✓ | Repairs (opravní zakázky se stavy), Projekt (úkoly ve fázích, kanban), Field Service (výjezdy technika, jen Enterprise) [4] |
| Práce | ✓ | Výkazy práce (Timesheets), u Field Service pracovní listy (worksheets) [4] |
| Materiál | ✓ | Sklad (Inventory), díly v opravách se odepisují ze skladu [4] |
| Dokumenty | ✓ | Nabídky, prodejní a nákupní objednávky, faktury, přílohy u každého záznamu; aplikace Documents jen Enterprise [4] |
| PDF / šablony | ◐ | PDF sestavy (QWeb), logo a rozvržení dokumentu v nastavení; úprava šablon přes Studio (Custom) nebo vývojem. **Faktura/nabídka vzniká jako koncept (draft) s tlačítkem Náhled**, potvrzuje se až poté |
| Platby | ✓ | Účetnictví: bankovní synchronizace, párování plateb, upomínky |
| Kalendář | ✓ | Aplikace Kalendář, plánování (Planning) |
| Uživatelé / role | ✓ | Skupiny přístupových práv po aplikacích, pravidla na úrovni záznamů, více firem (Custom) |
| Historie / audit | ✓ | „Chatter“ u každého záznamu sleduje změny polí, zprávy a aktivity; audit trail v účetnictví |
| Import / export | ◐ | Import/export CSV a XLSX z libovolného seznamu, PDF, e-faktury UBL/CII; **ISDOC není ve standardu** (česká lokalizace obsahuje jen účtový rozvrh, DPH a vzhled faktury; ISDOC jen moduly třetích stran) [6] |

✓ = ano · ◐ = částečně / jen Enterprise · ✗ = ne

## UI (ověř v trialu)
Moderní, jednotné webové rozhraní: domovská obrazovka s ikonami aplikací, uvnitř aplikace horní menu, seznamy s přepínáním zobrazení (seznam, kanban, kalendář, graf, pivot), formuláře s „chatterem“ vpravo nebo dole. Stavy dokumentu jsou vidět jako „stavová lišta“ (koncept → potvrzeno → zaplaceno). Vzhled je čistý, ale množství aplikací a nastavení je pro nového uživatele zahlcující.

## Výhody
- Pokryje prakticky všechny moduly BM v jednom systému, včetně oprav, výkazů práce, skladu a kalendáře.
- Open-source Community verze, možnost vlastního serveru i cloudu.
- Výborný model stavů dokumentu (koncept → náhled → potvrzení) a historie změn u každého záznamu.
- Obrovská komunita a tisíce rozšíření.

## Nevýhody vůči potřebám BusinessManageru
- Pro malou servisní firmu je to „kanón na vrabce“: složité nastavení, bez partnera se těžko zavádí.
- Nejdůležitější servisní části (Field Service, Documents, Studio) jsou jen v placené Enterprise verzi.
- Česká legislativa není ve standardu kompletní (ISDOC, některé výkazy) a řeší se doplňky.
- Úprava vzhledu dokumentů vyžaduje Studio nebo programování, nejde jen nahrát vlastní Excel šablonu jako v BM.
- Cena: licence za uživatele + implementace ve statisících Kč.

## Vhodnost pro malé firmy
Funkčně ano, ekonomicky a provozně spíš ne. Community verze je zdarma, ale na vlastním serveru ji musí někdo spravovat a chybí jí servisní moduly z Enterprise. Enterprise v cloudu je pohodlná, ale pro 3–5 uživatelů vychází řádově na tisíce Kč měsíčně plus implementace. Hodí se pro firmy, které počítají s růstem.

## Zdroje
1. Wikipedia: Odoo. https://en.wikipedia.org/wiki/Odoo [cit. 2026-11-02]
2. The Brussels Times: Odoo announces €10-billion valuation and a partial price increase (24. 9. 2026). https://www.brusselstimes.com/2332306/odoo-announces-e10-billion-valuation-and-a-partial-price-increase [cit. 2026-11-02]
3. Swell: Odoo Pricing 2026. https://www.swell.is/content/odoo-pricing [cit. 2026-11-02] (sekundární zdroj, ověřit na odoo.com)
4. Odoo S.A.: zdrojový kód Odoo Community 19.0 (moduly repair, maintenance, project, hr_timesheet, stock, calendar; soubor LICENSE). https://github.com/odoo/odoo/tree/19.0 [cit. 2026-11-02]
5. Elfox: Kolik stojí ERP Odoo ve skutečnosti? (13. 3. 2026). https://elfox.cz/blog/odoo/kolik-stoji-erp-odoo-ve-skutecnosti-kompletni-rozpocet-implementace [cit. 2026-11-02]
6. Odoo S.A.: modul l10n_cz (Czech – Accounting), __manifest__.py. https://github.com/odoo/odoo/blob/19.0/addons/l10n_cz/__manifest__.py [cit. 2026-11-02]
7. Odoo S.A.: Ceník. https://www.odoo.com/cs_CZ/pricing [ověřit ručně]

## Co si vyzkoušet a nafotit (trial Odoo Online)
1. Ceník na odoo.com (screenshot jako doklad ceny k datu).
2. Domovská obrazovka s aplikacemi (navigace).
3. Nová faktura: stav **Koncept**, tlačítko **Náhled**, pak Potvrdit (srovnání s náhledem v BM).
4. Repairs: opravní zakázka se sériovým číslem, díly, stavová lišta.
5. Seznam zakázek v zobrazení kanban a kalendář.
6. Chatter s historií změn u záznamu (srovnání s auditem v BM).
7. Nastavení → Uživatelé → přístupová práva.
