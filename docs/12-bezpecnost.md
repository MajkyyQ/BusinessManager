# 12. Bezpečnost

Aplikace pracuje s osobními a obchodními údaji zákazníků a před zveřejněním jako open source prošla bezpečnostním auditem celého zdrojového kódu (listopad 2026). Audit našel šest chyb, všechny jsou opravené a každou hlídá automatický test. Tato kapitola popisuje, co se zkoumalo, co se našlo, jak se to opravilo a co zůstává jako doporučení. Základní bezpečnostní opatření aplikace popisuje kapitola [Architektura](04-architektura.md#zabezpečení).

## Jak audit probíhal

Audit prošel zdrojový kód aplikace (repozitář BusinessManager) i modulu Odesílání e-mailů (repozitář BusinessManager-moduly). Postupoval podle metodiky *security-audit*: za chybu se považuje jen to, co porušuje skutečnou hranici důvěry. U každého nálezu je tedy jasné, **kdo** může chybu zneužít (např. zaměstnanec se základní rolí), **co** tím získá (např. práva administrátora) a **která kontrola** selhala. Obecná doporučení „best practice“ bez konkrétního dopadu jsou oddělená v části [Doporučení](#doporučení-do-budoucna).

Hranice důvěry, které audit zkoumal:

| Kdo | Co nesmí |
|:--|:--|
| nepřihlášený návštěvník v síti | vidět jakoukoli stránku nebo soubor, kromě přihlášení a průvodce prvním spuštěním |
| zaměstnanec se základní rolí | vidět doklady a ceny bez oprávnění, měnit nastavení, mazat cizí záznamy, získat vyšší oprávnění |
| technik, administrativa | překročit oprávnění své role |
| uživatel s oprávněním Nastavení | převzít účet hlavního administrátora |
| zákazník, dodavatel | poškodit aplikaci souborem, který firma nahraje (fotka, objednávka, faktura ISDOC) |

Oblasti, které audit prošel:

- **Přihlášení a oprávnění:** middleware `PravaMiddleware`, obecné pohledy (`lst`, `detail`, `edit`, `delete`), stránky modulů, soubory v `/media/`, průvodce prvním spuštěním, správa účtů zaměstnanců.
- **Vkládání kódu:** XSS v šablonách, v JavaScriptu (`innerHTML`) a v nahraných souborech; SQL injection; vkládání šablon (HTML šablony dokumentů); vkládání hlaviček do e-mailu.
- **Soubory:** nahrávání (přípony, skutečný typ), odesílání prohlížeči, cesty `../`, import ISDOC (XML External Entities, archivy ZIP), převod přes LibreOffice.
- **Přesměrování a CSRF:** parametr `next`, odkazy Zpět, ochrana formulářů.
- **Modul e-mail:** uložení hesla ke schránce, kdo smí odesílat, výběr příloh, adresy příjemců.
- **Konfigurace a nasazení:** `settings.py`, `.env`, Docker, instalační skript.

Nálezy byly ověřené čtením kódu, opravy pak automatickými testy (tabulka níže).

## Nálezy a opravy

| # | Závažnost | Nález | Kdo mohl chybu zneužít | Oprava | Test |
|:--|:--|:--|:--|:--|:--|
| 1 | vysoká | Nahraný soubor `.html` nebo `.svg` (příloha, „fotka“, přijatá faktura) se otevřel jako stránka aplikace a skript v něm běžel pod přihlášením toho, kdo ho otevřel. Takto šlo útočníkovi zaškrtnout „Hlavní administrátor“. | zaměstnanec se základní rolí | povolené přípony, ověření fotek knihovnou Pillow, bezpečné hlavičky při odeslání souboru | `BezpecnostTest`: `test_priloha_html_ani_svg_nejde_nahrat`, `test_podvrzena_fotka_nejde_nahrat`, `test_prijata_faktura_jen_povolene_pripony`, `test_soubory_se_posilaji_s_bezpecnymi_hlavickami` |
| 2 | střední | Kdokoli smazal cizí fotky a přílohy u zakázky, přestože popis oprávnění sliboval jen vlastní. | zaměstnanec se základní rolí | fotku a přílohu smaže jen ten, kdo ji nahrál, nebo uživatel s oprávněním Mazání | `test_cizi_fotku_nesmaze`, `test_spravce_s_opravnenim_mazani_smaze_cizi_prilohu` |
| 3 | nízká | Parametr `?next=/\cizi.web` po uložení formuláře přesměroval na cizí web (např. podvrženou přihlašovací stránku). | kdokoli, kdo pošle odkaz | kontrola funkcí `url_has_allowed_host_and_scheme` z Django | `test_next_nepresmeruje_na_cizi_web` |
| 4 | nízká | Soubory přijatých faktur a šablon v `/media/` stáhl i zaměstnanec bez oprávnění Faktury nebo Nastavení, pokud znal cestu. | zaměstnanec se základní rolí | oprávnění podle složky (`MEDIA_PRAVA`), ochrana proti obejití přes `../` | `test_soubor_prijate_faktury_jen_s_opravnenim_faktury` |
| 5 | nízká | Modul e-mail: kdokoli poslal z firemní schránky libovolný text na libovolnou adresu s podpisem firmy. | zaměstnanec se základní rolí | nové oprávnění „Odesílání e-mailů“ | `test_odesilat_smi_jen_role_s_opravnenim` (modul) |
| 6 | nízká | Uživatel s oprávněním Nastavení mohl změnit heslo hlavního administrátora (účtu z průvodce) nebo jeho účet vypnout. | role s oprávněním Nastavení | účet hlavního administrátora mění jen hlavní administrátor | `test_ucet_hlavniho_administratora_nezmeni_spravce_s_nastavenim` |

### 1. Skript v nahraném souboru

Nahrané soubory leží ve složce `media` a prohlížeč je otevírá ze stejné adresy jako aplikaci. Soubor typu HTML nebo SVG by tedy prohlížeč spustil jako součást aplikace, se všemi právy přihlášeného uživatele. Chyba měla tři příčiny: příloha přijala jakýkoli soubor, fotky se kontrolovaly jen podle typu, který hlásí prohlížeč (dá se podvrhnout), a soubory odesílala funkce `django.views.static.serve` s typem podle přípony.

Oprava (soubor `core/soubory.py`) má dvě nezávislé pojistky:

1. **Při nahrání** se povolí jen známé přípony: u příloh dokumenty, tabulky, obrázky a archivy (`PRIPONY_PRILOH`), u přijatých faktur PDF, ISDOC a obrázky. Import ISDOC přijme jen `.isdoc`, `.isdocx` a `.xml`. Fotku ověří knihovna Pillow (`forms.ImageField`), takže projde jen skutečný obrázek. Platí to pro formulář fotek i pro fotky přidané při založení zakázky.
2. **Při odeslání** prochází každý soubor pohledem `media`, který přidá hlavičku `X-Content-Type-Options: nosniff`. Obrázky a PDF se dál zobrazují v náhledu na pracovní ploše. Všechny ostatní soubory se jen stáhnou (`Content-Disposition: attachment`) a mají navíc `Content-Security-Policy: sandbox`, takže skript se nespustí ani v souboru, který se do složky dostal dřív nebo jinou cestou.

### 2. Mazání cizích souborů

Funkce `smi_stranku` v `core/prava.py` teď u fotek a příloh vyžaduje oprávnění Mazání a deaktivace, s výjimkou vlastních souborů (pole `nahral`). Tlačítko Smazat na pracovní ploše se zobrazí jen tomu, kdo smí soubor smazat. Řádek práce a materiálu vlastníka v databázi nemá, smazat ho tedy smí dál každý se základním přístupem. Popis oprávnění Mazání je upravený tak, aby to říkal přesně.

### 3. Přesměrování na cizí web

Funkce `safe_next` v `core/views.py` dřív kontrolovala jen to, že adresa začíná jedním lomítkem. Prohlížeče ale adresu `/\cizi.web` čtou jako `//cizi.web`, tedy jiný server. Nově adresu kontroluje funkce `url_has_allowed_host_and_scheme` z Django, kterou Django používá i u přihlášení.

### 4. Soubory podle oprávnění

`PravaMiddleware` u souborů v `/media/` kontroluje oprávnění podle složky (`MEDIA_PRAVA` v `core/prava.py`): `prijate_faktury/` vyžaduje oprávnění Faktury, `sablony/` oprávnění Nastavení, ostatní složky (fotky, přílohy, logo) základní přístup. Cesta se před kontrolou normalizuje, takže kontrolu nejde obejít adresou typu `/media/fotky/../prijate_faktury/…`.

### 5. Oprávnění k odesílání e-mailů

Volitelné moduly mohou nově přidat vlastní oprávnění (pole `opravneni` třídy `Modul`, viz [Volitelné moduly](11-moduly.md)). Modul e-mail přidává oprávnění **Odesílání e-mailů** (`email.odesilat`). Při instalaci modulu ho dostanou výchozí role Technik a Administrativa. Role Zaměstnanec ho nemá, administrátor ho může přidat nebo odebrat v Nastavení → Role. Bez oprávnění se tlačítko Odeslat e-mailem nezobrazí a stránka odesílání se neotevře.

### 6. Účet hlavního administrátora

`ZamestnanecForm` odmítne změnu přihlašovacího účtu s příznakem *Superuser* (zapnutí, jméno, heslo, administrátor), pokud ji neprovádí jiný superuser. Ostatní údaje karty (telefon, pozice) může upravit kdokoli s oprávněním Nastavení.

## Co audit ověřil jako bezpečné

- Oprávnění kontroluje server u každého požadavku (`PravaMiddleware`), ručně zadaná adresa skrytá tlačítka neobejde. Platí to i pro stránky modulů.
- Formuláře jsou chráněné proti CSRF. Šablony automaticky escapují vstupy a JavaScript vkládá texty přes funkci `esc()` nebo `json_script`.
- Databáze se používá jen přes ORM, žádný dotaz se neskládá ručně (ověřují testy `SQLInjectionTest`).
- Import ISDOC má vypnuté načítání externích entit a síťový přístup parseru XML (ochrana proti XXE).
- HTML šablony dokumentů (jazyk šablon Django) smí nahrávat jen uživatel s oprávněním Nastavení.
- Modul e-mail: heslo ke schránce se do formuláře nevypisuje, přílohy lze vybrat jen ze zvolené zakázky a podle oprávnění, adresy se ověřují a vložení hlaviček do e-mailu Django zablokuje.
- Instalační skript vytváří náhodný `SECRET_KEY` i heslo databáze a nastaví `DEBUG=0`. Port databáze se mimo Docker nepublikuje.

## Doporučení do budoucna

Tyto body nejsou zranitelnosti, ale zvyšují bezpečnost provozu:

- **HTTPS:** aplikace běží na `http://…:8080`, hesla jdou po firemní síti nešifrovaně. Pro provoz mimo malou uzavřenou síť je vhodné předřadit HTTPS (např. Caddy) a nastavit `SESSION_COOKIE_SECURE` a `CSRF_COOKIE_SECURE`.
- **Omezení pokusů o přihlášení:** např. knihovna `django-axes`.
- **Výchozí hodnoty v `settings.py`:** bez souboru `.env` platí `DEBUG=1` a pevný `SECRET_KEY`. Instalační skript to řeší, ruční spuštění ne; pro provoz vždy použít `.env`.
- **Heslo ke schránce SMTP** je v databázi uložené čitelně, takže je i v zálohách. Zálohy proto patří na bezpečné místo. Volba šifrování „Bez šifrování“ je jen pro místní poštovní server.
- **Průvodce prvním spuštěním:** dokud není založený první účet, stane se administrátorem ten, kdo stránku otevře jako první. Průvodce je proto potřeba dokončit hned po instalaci.
- **Velikost nahrávaných souborů** není omezená.
- **Závislosti:** knihovny v `requirements.txt` kromě Django a openpyxl nemají pevné verze. Před vydáním nové verze je vhodné zkontrolovat známé zranitelnosti (např. `pip-audit`).

## Nahlášení bezpečnostní chyby

Bezpečnostní chybu prosím nehlaste veřejným issue. Použijte na GitHubu **Security → Report a vulnerability** (soukromé hlášení), viz [SECURITY.md](../SECURITY.md).
