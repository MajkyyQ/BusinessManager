# 6. HELIOS (Asseco Solutions)

*Údaje ověřeny 2. 11. 2026. Oficiální web helios.eu byl při ověřování částečně nedostupný a výrobce nezveřejňuje ceník ani podrobný popis funkcí, proto část údajů pochází od partnerů a srovnávacích článků; takové údaje jsou označeny.*

| Kritérium | Zjištění |
|---|---|
| Název | Produktová řada HELIOS: **Red** (živnostníci), **Easy** (malé firmy), **iNuvio** (malé a střední firmy, nástupce HELIOS Orange), **Nephrite** (velké firmy), Fenix (veřejná správa) [1][2] |
| Společnost | Asseco Solutions, a.s., Praha (součást evropské skupiny Asseco); 30+ let, 15 000+ zákazníků, 100+ partnerů [3] |
| Typ aplikace | Desktopová aplikace pro Windows. iNuvio/Easy: klient–server nad Microsoft SQL Server, přístup v síti LAN/WAN nebo přes vzdálenou plochu (RDP); webového klienta technické požadavky neuvádějí [4]. Red: souborová aplikace nad DBF [5] |
| Hostování | Primárně vlastní server / lokální PC (i jednopočítačová „monoinstalace“) [4]; cloud jako samostatná služba ERPORT nebo u partnerů (např. AppOn.cloud, hosting od 1 150 Kč/měs. bez DPH, bez licence) [1][6] |
| Licence | Proprietární |
| Cena | **Nezveřejněna**, individuální nabídka po analýze podle modulů a počtu uživatelů [1][2][7]; implementace trvá měsíce [1] |
| Free trial | Ne, jen předváděcí demo / testovací prostředí na vyžádání [1] |

## Pokrytí modulů BusinessManageru (HELIOS iNuvio)

| Modul | HELIOS iNuvio | Poznámka |
|---|---|---|
| Zákazníci | ✓ | Organizace a kontakty, CRM (obchodní příležitosti, mobilní obchodník), napojení na ARES [1][7] |
| Zařízení + historie | ◐ | Výrobce uvádí modul řízení projektů a **servisu**; detail evidence zařízení zákazníka veřejně popsán není (ověřit na demu) [1] |
| Zakázky | ◐ | Řízení projektů a servisu, zakázky v rámci výroby/obchodu; podrobnosti nezveřejněny [1] |
| Práce | ◐ | Docházka a plánování v modulu Lidské zdroje; evidence servisních úkonů neověřena [1] |
| Materiál | ✓ | Sklady od příjmu po expedici [1] |
| Dokumenty | ✓ | Fakturace, objednávky, nabídky v modulu Obchod; DMS jako samostatný produkt [1][8] |
| PDF / šablony | ◐ | Tiskové sestavy systému; úprava šablon zpravidla přes partnera (neověřeno) |
| Platby | ✓ | Homebanking, import výpisů, párování [7] |
| Kalendář | ? | Veřejně nepopsáno |
| Uživatelé / role | ✓ | Centrální správa a administrace uživatelů [8] |
| Historie / audit | ? | Veřejně nepopsáno |
| Import / export | ◐ | Otevřené API, ARES, import bankovních výpisů, export do MS Office [4][7]; ISDOC je u českých ERP standardem, u HELIOS veřejně nedoloženo |

✓ = ano · ◐ = částečně / neověřeno v detailu · ? = výrobce veřejně neuvádí

## UI
Klasická desktopová aplikace pro Windows s přehledy (gridy), formuláři a stromovým menu modulů; iNuvio přináší podle výrobce modernější rozhraní, přizpůsobitelné dashboardy a fulltextové vyhledávání oproti HELIOS Orange [1][7]. Bez trialu nelze UI vlastnoručně ověřit, v práci je proto vhodné vycházet z oficiálních screenshotů / videí výrobce a uvést to.

## Výhody
- Robustní a v ČR rozšířené ERP s kompletní českou legislativou, mzdami, výrobou a dopravou.
- Škálovatelná řada od živnostníka (Red) po velkou firmu (Nephrite).
- Možnost provozu zcela na vlastním serveru, data pod kontrolou firmy.
- Síť implementačních partnerů a podpora.

## Nevýhody vůči potřebám BusinessManageru
- Nezveřejněná cena, žádný trial, implementace v řádu měsíců – pro malou servisní firmu příliš těžkopádné.
- Desktop pouze pro Windows a MS SQL; vzdálený přístup přes RDP nebo hostovaný cloud, ne nativní web.
- Servisní funkce existují, ale nejsou veřejně popsané a jejich nastavení vyžaduje partnera.
- Vzhled dokumentů a UI upravuje typicky partner, ne sám uživatel.

## Vhodnost pro malé firmy
Pro malou firmu nevhodné až podmíněně vhodné (HELIOS Easy/Red): vyžaduje vlastní Windows server nebo placený hosting, licence a implementaci na míru a neveřejná cena brání rychlému rozhodnutí. Hodí se pro střední a větší firmy s komplexními procesy (výroba, sklady, mzdy).

## Zdroje
1. Asseco Solutions: Helios Inuvio for medium company. https://www.helios.eu/en/inuvio-for-medium-company [cit. 2026-11-02]
2. AutoERP: ERP systém 2026 – průvodce a srovnání 10 systémů v ČR s cenami (aktualizováno 10/2026). https://autoerp.cz/erp-system [cit. 2026-11-02]
3. Asseco Solutions: produktový list HELIOS Fenix (údaje o společnosti). https://www.helios.eu/files/pl-helios-fenix.pdf [cit. 2026-11-02]
4. Asseco Solutions: Technical requirements – Helios Easy / Inuvio. https://www.helios.eu/en/technical-requirements-helios-easy [cit. 2026-11-02]
5. Asseco Solutions: Technical requirements – HELIOS Red. https://www.helios.eu/en/technical-requirements-helios-red [cit. 2026-11-02]
6. AppOn.cloud: Helios iNuvio v cloudu. https://www.appon.cloud/cs/application/helios-inuvio-v-cloudu/ [cit. 2026-11-02]
7. Ucetnictvi.cz: HELIOS iNuvio – účetní software. https://ucetnictvi.cz/software/helios-inuvio [cit. 2026-11-02]
8. IT Point: ERP HELIOS iNuvio. https://www.itpoint.cz/asseco-solutions/?i=erp-helios-inuvio-14447 [cit. 2026-11-02]

## Co udělat místo trialu
1. Vyžádat si online demo přes kontaktní formulář na helios.eu (zmínit, že jde o bakalářskou práci, firmy to často vyjdou vstříc).
2. Jinak použít oficiální screenshoty / videa výrobce (YouTube kanál, produktové listy PDF) a v popisku obrázku uvést „Zdroj: Asseco Solutions, a.s.“ s URL.
3. Fotit: hlavní okno a menu modulů, přehled dokladů (grid), formulář faktury a tiskový náhled, servisní modul.
