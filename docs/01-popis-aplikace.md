# Popis aplikace

**BusinessManager** je informační systém pro evidenci servisních zakázek, který byl navržen přímo pro potřeby malé servisní firmy zabývající se opravami elektromotorů a dalších technických zařízení. Aplikace sdružuje na jednom místě vše, co se ve firmě dříve evidovalo odděleně v papírových formulářích, tabulkách aplikace Excel a složkách s fotografiemi: zákazníky, jejich zařízení, průběh opravy, provedené práce, použitý materiál a z nich vytvářené dokumenty, tedy zakázkové listy, cenové nabídky a faktury.

## Účel a hlavní myšlenka aplikace

Hlavní myšlenkou aplikace je, že *každý údaj se zadává pouze jednou* a všechny další výstupy z něj vznikají automaticky. Zákazník, zařízení nebo položka materiálu se do systému zapíší v okamžiku, kdy se poprvé objeví, a od té chvíle se na ně pouze odkazuje. Když je pak potřeba vystavit nabídku nebo fakturu, aplikace sama sestaví její položky z prací a materiálu evidovaných u zakázky, doplní údaje o zákazníkovi a o firmě a vloží je do firemní šablony dokumentu. Odpadá tak ruční přepisování údajů mezi jednotlivými dokumenty, které bylo podle analýzy firmy hlavním zdrojem chyb a časových ztrát.

Druhou důležitou myšlenkou je, že *vzhled dokumentů zůstává v rukou firmy*. Firma používala vlastní zakázkové listy, nabídky a faktury vytvořené v Excelu a nechtěla je nahrazovat jednotným vzhledem, který by nabídl hotový software. Aplikace proto pracuje s Excelovými šablonami, do kterých se na vybraná místa vkládají tzv. značky (například `{{dokument.cislo}}`), a při tvorbě dokumentu je nahradí skutečnými údaji z databáze. Systému šablon je věnována samostatná kapitola [Šablony dokumentů](08-sablony-dokumentu.md).

## Problém, který aplikace řeší

Před zavedením aplikace byla administrativa servisní zakázky ve firmě rozdělena mezi několik nezávislých nástrojů. Údaje o zákazníkovi a zařízení se zapisovaly do papírového zakázkového listu, provedené práce a materiál do samostatné tabulky, fotografie byly uloženy ve složkách na disku a nabídky i faktury vznikaly ručním vyplněním Excelových formulářů. To přinášelo několik konkrétních problémů:

- stejné údaje (jméno zákazníka, IČO, typ zařízení, ceny) se opakovaně přepisovaly, a vznikaly tak chyby a nesoulad mezi dokumenty,
- nebylo snadné zjistit, v jakém stavu je konkrétní zakázka a která zařízení jsou právě ve firmě,
- historie oprav konkrétního zařízení byla dohledatelná jen pracně, procházením starých listů a souborů,
- součty cen, DPH a číslování dokladů se počítaly ručně.

Aplikace tyto problémy řeší tím, že všechny údaje ukládá do jedné relační databáze, kde jsou navzájem propojené, a všechny výstupy z nich odvozuje.

## Pro koho je aplikace určena

Aplikace je určena pro zaměstnance jedné konkrétní servisní firmy, především pro administrativní pracovníky, kteří přijímají zařízení od zákazníků, vedou evidenci zakázek a vystavují nabídky a faktury, a dále pro techniky, kteří do zakázky doplňují provedené práce a použitý materiál. Jde o uživatele bez specializovaných znalostí informačních technologií, a proto je rozhraní celé v češtině, používá pojmy z běžné praxe firmy (zakázkový list, přijetí, vydání zařízení) a před začátkem práce stačí v krátkém průvodci prvním spuštěním založit účet administrátora a vyplnit název firmy.

Aplikace není univerzálním fakturačním ani účetním systémem. Účetnictví, mzdy nebo skladová evidence nejsou jejím předmětem; jejím úkolem je pokrýt životní cyklus servisní zakázky od přijetí zařízení po vystavení dokladu.

