# Checklist: zkušební verze a screenshoty pro rešerši

## 1. Kde co vyzkoušet

| Řešení | Přístup | Délka | Poznámka |
|---|---|---|---|
| Fakturoid | Veřejné demo bez registrace (Lite / Everyday / **Max**) + trial | 30 dní | Začni demem Max, je tam vše |
| iDoklad | Registrace zdarma, bez karty | 60 dní (tarif Prémiový) | |
| Odoo | Trial Odoo Online (registrace) | ověř při registraci | Vyber aplikace Faktury, Opravy, Sklad |
| ERPNext | Trial Frappe Cloud | 14 dní | |
| ABRA Flexi | Trial bez karty, zvol tarif Business | 30 dní | |
| HELIOS | Bez trialu, jen demo na vyžádání | – | Kontaktní formulář; jinak oficiální screenshoty/videa |

Tip: založ si ve všech stejná testovací data (1 zákazník, 2 položky, 1 faktura), ať jsou screenshoty srovnatelné.

## 2. Co nafotit u každého řešení (stejná sada = srovnatelnost)

1. **Hlavní obrazovka / dashboard** – navigace, první dojem.
2. **Seznam dokladů** (faktury) – přehlednost, filtry.
3. **Formulář nové faktury** – celý, ideálně jedním snímkem.
4. **Náhled dokumentu před vytvořením** – hlavní inspirace pro BM:
   - Fakturoid: tlačítko *Náhled* dole ve formuláři → plovoucí okno → *Vystavit*.
   - Odoo: faktura ve stavu *Koncept* → *Náhled* → *Potvrdit*.
   - ERPNext: Sales Invoice v *Draft* → *Print* (náhled) → *Submit*.
   - ABRA Flexi: *Náhled* tiskové sestavy.
   - iDoklad: ověř, zda náhled před uložením existuje; když ne, nafoť menu *Další akce* jako protipříklad.
5. **Nastavení vzhledu / šablon dokumentu** – srovnání s Excel šablonami se značkami v BM.
6. **Servisní/zakázková část**, pokud existuje (obchodní případy, Repairs, Maintenance Visit, Zakázky).
7. **Uživatelé a oprávnění.**
8. **Historie změn** záznamu (Odoo chatter, ERPNext časová osa).
9. **Ceník** na webu výrobce (doklad ceny k datu, hlavně Odoo – ten mi web nedovolil načíst).

## 3. Jak screenshoty zdokumentovat, aby to v práci obstálo

**Pojmenování souborů:** `reserse/<reseni>-<co>-<datum>.png`, např. `fakturoid-nahled-faktury-2026-11-05.png`. Hned si k nim veď tabulku: soubor · řešení · verze/tarif · URL · datum a čas pořízení.

**Popisek obrázku (caption)** vždy obsahuje: co je na obrázku, z jakého řešení, že jde o vlastní snímek a kdy byl pořízen. Příklad:
> Obrázek 1.1: Náhled faktury před vystavením v aplikaci Fakturoid (zdroj: vlastní snímek obrazovky z veřejné demoverze, pořízeno 5. 11. 2026)

U HELIOS z materiálů výrobce: *(zdroj: Asseco Solutions, a.s., URL, cit. datum)* + položka v bibliografii.

**V textu na obrázek vždy odkaž a řekni proč tam je**, jinak je to jen „líbilo se mi to“. Vzor:
> Fakturoid zobrazuje výslednou fakturu v plovoucím okně ještě před vystavením (obrázek 1.1), takže uživatel zkontroluje dokument bez nutnosti ho uložit a případně stornovat. Stejný princip byl použit v BusinessManageru, kde se před vytvořením dokladu zobrazí náhled vygenerovaného dokumentu (kapitola 9). Na rozdíl od Fakturoidu však BM generuje dokument z vlastní šablony firmy.

Tím je vazba inspirace → návrh dohledatelná. Ideálně dej vedle sebe screenshot cizího řešení a odpovídající obrazovku BM.

**Právní poznámka:** snímky obrazovky cizí aplikace v bakalářské práci jsou citací podle § 31 autorského zákona (č. 121/2000 Sb.), pokud uvedeš zdroj a použiješ je v rozsahu nutném pro rozbor. Proto u každého obrázku zdroj.

**Citlivé údaje:** na screenshotech nesmí být tvoje osobní údaje z registrace (e-mail, jméno v rohu) – zakryj je nebo použij demo.

## 4. Vložení do LaTeXu
Obrázky dej do `obrazky/reserse/` a použij šablonu na konci `kapitoly/01-reserse.tex` (zakomentovaný blok `figure`).
