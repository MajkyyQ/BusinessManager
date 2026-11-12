# Referenční přehled tabulek a sloupců

> Tento soubor je vygenerovaný přímo z modelů v `core/models.py` skriptem `docs/generuj_prehled_databaze.py`, takže přesně odpovídá aktuální databázi. Význam tabulek a vazeb vysvětluje [Databáze](07-databaze.md).

Zkratky: **PK** primární klíč, **FK** cizí klíč, **M:N** vazba přes vazební tabulku. Sloupec *Povinné* říká, zda databáze dovolí prázdnou hodnotu.

## Obsah

- [Zakaznik](#zakaznik) – zákazník
- [KontaktniOsoba](#kontaktniosoba) – kontaktní osoba
- [ZakaznikKontakt](#zakaznikkontakt) – kontakt zákazníka
- [Zarizeni](#zarizeni) – zařízení
- [StavZakazky](#stavzakazky) – stav zakázky
- [Zamestnanec](#zamestnanec) – zaměstnanec
- [Opravneni](#opravneni) – oprávnění
- [Role](#role) – role
- [Zakazka](#zakazka) – zakázka
- [ZakazkaKontakt](#zakazkakontakt) – kontakt na zakázce
- [TypUkonu](#typukonu) – typ úkonu
- [ProvedenyUkon](#provedenyukon) – provedený úkon
- [Material](#material) – materiál
- [PouzityMaterial](#pouzitymaterial) – použitý materiál
- [Fotografie](#fotografie) – fotografie
- [Priloha](#priloha) – příloha
- [Nabidka](#nabidka) – nabídka
- [PolozkaNabidky](#polozkanabidky) – položka nabídky
- [Objednavka](#objednavka) – objednávka
- [Faktura](#faktura) – faktura
- [PolozkaFaktury](#polozkafaktury) – položka faktury
- [Platba](#platba) – platba
- [Dodavatel](#dodavatel) – dodavatel
- [PrijataFaktura](#prijatafaktura) – přijatá faktura
- [KalendarUdalost](#kalendarudalost) – událost kalendáře
- [HistorieZmen](#historiezmen) – změna
- [NastaveniFirmy](#nastavenifirmy) – nastavení firmy
- [CiselnaRada](#ciselnarada) – číselná řada
- [SazbaDPH](#sazbadph) – sazba DPH
- [SablonaDokumentu](#sablonadokumentu) – šablona dokumentu

## Zakaznik

Tabulka `core_zakaznik` – zákazník.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `typ_zakaznika` | text (20); hodnoty: „Firma“, „Soukromá osoba“ | ne |  |
| `jmeno` | text (150) | ne |  |
| `firma` | text (255) | ne |  |
| `adresa` | text (200) | ne |  |
| `telefon` | text (20) | ne |  |
| `email` | text (254) | ne |  |
| `ico` | text (8) | ne | IČO |
| `dic` | text (14) | ne | DIČ |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |

**Integritní omezení:**

- `zakaznik_typ_platny` – CHECK `("typ_zakaznika" IN ('Firma', 'Soukromá osoba') OR "typ_zakaznika" = '')`
- `zakaznik_jmeno_nebo_firma` – CHECK `(NOT ("jmeno" = '') OR NOT ("firma" = ''))`

## KontaktniOsoba

Tabulka `core_kontaktniosoba` – kontaktní osoba.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `jmeno` | text (150) | ne |  |
| `telefon` | text (20) | ne |  |
| `email` | text (254) | ne |  |
| `poznamka` | dlouhý text | ne |  |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |

## ZakaznikKontakt

Tabulka `core_zakaznikkontakt` – kontakt zákazníka.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `zakaznik_id` | FK → Zakaznik (CASCADE) | ano |  |
| `kontakt_id` | FK → KontaktniOsoba (CASCADE) | ano |  |
| `poznamka` | text (200) | ne |  |

**Integritní omezení:**

- `zakaznik_kontakt_unikatni` – UNIQUE (zakaznik, kontakt)

## Zarizeni

Tabulka `core_zarizeni` – zařízení.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `zakaznik_id` | FK → Zakaznik (PROTECT) | ano |  |
| `vyrobce` | text (100) | ne |  |
| `typ` | text (100) | ne |  |
| `seriove_cislo` | text (100), index | ne |  |
| `popis` | dlouhý text | ne |  |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |

## StavZakazky

Tabulka `core_stavzakazky` – stav zakázky.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev` | text (100) | ano |  |
| `popis` | dlouhý text | ne |  |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |
| `poradi` | celé číslo | ano |  (výchozí 0) |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |
| `barva` | text (7) | ano | Barva štítku stavu v přehledech, kanbanu a na pracovní ploše zakázky. (výchozí #0dcaf0) |

## Zamestnanec

Tabulka `core_zamestnanec` – zaměstnanec.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `jmeno` | text (100) | ne |  |
| `prijmeni` | text (100) | ne |  |
| `telefon` | text (20) | ne |  |
| `email` | text (254) | ne |  |
| `pracovni_pozice` | text (100) | ne |  |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |
| `uzivatel_id` | 1:1 → auth_user (SET_NULL) | ne | uživatelský účet |

## Opravneni

Tabulka `core_opravneni` – oprávnění.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `kod` | text (100), unikátní | ano |  |
| `nazev` | text (200) | ne |  |
| `popis` | dlouhý text | ne |  |

## Role

Tabulka `core_role` – role.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev` | text (100) | ano |  |
| `popis` | dlouhý text | ne |  |
| `je_administrator` | logická hodnota | ano |  (výchozí ne) |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |

## Zakazka

Tabulka `core_zakazka` – zakázka.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `cislo_zakazky` | text (50), unikátní | ne | Prázdné = vygeneruje se automaticky |
| `zakaznik_id` | FK → Zakaznik (PROTECT) | ano |  |
| `stav_id` | FK → StavZakazky (PROTECT) | ne |  |
| `datum_prijeti` | datum a čas | ne |  |
| `datum_vydani` | datum a čas | ne |  |
| `identifikacni_cislo` | text (50), index | ne |  |
| `sekundarni_cislo` | text (50), index | ne |  |
| `popis_zavady` | dlouhý text | ne |  |
| `poznamka` | dlouhý text | ne |  |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |
| `datum_upravy` | datum a čas | ne |  |
| `poradi` | celé kladné číslo | ne | pořadové číslo – Pořadí z čísla zakázky; přebírá ho nabídka. |

## ZakazkaKontakt

Tabulka `core_zakazkakontakt` – kontakt na zakázce.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `zakazka_id` | FK → Zakazka (CASCADE) | ano |  |
| `kontakt_id` | FK → KontaktniOsoba (CASCADE) | ano |  |
| `role` | text (30); hodnoty: „Přinesl zařízení“, „Vyzvedl zařízení“, „Kontakt“, „Jiné“ | ne |  |

**Integritní omezení:**

- `zakazka_kontakt_unikatni` – UNIQUE (zakazka, kontakt, role)
- `zakazka_kontakt_role_platna` – CHECK `("role" IN ('Přinesl zařízení', 'Vyzvedl zařízení', 'Kontakt', 'Jiné') OR "role" = '')`

## TypUkonu

Tabulka `core_typukonu` – typ úkonu.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev` | text (150) | ano |  |
| `popis` | dlouhý text | ne |  |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |

## ProvedenyUkon

Tabulka `core_provedenyukon` – provedený úkon.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `zakazka_id` | FK → Zakazka (CASCADE) | ano |  |
| `typ_ukonu_id` | FK → TypUkonu (PROTECT) | ano |  |
| `cena` | desetinné (12,2) | ne |  |
| `sazba_dph` | desetinné (5,2) | ne |  |
| `poznamka` | dlouhý text | ne |  |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |

## Material

Tabulka `core_material` – materiál.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev` | text (200) | ano |  |
| `jednotka` | text (20) | ne |  (výchozí ks) |
| `posledni_cena` | desetinné (12,2) | ne |  |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |

## PouzityMaterial

Tabulka `core_pouzitymaterial` – použitý materiál.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `zakazka_id` | FK → Zakazka (CASCADE) | ano |  |
| `material_id` | FK → Material (PROTECT) | ano |  |
| `mnozstvi` | desetinné (12,3) | ano |  (výchozí 1) |
| `jednotkova_cena` | desetinné (12,2) | ne |  |
| `sazba_dph` | desetinné (5,2) | ne |  |
| `poznamka` | dlouhý text | ne |  |
| `datum_pridani` | datum a čas | ne |  |

## Fotografie

Tabulka `core_fotografie` – fotografie.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `zakazka_id` | FK → Zakazka (CASCADE) | ano |  |
| `soubor` | soubor (cesta) | ano |  |
| `popis` | dlouhý text | ne |  |
| `nahral_id` | FK → auth_user (PROTECT) | ne |  |
| `datum_nahrani` | datum a čas | ne |  |

## Priloha

Tabulka `core_priloha` – příloha.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev` | text (200) | ano |  |
| `soubor` | soubor (cesta) | ano |  |
| `typ_souboru` | text (10) | ne |  |
| `nahral_id` | FK → auth_user (PROTECT) | ne |  |
| `datum_nahrani` | datum a čas | ne |  |
| `poznamka` | dlouhý text | ne |  |

## Nabidka

Tabulka `core_nabidka` – nabídka.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `zakaznik_id` | FK → Zakaznik (PROTECT) | ano |  |
| `identifikacni_cislo` | text (50), index | ne |  |
| `sekundarni_cislo` | text (50), index | ne |  |
| `zakaznik_jmeno` | text (150) | ne |  |
| `zakaznik_firma` | text (255) | ne |  |
| `zakaznik_adresa` | text (200) | ne |  |
| `zakaznik_ico` | text (8) | ne |  |
| `zakaznik_dic` | text (14) | ne |  |
| `cena_bez_dph` | desetinné (12,2) | ne |  |
| `dph` | desetinné (12,2) | ne |  |
| `cena_s_dph` | desetinné (12,2) | ne |  |
| `poznamka` | dlouhý text | ne |  |
| `cislo_nabidky` | text (50), unikátní | ne | Prázdné = vygeneruje se automaticky |
| `datum_vystaveni` | datum a čas | ano |  |
| `vypracoval_id` | FK → auth_user (PROTECT) | ne |  |

## PolozkaNabidky

Tabulka `core_polozkanabidky` – položka nabídky.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `popis` | dlouhý text | ano |  |
| `mnozstvi` | desetinné (12,3) | ano |  (výchozí 1) |
| `jednotka` | text (20) | ne |  (výchozí ks) |
| `jednotkova_cena` | desetinné (12,2) | ne |  |
| `sazba_dph` | desetinné (5,2) | ne |  |
| `cena_bez_dph` | desetinné (12,2) | ne |  |
| `cena_s_dph` | desetinné (12,2) | ne |  |
| `nabidka_id` | FK → Nabidka (CASCADE) | ano |  |
| `zakazka_id` | FK → Zakazka (PROTECT) | ne |  |

## Objednavka

Tabulka `core_objednavka` – objednávka.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `cislo_objednavky` | text (50) | ano |  |
| `zakaznik_id` | FK → Zakaznik (PROTECT) | ano |  |
| `datum_objednavky` | datum | ne | datum vystavení – Datum uvedené na objednávce zákazníka. |
| `stredisko` | text (100) | ne | středisko |
| `predmet` | text (200) | ne | předmět objednávky – Stručně, o co se jedná. |
| `text` | dlouhý text | ne | text objednávky – Co zákazník objednává, opsané z objednávky. |
| `priloha_id` | FK → Priloha (PROTECT) | ne |  |
| `poznamka` | dlouhý text | ne |  |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |

## Faktura

Tabulka `core_faktura` – faktura.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `zakaznik_id` | FK → Zakaznik (PROTECT) | ano |  |
| `identifikacni_cislo` | text (50), index | ne |  |
| `sekundarni_cislo` | text (50), index | ne |  |
| `zakaznik_jmeno` | text (150) | ne |  |
| `zakaznik_firma` | text (255) | ne |  |
| `zakaznik_adresa` | text (200) | ne |  |
| `zakaznik_ico` | text (8) | ne |  |
| `zakaznik_dic` | text (14) | ne |  |
| `cena_bez_dph` | desetinné (12,2) | ne |  |
| `dph` | desetinné (12,2) | ne |  |
| `cena_s_dph` | desetinné (12,2) | ne |  |
| `poznamka` | dlouhý text | ne |  |
| `cislo_faktury` | text (50), unikátní | ne | Prázdné = vygeneruje se automaticky podle Nastavení → Dokumenty |
| `datum_vystaveni` | datum | ano |  |
| `datum_splatnosti` | datum | ne |  |
| `datum_zdanitelneho_plneni` | datum | ne |  |
| `vystavil_id` | FK → auth_user (PROTECT) | ne |  |

## PolozkaFaktury

Tabulka `core_polozkafaktury` – položka faktury.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `popis` | dlouhý text | ano |  |
| `mnozstvi` | desetinné (12,3) | ano |  (výchozí 1) |
| `jednotka` | text (20) | ne |  (výchozí ks) |
| `jednotkova_cena` | desetinné (12,2) | ne |  |
| `sazba_dph` | desetinné (5,2) | ne |  |
| `cena_bez_dph` | desetinné (12,2) | ne |  |
| `cena_s_dph` | desetinné (12,2) | ne |  |
| `faktura_id` | FK → Faktura (CASCADE) | ano |  |
| `zakazka_id` | FK → Zakazka (PROTECT) | ne |  |

## Platba

Tabulka `core_platba` – platba.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `faktura_id` | FK → Faktura (PROTECT) | ne |  |
| `zakazka_id` | FK → Zakazka (PROTECT) | ne |  |
| `stav` | text (30); hodnoty: „Čeká na zaplacení“, „Zaplaceno“ | ne |  |
| `zpusob` | text (30); hodnoty: „Hotově“, „Bankovní převod“, „Jiný“ | ne |  |
| `castka` | desetinné (12,2) | ne |  |
| `datum_zaplaceni` | datum a čas | ne |  |
| `poznamka` | dlouhý text | ne |  |

**Integritní omezení:**

- `platba_stav_platny` – CHECK `("stav" IN ('Čeká na zaplacení', 'Zaplaceno') OR "stav" = '')`
- `platba_zpusob_platny` – CHECK `("zpusob" IN ('Hotově', 'Bankovní převod', 'Jiný') OR "zpusob" = '')`

## Dodavatel

Tabulka `core_dodavatel` – dodavatel.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev` | text (255) | ano | název |
| `ico` | text (8) | ne | IČO |
| `dic` | text (14) | ne | DIČ |
| `adresa` | text (200) | ne |  |
| `telefon` | text (20) | ne |  |
| `email` | text (254) | ne |  |
| `cislo_uctu` | text (50) | ne | číslo účtu |
| `poznamka` | dlouhý text | ne |  |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |

## PrijataFaktura

Tabulka `core_prijatafaktura` – přijatá faktura.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `dodavatel_id` | FK → Dodavatel (PROTECT) | ano |  |
| `cislo_faktury` | text (50) | ano | číslo faktury dodavatele |
| `variabilni_symbol` | text (20) | ne | variabilní symbol |
| `datum_vystaveni` | datum | ne | datum vystavení |
| `datum_doruceni` | datum | ano | datum doručení |
| `datum_zdanitelneho_plneni` | datum | ne | DUZP |
| `datum_splatnosti` | datum | ne |  |
| `cena_bez_dph` | desetinné (12,2) | ne | částka bez DPH |
| `dph` | desetinné (12,2) | ne | DPH |
| `cena_s_dph` | desetinné (12,2) | ne | částka k úhradě |
| `mena` | text (3) | ne | měna (výchozí CZK) |
| `cislo_uctu` | text (50) | ne | účet pro platbu |
| `stav` | text (20); hodnoty: „Nezaplaceno“, „Zaplaceno“ | ano |  (výchozí Nezaplaceno) |
| `datum_zaplaceni` | datum | ne | datum zaplacení |
| `soubor` | soubor (cesta) | ne | soubor faktury |
| `zakazka_id` | FK → Zakazka (PROTECT) | ne | zakázka |
| `poznamka` | dlouhý text | ne |  |
| `vytvoril_id` | FK → auth_user (PROTECT) | ne |  |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |

**Integritní omezení:**

- `prijata_faktura_unikatni` – UNIQUE (dodavatel, cislo_faktury)
- `prijata_faktura_stav_platny` – CHECK `"stav" IN ('Nezaplaceno', 'Zaplaceno')`
- `prijata_faktura_datum_jen_u_zaplacene` – CHECK `("stav" = 'Zaplaceno' OR "datum_zaplaceni" IS NULL)`

## KalendarUdalost

Tabulka `core_kalendarudalost` – událost kalendáře.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev` | text (200) | ano |  |
| `popis` | dlouhý text | ne |  |
| `datum` | datum a čas | ano |  |
| `typ` | text (30); hodnoty: „Přijetí zakázky“, „Vydání zařízení“, „Fakturováno“, „Zaplaceno“, „Přijatá faktura“, „Splatnost faktury“, „Zaplaceno dodavateli“, „Vlastní událost“ | ne |  (výchozí Vlastní událost) |
| `automaticka` | logická hodnota | ano |  (výchozí ne) |
| `zakazka_id` | FK → Zakazka (PROTECT) | ne |  |
| `faktura_id` | FK → Faktura (PROTECT) | ne |  |
| `platba_id` | FK → Platba (PROTECT) | ne |  |
| `vytvoril_id` | FK → auth_user (PROTECT) | ne |  |
| `prijata_faktura_id` | FK → PrijataFaktura (CASCADE) | ne | přijatá faktura |

**Integritní omezení:**

- `kalendar_typ_platny` – CHECK `"typ" IN ('Přijetí zakázky', 'Vydání zařízení', 'Fakturováno', 'Zaplaceno', 'Přijatá faktura', 'Splatnost faktury', 'Zaplaceno dodavateli', 'Vlastní událost')`

## HistorieZmen

Tabulka `core_historiezmen` – změna.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `uzivatel_id` | FK → auth_user (PROTECT) | ne |  |
| `datum` | datum a čas | ne |  |
| `typ_objektu` | text (50) | ne |  |
| `id_objektu` | velké celé číslo | ne |  |
| `akce` | text (30) | ne |  |
| `pole` | text (100) | ne |  |
| `puvodni_hodnota` | dlouhý text | ne |  |
| `nova_hodnota` | dlouhý text | ne |  |
| `popis` | dlouhý text | ne |  |

## NastaveniFirmy

Tabulka `core_nastavenifirmy` – nastavení firmy.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev_firmy` | text (255) | ne |  |
| `adresa` | text (200) | ne |  |
| `ico` | text (8) | ne | IČO |
| `dic` | text (14) | ne | DIČ |
| `telefon` | text (20) | ne |  |
| `email` | text (254) | ne |  |
| `web` | text (200) | ne |  |
| `cislo_uctu` | text (50) | ne | číslo účtu |
| `logo` | soubor (cesta) | ne |  |
| `mena` | text (3); hodnoty: „CZK“, „EUR“ | ne |  (výchozí CZK) |
| `vychozi_dph` | desetinné (5,2) | ne |  |
| `datum_upravy` | datum a čas | ne |  |
| `vytvoril_id` | FK → auth_user (SET_NULL) | ne | vytvořil |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |
| `prvni_nastaveni_skryto` | logická hodnota | ano | první nastavení skryto (výchozí ne) |

**Integritní omezení:**

- `nastaveni_mena_platna` – CHECK `("mena" IN ('CZK', 'EUR') OR "mena" = '')`
- `nastaveni_dph_rozsah` – CHECK `("vychozi_dph" IS NULL OR ("vychozi_dph" >= '0' AND "vychozi_dph" <= '100'))`

## CiselnaRada

Tabulka `core_ciselnarada` – číselná řada.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `typ` | text (20), unikátní; hodnoty: „zakazka“, „nabidka“, „faktura“ | ano |  |
| `vzor` | text (50) | ano | vzor čísla – Ukázkové číslo tak, jak ho uživatel zadal, např. DMN260001. |
| `format` | text (100) | ano | Vzor rozložený na části, např. DMN{YY}{N4}. |
| `nulovat` | text (10); hodnoty: „rok“, „mesic“, „nikdy“ | ano | pořadí od 1 (výchozí rok) |
| `zacit_od` | celé kladné číslo | ano | další pořadové číslo (výchozí 1) |
| `zacit_od_obdobi` | text (10) | ne | Období (rok/měsíc), pro které platí „další pořadové číslo“. |
| `datum_upravy` | datum a čas | ne |  |

**Integritní omezení:**

- `ciselna_rada_typ_platny` – CHECK `"typ" IN ('zakazka', 'nabidka', 'faktura')`
- `ciselna_rada_nulovani_platne` – CHECK `"nulovat" IN ('rok', 'mesic', 'nikdy')`

## SazbaDPH

Tabulka `core_sazbadph` – sazba DPH.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `sazba` | desetinné (5,2) | ano |  |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |

**Integritní omezení:**

- `sazba_dph_rozsah` – CHECK `("sazba" >= '0' AND "sazba" <= '100')`

## SablonaDokumentu

Tabulka `core_sablonadokumentu` – šablona dokumentu.

| Sloupec | Datový typ | Povinné | Popis |
|:--|:--|:--|:--|
| `id` | celé číslo, PK | ano |  |
| `nazev` | text (150) | ano | název |
| `typ_dokumentu` | text (30), index | ano |  |
| `format` | text (20) | ano | formát (výchozí excel) |
| `soubor` | soubor (cesta) | ne | soubor šablony |
| `vestavena` | text (100) | ne | vestavěná šablona |
| `mapovani` | JSON | ne | mapování polí |
| `nahled` | soubor (cesta) | ne | miniatura |
| `popis` | dlouhý text | ne |  |
| `vychozi` | logická hodnota | ano | výchozí (výchozí ne) |
| `aktivni` | logická hodnota | ano | aktivní (výchozí ano) |
| `verze` | celé kladné číslo | ano |  (výchozí 1) |
| `datum_vytvoreni` | datum a čas | ne | datum vytvoření |
| `datum_upravy` | datum a čas | ne |  |

## Vazební tabulky (M:N)

| Tabulka | Propojuje |
|:--|:--|
| `core_zamestnanec_role` | Zamestnanec ↔ Role |
| `core_role_opravneni` | Role ↔ Opravneni |
| `core_zakazka_zarizeni` | Zakazka ↔ Zarizeni |
| `core_zakazka_zamestnanci` | Zakazka ↔ Zamestnanec |
| `core_provedenyukon_zamestnanci` | ProvedenyUkon ↔ Zamestnanec |
| `core_priloha_zakazky` | Priloha ↔ Zakazka |
| `core_nabidka_zakazky` | Nabidka ↔ Zakazka |
| `core_objednavka_zakazky` | Objednavka ↔ Zakazka |
| `core_faktura_zakazky` | Faktura ↔ Zakazka |
| `core_kalendarudalost_zamestnanci` | KalendarUdalost ↔ Zamestnanec |