## Hlavní princip fungování

BusinessManager je *webová aplikace*, která běží na jednom počítači ve firmě (v roli serveru) a zaměstnanci s ní pracují prostřednictvím webového prohlížeče. Není tedy potřeba instalovat aplikaci na každý počítač zvlášť; stačí otevřít v prohlížeči adresu firemního počítače. Před zahájením práce se uživatel přihlásí svým účtem, bez přihlášení není dostupná žádná stránka ani žádný uložený soubor. Aplikace nepotřebuje připojení k internetu: všechny knihovny rozhraní jsou její součástí, takže stačí místní síť firmy.

Středobodem celé aplikace je **zakázka**. Ke každé zakázce patří právě jeden zákazník a k ní se postupně připojují zařízení, kontaktní osoby, fotografie, přílohy, provedené práce, použitý materiál, odpovědní zaměstnanci a nakonec i vytvořené nabídky, objednávky, faktury a platby. Zakázka prochází jednotlivými stavy (Nová, Rozpracováno, Čeká na díl, Opraveno, Připraveno k vyzvednutí, Vydáno a další), které odpovídají skutečnému průběhu opravy ve firmě.

Všechny dokumenty jsou z pohledu aplikace pouze *pohledem na uložená data*. Zakázkový list se při každém otevření sestaví znovu z aktuálního stavu zakázky. Nabídka a faktura se uloží jako samostatné záznamy se svými položkami, aby se jejich obsah po vystavení již neměnil, a jejich výsledný vzhled (PDF) se vytvoří vložením uložených údajů do zvolené šablony.

## Typický průběh práce s aplikací

Typický průběh servisní zakázky v aplikaci odpovídá pracovnímu postupu firmy a probíhá v těchto krocích:

1.  **Přijetí zařízení.** Pracovník otevře formulář „Nová zakázka“. Vyhledá zákazníka (nebo ho rovnou založí), vybere jeho zařízení (nebo založí nové), zadá kontaktní osobu, popis závady, datum přijetí, kdo zařízení převzal, a případně přiloží fotografie zařízení při převzetí. Po uložení aplikace přidělí zakázce číslo podle nastavené číselné řady (výchozí tvar `2026-048`), nastaví stav „Nová“ a do kalendáře zapíše událost přijetí.

2.  **Zakázkový list.** Ihned po přijetí lze vytisknout zakázkový list, který se vyplní údaji ze zakázky a slouží jako průvodní list zařízení ve firmě.

3.  **Diagnostika a oprava.** Technici postupně doplňují provedené práce (typ úkonu, cena, sazba DPH, kdo práci provedl) a použitý materiál (položka z katalogu materiálu, množství, cena). Ke zakázce lze kdykoli přidat další fotografie a přílohy, například technické listy nebo objednávku zákazníka. Stav zakázky se mění tlačítky („Zahájit práci“, „Čeká na díl“, „Dokončit opravu“ apod.); přidáním první práce se nová zakázka sama přepne do stavu „Rozpracováno“. Více prací nebo položek materiálu lze zapsat najednou.

4.  **Cenová nabídka.** Pokud zákazník požaduje nabídku, vytvoří se jedním kliknutím ze zakázky. Aplikace převezme práce a materiál jako položky nabídky, spočítá ceny s DPH a celkové součty, nabídce přidělí číslo s pořadím převzatým ze zakázky, a pokud je zakázka ještě ve stavu „Nová“, přepne ji do stavu „Čeká na schválení“. Z hotové nabídky lze tlačítkem „Pokračovat na fakturu“ rovnou přejít k vystavení faktury.

5.  **Dokončení a vydání.** Po dokončení opravy se zakázka označí jako opravená a připravená k vyzvednutí. Při předání zákazníkovi se stiskne „Vydat zákazníkovi“; aplikace uloží datum vydání, zapíše, kdo zařízení vydal, a vytvoří událost v kalendáři.

