# 10. První nastavení po instalaci (pro administrátora)

Průvodce prvním spuštěním založí jen **účet administrátora** a **název firmy**. Aby aplikace ve firmě opravdu fungovala, musí administrátor
ještě pár věcí nastavit. První účet je vždy administrátorský a běžní zaměstnanci sekci **Nastavení** vůbec nevidí, takže tyto kroky
udělá jen administrátor (nebo zaměstnanec s rolí, která má oprávnění *Nastavení*).

Stejný seznam je přímo v aplikaci: **⚙ Nastavení → První nastavení aplikace**. U každého kroku je odkaz a aplikace sama pozná,
které povinné kroky už jsou hotové. Dokud nejsou, ukazuje se administrátorovi na pracovní ploše žluté upozornění
*Dokončete první nastavení aplikace* (jde skrýt tlačítkem **Skrýt** a v Nastavení zase zobrazit).

## Povinné kroky

### 1. Údaje o firmě – Nastavení → Firma → Údaje o firmě a logo
Doplňte **IČ, DIČ** (jen plátce DPH), **adresu**, **číslo účtu** a **logo**. Tyto údaje se tisknou na zakázkové listy, nabídky
a faktury; bez čísla účtu nemá faktura kam platit. Tady se nastavuje i **výchozí sazba DPH** (předvyplní se 21 %) a **měna**.

*Hotovo, když:* je vyplněné IČ, adresa a číslo účtu.

### 2. Role – Nastavení → Uživatelé a oprávnění → Role
Role určují, co kdo v aplikaci smí. Po instalaci jsou připravené čtyři:

| Role | Co smí |
|:--|:--|
| **Zaměstnanec** | jen základní přístup (zakázky, zápis práce, materiálu a fotek, nový zákazník); dostane ji každý nový zaměstnanec |
| **Technik** | navíc ruční změna stavu zakázky a úprava kalendáře |
| **Administrativa** | navíc úprava zákazníků, nabídky, objednávky, faktury a platby |
| **Administrátor** | všechno včetně mazání a Nastavení |

Zkontrolujte, jestli rozdělení odpovídá vaší firmě. Roli můžete upravit (zaškrtnout jiná oprávnění) nebo přidat vlastní,
např. *Skladník*. Popis všech oprávnění je v [README](../README.md#oprávnění).

*Hotovo, když:* některá role byla upravena nebo přidána, případně má některý zaměstnanec přidělenou jinou než základní roli.

### 3. Zaměstnanci – Nastavení → Uživatelé a oprávnění → Zaměstnanci
Každému, kdo bude s aplikací pracovat, založte kartu zaměstnance:

1. **+ Nový**, vyplňte jméno, příjmení a pracovní pozici.
2. V části **Role** zaškrtněte jeho role (chybí-li vhodná, tlačítko **+ Nová role** ji založí bez opuštění formuláře).
3. V části **Přihlašovací účet** zaškrtněte *Může se přihlásit do aplikace* a zadejte **přihlašovací jméno** a **heslo**.
   Volbu *Hlavní administrátor* zapínejte jen tomu, kdo má smět úplně všechno.
4. Přihlašovací jméno a heslo předejte zaměstnanci.

Zaměstnanec bez karty nebo bez role se sice přihlásí, ale uvidí jen hlášku, že nemá přístup. Kartu pro samotného administrátora
založí průvodce prvním spuštěním automaticky (s rolí Administrátor), aby se objevoval v zakázkách jako ten, kdo zařízení převzal nebo pracoval.

*Hotovo, když:* existuje aspoň jeden další aktivní zaměstnanec s přihlašovacím účtem.

### 4. Typy úkonů – Nastavení → Katalogy → Typy úkonů
Druhy prací, ze kterých technik vybírá při zápisu práce na zakázce, např. *Diagnostika*, *Výměna displeje*, *Čištění*,
*Instalace systému*. Seznam je po instalaci prázdný, a dokud v něm nic není, **nejde na zakázku zapsat práci**.

*Hotovo, když:* existuje aspoň jeden aktivní typ úkonu.

## Volitelné kroky

| Co | Kde | Proč |
|:--|:--|:--|
| **Číslování dokladů** | Nastavení → Dokumenty → Číslování dokladů | Jak vypadají čísla zakázkových listů, nabídek a faktur (např. `ZL260001`, `FV2026001`) a od kolika se začíná. Výchozí číslování funguje i bez úprav; změnit ho jde kdykoli, vystavené doklady si čísla nechají. |
| **Šablony dokumentů** | Nastavení → Dokumenty → Šablony dokumentů | Vzhled zakázkového listu, nabídky a faktury. Připravené jsou šablony *firemní*, *standardní* a *jednoduchá*; jde nahrát i vlastní Excel se značkami, viz [Šablony dokumentů](08-sablony-dokumentu.md). |
| **Stavy zakázek** | Nastavení → Katalogy → Stavy zakázek | Připravené jsou stavy Nová, Rozpracováno, Čeká na schválení, Čeká na díl, Opraveno, Připraveno k vyzvednutí, Vydáno a Zrušeno. Jde změnit pořadí, barvu nebo přidat vlastní. |
| **Sazby DPH** | Nastavení → DPH → Sazby DPH | Připravené jsou 21 %, 12 % a 0 %. Výchozí sazba se nastavuje v údajích o firmě. |
| **Materiály a dodavatelé** | Nastavení → Katalogy | Katalog materiálu a náhradních dílů s cenou usnadní zápis materiálu na zakázku. Jde doplňovat i průběžně přímo ze zakázky. |
| **Zálohování** | Nastavení → Systém → Zálohování | Pravidelná záloha databáze a souborů, viz [INSTALACE.md, část Zálohování](../INSTALACE.md#8-zálohování). |

## Shrnutí v jednom seznamu

- [ ] Nastavení → Firma: IČ, DIČ, adresa, číslo účtu, logo, výchozí DPH
- [ ] Nastavení → Role: zkontrolovat výchozí role, případně upravit nebo přidat vlastní
- [ ] Nastavení → Zaměstnanci: karta, role a přihlašovací účet pro každého, kdo bude aplikaci používat
- [ ] Nastavení → Typy úkonů: aspoň základní druhy prací
- [ ] *(volitelně)* Číslování dokladů, šablony dokumentů, stavy zakázek, materiály, zálohování

Technicky je seznam kroků i to, jak se pozná „hotovo“, v souboru `core/prvni_nastaveni.py`.
