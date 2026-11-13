# Modul Odesílání e-mailů

Volitelný modul, který ukazuje, jak lze aplikaci rozšiřovat. Dokumenty, fotografie a přílohy zakázky se odešlou e-mailem přímo z aplikace, takže je není nutné stahovat a ručně přikládat v poštovním programu.

## Co modul potřebuje

- **E-mailovou schránku firmy** vyplněnou v **Nastavení → Moduly → E-mail** (server odchozí pošty, port, šifrování, přihlašovací jméno a heslo).
- **Připojení k internetu** ve chvíli odeslání. Je to jediná část aplikace, která internet potřebuje. Bez nastavení nebo bez internetu se nic neodešle a zbytek aplikace funguje dál offline.

## Nastavení (administrátor)

Nastavení → Moduly → E-mail:

| Pole | Příklad | Poznámka |
|:--|:--|:--|
| E-mail odesílatele | info@firma.cz | adresa, ze které zákazník e-mail dostane |
| Jméno odesílatele | Servis s.r.o. | prázdné = název firmy |
| Server, port, šifrování | smtp.seznam.cz, 465, SSL | odkazy *Seznam.cz*, *Gmail*, *Microsoft 365* údaje vyplní samy |
| Přihlašovací jméno, heslo | info@firma.cz | u Gmailu a Microsoftu 365 je potřeba **heslo aplikace** |
| Skrytá kopie odesílateli | zapnuto | odeslaný e-mail je pak i ve firemní schránce |
| Podpis | viz níže | připojí se na konec každého e-mailu |

Tlačítko **Uložit a odeslat zkušební e-mail** ověří, že nastavení funguje.

**Podpis** může obsahovat značky, které aplikace nahradí údaji odesílajícího zaměstnance a firmy: `{pracovnik}`, `{pozice}`, `{firma}`, `{adresa}`, `{telefon}`, `{email}`, `{web}`, `{ico}`. Telefon a e-mail se berou z karty zaměstnance, a když tam nejsou, z údajů firmy. Řádek, ke kterému údaj chybí (např. `Tel.: {telefon}`), se vynechá. Výchozí podpis:

```
S pozdravem

{pracovnik}
{pozice}
{firma}
{adresa}
Tel.: {telefon}
E-mail: {email}
{web}
```

## Odeslání (zaměstnanec)

1. Na zakázce klikne na **✉ Odeslat e-mailem** (nebo v náhledu dokumentu, kde je dokument už předem zaškrtnutý).
2. Zakázku lze ve formuláři změnit. Příjemce se předvyplní e-mailem zákazníka, další kontakty zakázky se dají přidat kliknutím.
3. Napíše předmět a text, pod textem vidí, jaký podpis se připojí.
4. Zaškrtne, co chce poslat: zakázkový list, nabídky a faktury jako PDF (podle výchozí šablony), faktury i ve formátu ISDOC, přílohy objednávek, fotografie a přílohy zakázky. Formulář ukazuje velikost souborů a upozorní, když je e-mail větší než 18 MB.
5. Klikne na **Odeslat**. Odeslaný e-mail se zapíše do historie zakázky a do seznamu Nastavení → Moduly → Odeslané e-maily.

Doklady (nabídky, faktury) se nabídnou jen zaměstnanci, který s nimi smí pracovat, stejně jako na pracovní ploše. Odpověď zákazníka přijde přímo odesílajícímu zaměstnanci (hlavička Reply-To), pokud má v kartě vyplněný e-mail.

## Chyby

Technické chyby serveru se uživateli ukážou srozumitelně, např.:

- *Nepodařilo se spojit s poštovním serverem. Je počítač s aplikací připojený k internetu?*
- *Server odmítl přihlášení. Zkontrolujte jméno a heslo…*
- *Server odmítl adresu příjemce…*

Spojení se serverem čeká nejvýše 20 sekund.

## Na pozadí

| Část | Soubor |
|:--|:--|
| Logika modulu (podpis, výběr souborů, odeslání, chyby, stránky) | `core/email_modul.py` |
| Šablony stránek | `core/templates/core/email_nastaveni.html`, `email_odeslat.html` |
| Tabulky | `NastaveniEmailu` (jediný záznam), `OdeslanyEmail` (migrace `0021_modul_email`) |
| Testy | `ModulEmailTest` v `core/tests.py` |

E-mail se odesílá vestavěným modulem Django (`django.core.mail`, protokol SMTP), žádná další knihovna není potřeba. PDF dokumentů vytváří stejný převod jako tlačítko *Stáhnout PDF*.

Heslo ke schránce je uložené v databázi aplikace, která běží jen v místní síti firmy. Tabulka nastavení e-mailu proto nemá obecný seznam ani detail, heslo se ve formuláři nezobrazuje a stránku smí otevřít jen uživatel s oprávněním Nastavení.
