# 12. Bezpečnost

Aplikace pracuje s osobními a obchodními údaji zákazníků a před zveřejněním jako open source prošla bezpečnostním auditem celého zdrojového kódu (listopad 2026). Audit našel šest chyb, všechny jsou opravené a každou hlídá automatický test. Tato kapitola popisuje, co se zkoumalo, co se našlo, jak se to opravilo a co zůstává jako doporučení. Základní bezpečnostní opatření aplikace popisuje kapitola [Architektura](04-architektura.md#zabezpečení).

## Pro jaký provoz je aplikace navržená

BusinessManager je určený pro malou firmu: aplikace běží na jednom firemním PC a uživatelé se k ní připojují z prohlížeče na tomto PC nebo z jiných počítačů ve stejné firemní síti. Jejím cílem je nahradit a sjednotit evidenci zakázek a dokladů v jedné databázi, ne chránit data před cíleným útokem. Z toho vychází, proti čemu aplikace chrání a proti čemu ne:

| Kdo | Co aplikace zajišťuje |
|:--|:--|
| zaměstnanec s vlastním účtem | vidí a mění jen to, co mu dovolí oprávnění jeho role; nezíská vyšší práva (opravy z auditu níže) |
| někdo v síti bez účtu | uvidí jen přihlašovací stránku; databáze se do sítě nepublikuje, takže se k ní z jiného PC nepřipojí |
| kdo získá zálohu nebo kopii databáze | nepřečte hesla k účtům (uložená jen jako otisk) ani heslo ke schránce modulu e-mail (zašifrované klíčem z `.env`) |

**Co aplikace neřeší:** kdo má přístup přímo k serverovému PC (fyzicky nebo jako jeho správce), má přístup i k databázi, souborům a `.env` a žádné zabezpečení uvnitř aplikace ho nezastaví. Ochrana serverového PC (heslo k Windows, šifrování disku, aktualizace) patří k provozu firmy, ne k aplikaci. Aplikace také není určená k vystavení do internetu. Přístup zvenku, např. z telefonu na výjezdu, je vhodné řešit soukromou sítí (VPN, např. Tailscale), ne přesměrováním portu v routeru.

Proto se zpevnění po auditu omezilo na základní opatření (viz [Zpevnění po auditu](#zpevnění-po-auditu)). Složitější ochrany (omezení pokusů o přihlášení, HTTPS, pevné verze knihoven) jsou vedené jako [doporučení](#doporučení-do-budoucna) pro případ, že by se aplikace používala v otevřenější síti.

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

Opravy se řídily zásadou nejmenší účinné změny v místě, kde aplikace o přístupu rozhoduje. U nahraných souborů jsou dvě nezávislé pojistky (kontrola při nahrání a bezpečné hlavičky při odeslání), takže druhá chrání i soubory, které se do aplikace dostaly před opravou. Aby mohl modul e-mail přidat vlastní oprávnění, rozšířil se systém modulů o oprávnění, která administrátor přiřazuje rolím stejně jako oprávnění základní aplikace.

### Jak testy opravy ověřují

Každou opravu hlídá automatický test, který by chybu odhalil, kdyby se v kódu znovu objevila. Testy pro nálezy 1 až 4 a 6 jsou ve třídě `BezpecnostTest` v `core/tests.py`, test oprávnění k odesílání e-mailů je v testech modulu. Testy zkoušejí skutečné útoky:

- nahrání souboru `.html` a `.svg` jako přílohy a souboru HTML vydávajícího se za obrázek PNG,
- otevření staršího souboru HTML, který už v úložišti je,
- smazání cizí fotky,
- přesměrování na adresy `/\cizi.web` a `//cizi.web`,
- stažení přijaté faktury technikem, i přes cestu `fotky/../`,
- změnu hesla hlavního administrátora uživatelem s oprávněním Nastavení,
- odeslání e-mailu zaměstnancem bez oprávnění.

Ověřují také, že povolené činnosti fungují dál: nahrání PDF a skutečné fotky, smazání vlastní fotky, přesměrování v rámci aplikace a úprava ostatních údajů karty administrátora.

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

## Zpevnění po auditu

Doporučení z auditu se postupně zapracovávají:

| Doporučení | Stav |
|:--|:--|
| Bezpečné výchozí nastavení | hotovo: `DEBUG` je bez `.env` vypnutý; chybí-li `SECRET_KEY`, vygeneruje se náhodný klíč do souboru `.secret_key` (dřív platil pevný klíč známý z repozitáře); `.env` se načte i při spuštění bez Dockeru; volba `HTTPS=1` pro šifrované cookies (test `BezpecneNastaveniTest`) |
| Limit velikosti nahrávaných souborů | hotovo: jeden soubor nejvýš 50 MB, jedno nahrání (např. víc fotek najednou) nejvýš 500 MB; obojí jde změnit v `.env` (`MAX_VELIKOST_SOUBORU_MB`, `MAX_VELIKOST_NAHRAVANI_MB`). Příliš velké nahrání se odmítne dřív, než se začne ukládat na disk (test `LimitVelikostiSouboruTest`) |
| Heslo ke schránce SMTP šifrovaně | hotovo v modulu e-mail 1.2: heslo se ukládá zašifrované (Fernet, knihovna `cryptography`) klíčem odvozeným z `SECRET_KEY`, takže z databáze ani ze zálohy nejde přečíst. Při jiném `SECRET_KEY` (obnova bez původního `.env`) aplikace požádá o nové zadání hesla (test modulu `test_heslo_je_v_databazi_zasifrovane`) |
| Záloha mimo serverové PC | hotovo: `zaloha.bat` ukládá i `.env`, na PC nechá posledních 7 záloh a při nastavení `ZALOHA_KOPIE` v `.env` zkopíruje poslední zálohu na jiný disk nebo PC (drží tam poslední 2) |

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

- **HTTPS:** aplikace běží na `http://…:8080`, hesla jdou po firemní síti nešifrovaně. Pro provoz mimo malou uzavřenou síť je vhodné předřadit HTTPS (např. Caddy) a v `.env` nastavit `HTTPS=1`: cookies přihlášení se pak posílají jen šifrovaně.
- **Omezení pokusů o přihlášení:** např. knihovna `django-axes`. V malé firemní síti není nutné, smysl má při přístupu z otevřenější sítě.
- **Přístup zvenku (telefon na výjezdu):** přes soukromou síť (VPN, např. Tailscale) mezi serverovým PC a telefonem. Aplikace pak dál není vidět z internetu; serverové PC ale musí být zapnuté.
- **Průvodce prvním spuštěním:** dokud není založený první účet, stane se administrátorem ten, kdo stránku otevře jako první. Průvodce je proto potřeba dokončit hned po instalaci.
- **Závislosti:** knihovny v `requirements.txt` kromě Django a openpyxl nemají pevné verze. Před vydáním nové verze je vhodné zkontrolovat známé zranitelnosti (např. `pip-audit`).

## Nahlášení bezpečnostní chyby

Bezpečnostní chybu prosím nehlaste veřejným issue. Použijte na GitHubu **Security → Report a vulnerability** (soukromé hlášení), viz [SECURITY.md](../SECURITY.md).