6.  **Faktura.** Faktura se vytvoří ze zakázky stejně jako nabídka. Aplikace jí přidělí číslo podle číselné řady faktur (výchozí tvar `001-27-10/2026`), nastaví datum splatnosti a datum uskutečnění zdanitelného plnění, převezme položky ze zakázky a založí k ní platbu ve stavu „Čeká na zaplacení“.

7.  **Výsledné dokumenty.** Zakázkový list, nabídku i fakturu lze zobrazit v náhledu, vytisknout nebo stáhnout jako soubor PDF. Dokument se vytvoří z výchozí firemní šablony, případně z jiné šablony, kterou uživatel v náhledu zvolí. Fakturu lze navíc stáhnout jako elektronickou fakturu ve formátu ISDOC pro import do účetního programu.

8.  **Platba.** Po úhradě stačí v detailu faktury stisknout **✓ Zaplaceno**; platba se označí jako zaplacená a do kalendáře se zapíše odpovídající událost. Platbu bez faktury (např. v hotovosti) lze zapsat přímo k zakázce.

Mimo průběh zakázky aplikace eviduje také **přijaté faktury** od dodavatelů. Fakturu ve formátu ISDOC stačí nahrát; aplikace převezme její údaje, přiřadí ji dodavateli a do kalendáře zapíše, kdy faktura přišla, kdy je splatná a zda už byla zaplacena.

Podrobný technický popis toho, jak data při tomto postupu procházejí jednotlivými částmi systému, obsahuje kapitola [Tok dat](06-tok-dat.md).

## Vztahy mezi částmi systému

Aplikaci lze z funkčního hlediska rozdělit na několik částí, které odpovídají položkám hlavní nabídky v levé liště rozhraní:

- **Pracovní plocha** – je výchozí obrazovka s vyhledáváním zakázek, naposledy otevřenými a otevřenými zakázkami a dnešními událostmi. Detail zakázky je pak pracovním prostorem, ve kterém se zobrazují všechny údaje a soubory zakázky včetně prohlížeče dokumentů.
- **Zakázky** – obsahují seznam zakázek, formulář nového přijetí a řízení stavu zakázky.
- **Zákazníci** – obsahují evidenci zákazníků a jejich kontaktních osob.
- **Zařízení** – obsahují přehled všech zařízení zákazníků s informací, zda je zařízení právě ve firmě, a historii jeho oprav.
- **Dokumenty** – sdružují nabídky, přijaté objednávky, vystavené a přijaté faktury, platby a šablony dokumentů.
- **Kalendář** – zobrazuje automaticky vznikající i vlastní (ručně zadané) události.
- **Nastavení** – obsahuje údaje o firmě, číslování dokladů, sazby DPH, katalogy (stavy zakázek, typy úkonů, materiál, dodavatelé), zaměstnance s jejich účty, role a oprávnění, šablony dokumentů, historii změn a zálohování. Nastavení vidí a mění jen administrátor, tedy uživatel s oprávněním Nastavení. Co smějí ostatní zaměstnanci (např. technik nebo administrativa), určují jejich role.

Všechny tyto části pracují nad společnou databází. Zákazník založený při přijetí zakázky je okamžitě vidět v evidenci zákazníků, zařízení přidané do zakázky se objeví v přehledu zařízení, cena materiálu z katalogu se nabídne při jeho přidání do zakázky, práce a materiál zakázky se stanou položkami nabídky i faktury a vystavení faktury se promítne do kalendáře. Systém šablon dokumentů je přitom na evidenci zcela nezávislý: šablona určuje pouze vzhled dokumentu a nikdy nemění uložená data. Tím je zajištěno, že změna vzhledu faktury nemůže ovlivnit její obsah, a naopak oprava údajů v evidenci se projeví ve všech dokumentech, které se z nich nově vytvoří.
