# Čistá instalace na firemní PC (Windows)

Návod nasadí BusinessManager na jeden firemní počítač s Windows 10/11. Ten počítač bude „server“:
aplikace na něm běží v Dockeru a ostatní počítače ve firmě se k ní připojí přes prohlížeč.
Instalace je čistá: databáze je prázdná, bez testovacích dat. Účet administrátora a údaje o firmě
založíte v průvodci při prvním otevření.

Celé to zabere asi 30–60 minut, nejdéle trvá první sestavení aplikace (stahuje se LibreOffice).

## 0. Co je potřeba

- Windows 10 (22H2) nebo 11, 64bitové, alespoň 8 GB RAM a 10 GB volného místa.
- Účet s **administrátorskými právy** na tomto PC (kvůli instalaci Dockeru a otevření portu ve firewallu).
- Internet během instalace. Za provozu už internet potřeba není.
- Počítač by měl být zapnutý vždy, když s aplikací někdo pracuje.

Docker Desktop je zdarma pro firmy do 250 zaměstnanců a do 10 mil. USD obratu.

## 1a. Připravte Windows: virtualizace a WSL

Docker Desktop potřebuje dvě věci, které na většině PC nejsou zapnuté. Stačí to udělat jednou.

**a) Zkontrolujte virtualizaci.** Otevřete Správce úloh (Ctrl+Shift+Esc) → **Výkon** → **CPU**.
Vpravo dole musí být **Virtualizace: Povoleno**.

Když je tam *Zakázáno*, zapněte ji v BIOSu:
1. Restartujte PC a hned po zapnutí opakovaně mačkejte klávesu pro BIOS. Bývá to **F2**, **Del**, **F10** nebo **F1**,
   u notebooků Lenovo často **F1**/**F2**, u HP **Esc** a pak **F10**. Klávesa se většinou krátce ukáže dole na obrazovce.
   Jiná cesta: Nastavení Windows → Systém → Obnovení → **Rozšířené spuštění** → Řešení potíží → Upřesnit možnosti →
   **Nastavení firmwaru UEFI**.
2. Najděte položku **Intel Virtualization Technology** (VT-x), u AMD **SVM Mode** nebo **AMD-V**.
   Bývá v sekci *Advanced*, *CPU Configuration* nebo *Security*.
3. Nastavte ji na **Enabled**, uložte (obvykle **F10**) a nechte PC nastartovat.

Na firemním PC může být BIOS zamčený heslem. Pak je potřeba požádat správce IT.

**b) Nainstalujte WSL** (část Windows, ve které Docker běží). Klikněte pravým tlačítkem na Start →
**Terminál (správce)** nebo **Windows PowerShell (správce)** a zadejte:
```
wsl --install --no-distribution
```
Po dokončení **restartujte PC**. Když WSL už nainstalované je, spusťte místo toho `wsl --update`.
Na starších Windows 10 může příkaz hlásit neznámý parametr. Pak zadejte jen `wsl --install`; pokud se potom otevře okno
Ubuntu a chce uživatelské jméno, můžete ho zavřít, Docker ho nepotřebuje.

## 1b. Nainstalujte Docker Desktop

1. Stáhněte **Docker Desktop for Windows** z https://www.docker.com/products/docker-desktop/ a nainstalujte
   (nechte zaškrtnuté *Use WSL 2*).
2. Restartujte počítač, pokud o to instalátor požádá.
3. Spusťte Docker Desktop, odsouhlaste podmínky (přihlášení k účtu Docker můžete přeskočit).
4. V Docker Desktop → **Settings → General** zaškrtněte **Start Docker Desktop when you sign in to your computer**.
   Díky tomu se aplikace po restartu PC spustí sama, jakmile se někdo přihlásí do Windows.
5. Ověření: otevřete **Příkazový řádek** (Start → napište `cmd`) a zadejte
   ```
   docker --version
   docker compose version
   ```
   Obojí musí vypsat číslo verze.

Když Docker i tak hlásí chybu virtualizace nebo WSL, vraťte se ke kroku 1a: zkontrolujte ve Správci úloh,
že je virtualizace povolená, spusťte `wsl --update` jako správce a restartujte PC.

## 2. Stáhněte aplikaci

**Varianta A, bez Gitu (nejjednodušší):**
1. Otevřete https://github.com/MajkyyQ/BusinessManager → zelené tlačítko **Code → Download ZIP**.
2. Rozbalte ZIP do `C:\` a složku **přejmenujte** z `BusinessManager-main` na `BusinessManager`,
   aby výsledek byl `C:\BusinessManager` (uvnitř je přímo `docker-compose.yml`).

**Varianta B, s Gitem** (pohodlnější pozdější aktualizace; Git pro Windows z https://git-scm.com/download/win):
```
cd C:\
git clone https://github.com/MajkyyQ/BusinessManager.git
```

Nekopírujte do firmy soubor `db.sqlite3` ani složku `media` ze svého vývojového počítače. Jsou v nich testovací data.

## Rychlá cesta: skript `instalace.bat`

Kroky 3 až 5 udělá skript za vás. Po přípravě Windows a instalaci Dockeru (kroky 1a a 1b) a rozbalení aplikace (krok 2):

1. Spusťte Docker Desktop a počkejte, až se načte.
2. Ve složce `C:\BusinessManager` dvakrát klikněte na **`instalace.bat`**.
3. Skript vytvoří soubor `.env` s náhodnými hesly, spustí aplikaci (poprvé 5–15 minut) a otevře prohlížeč.
   Pak pokračujte krokem 6 (průvodce prvním spuštěním).

**Jaká hesla skript vytváří a jestli je potřebujete znát:** dvě, `SECRET_KEY` a `DB_PASSWORD`. Používá je jen aplikace
sama mezi svými částmi, **nikam se nezadávají** a pro přihlášení ani zálohy nejsou potřeba. Jsou uložená v souboru
`C:\BusinessManager\.env` (otevřete ho Poznámkovým blokem). Neměňte je, databáze by se pak neotevřela.
Heslo, které si zapamatovat **musíte**, je heslo účtu administrátora, které si sami zvolíte v průvodci.

Skript na konci vypíše i adresy, na kterých aplikaci otevřete z ostatních počítačů (po povolení firewallu v kroku 7).
Když `.env` už existuje, skript ho nepřepíše, takže ho lze bezpečně spustit znovu.

## 3. Zjistěte adresu počítače (ruční postup)

Tento krok je potřeba jen tehdy, když se k aplikaci budou připojovat i jiné počítače. Pokud se bude pracovat
jen na tomto PC, přeskočte ho i krok 7 a používejte adresu http://localhost:8080.

V příkazovém řádku zadejte:
```
ipconfig
hostname
```
Poznamenejte si **IPv4 adresu** (např. `192.168.1.50`) a **název počítače** (např. `KANCELAR-PC`).

Doporučení: požádejte správce sítě, ať tomuto PC v routeru **zarezervuje pevnou IP adresu**.
Jinak se adresa může po čase změnit a ostatní se nepřipojí.

## 4. Vytvořte soubor s nastavením `.env`

```
cd C:\BusinessManager
copy .env.example .env
notepad .env
```

V Poznámkovém bloku upravte řádky takto (příklad pro IP `192.168.1.50` a název `KANCELAR-PC`):

```
SECRET_KEY=sem-vlozte-dlouhy-nahodny-retezec
DEBUG=0
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.50,KANCELAR-PC
CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://192.168.1.50:8080,http://KANCELAR-PC:8080
DB_NAME=businessmanager
DB_USER=businessmanager
DB_PASSWORD=sem-vlastni-silne-heslo
```

- **SECRET_KEY**: náhodný řetězec aspoň 50 znaků. Vygenerujete ho v PowerShellu:
  `-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 50 | % {[char]$_})`
- **DB_PASSWORD**: heslo k databázi, nikam ho nemusíte zadávat, jen ho nesdílejte.
  Používejte jen písmena a číslice (bez `$`, `#`, mezer a uvozovek).
- **DEBUG=0** nechte, jinak by aplikace při chybě ukazovala technické detaily.
- `DB_NAME` a `DB_USER` neměňte, příkazy pro zálohy níže s nimi počítají.

Soubor uložte. Musí se jmenovat přesně `.env` (ne `.env.txt`). Ověříte to příkazem `dir /a` ve složce.

Soubor `.env` obsahuje hesla. Nedávejte ho na GitHub ani nikam neposílejte.

## 5. Spusťte aplikaci

```
cd C:\BusinessManager
docker compose up -d --build
```

Poprvé to trvá 5–15 minut. Na konci musí být u obou kontejnerů `Started`. Kontrola:
```
docker compose ps
```
Oba řádky (`db` a `web`) musí mít stav `Up` (u `db` navíc `healthy`).

Databázové tabulky (migrace) se vytvoří samy při každém spuštění, nic dalšího se spouštět nemusí.
Příkaz `seed_data` (testovací data) **nespouštějte**.

## 6. První spuštění: účet administrátora a firma

1. Na tomto PC otevřete v prohlížeči **http://localhost:8080**.
2. Otevře se průvodce **První spuštění**:
   - **Krok 1, Účet administrátora:** přihlašovací jméno, jméno, příjmení, e-mail a heslo.
     Tento účet má plná práva (Nastavení, zaměstnanci, Django admin). Heslo si bezpečně uložte.
   - **Krok 2, Údaje o firmě:** povinný je jen název. IČ, DIČ, adresu, číslo účtu, logo a DPH lze doplnit
     později v **Nastavení → Firma**.
3. Ostatním lidem založte účty v **Nastavení → Zaměstnanci**: v kartě zaměstnance je sekce
   *Přihlašovací účet* (jméno, heslo, případně administrátor).
4. Doporučené doplnění: **Nastavení → Firma** (číslo účtu, logo), **Nastavení → Číslování dokladů**,
   **Dokumenty → Šablony dokumentů**.

## 7. Přístup z ostatních počítačů ve firmě

1. Na serverovém PC povolte port 8080 ve firewallu. Otevřete **PowerShell jako správce**
   (Start → PowerShell → pravým tlačítkem → Spustit jako správce) a zadejte:
   ```
   New-NetFirewallRule -DisplayName "BusinessManager 8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private,Domain
   ```
   Síť musí být ve Windows nastavená jako **soukromá** nebo doménová, ne veřejná
   (Nastavení → Síť a internet → vlastnosti připojení).
2. Na jiném PC ve stejné síti otevřete **http://192.168.1.50:8080** (vaše IP) nebo **http://KANCELAR-PC:8080**.
3. Když se zobrazí chyba **400 Bad Request**, adresa chybí v `ALLOWED_HOSTS` v `.env`.
   Doplňte ji (i do `CSRF_TRUSTED_ORIGINS`) a spusťte znovu `docker compose up -d`.

Aplikace běží přes obyčejné `http` jen v místní síti. Nezveřejňujte port 8080 do internetu (nepřesměrovávejte ho v routeru).

## 8. Zálohování

Data jsou ve dvou částech: **databáze** (zákazníci, zakázky, faktury…) a **soubory** (fotky, přílohy, logo).
Obojí zálohuje skript `zaloha.bat` ve složce aplikace.

**Ruční záloha:** dvakrát klikněte na `C:\BusinessManager\zaloha.bat`.
Vytvoří složku `C:\BusinessManager\zalohy\RRRR-MM-DD_HHMM` se souborem `databaze.sql` a složkou `media`.

**Automatická záloha každý den:**
1. Start → **Plánovač úloh** → *Vytvořit základní úlohu*.
2. Název `Záloha BusinessManager`, spouštění **Denně** (např. 12:30, kdy je PC zapnuté).
3. Akce *Spustit program*: `C:\BusinessManager\zaloha.bat`, *Přidat argumenty*: `auto`
   (skript pak nečeká na stisk klávesy), *Spustit v*: `C:\BusinessManager`.

**Zálohy kopírujte i mimo tento počítač** (USB disk, síťový disk, OneDrive). Když se disk PC porouchá,
záloha na stejném disku nepomůže. Staré zálohy občas smažte.

Zálohu databáze dělejte v **Příkazovém řádku (cmd)** nebo skriptem, ne v PowerShellu:
PowerShell při přesměrování `>` změní kódování a záloha by nešla obnovit.

### Obnova ze zálohy (např. na nový PC)

Obnova **přepíše** všechna současná data. Postup v příkazovém řádku ve složce aplikace
(`2026-11-05_1230` nahraďte názvem složky se zálohou):

```
cd C:\BusinessManager
docker compose down
docker volume rm businessmanager_pgdata
docker compose up -d db
timeout /t 15
docker compose exec -T db psql -q -v ON_ERROR_STOP=1 -U businessmanager businessmanager < zalohy\2026-11-05_1230\databaze.sql
docker compose up -d
docker compose cp zalohy\2026-11-05_1230\media\. web:/app/media
```

Název `businessmanager_pgdata` platí pro složku `BusinessManager`. Přesný název zjistíte příkazem `docker volume ls`.
Obnova do databáze, ve které už data jsou, skončí chybami. Proto se databáze nejdřív smaže (`docker volume rm`).

## 9. Běžný provoz

| Co | Příkaz (v `C:\BusinessManager`) |
|---|---|
| Stav aplikace | `docker compose ps` |
| Zastavit | `docker compose stop` |
| Spustit | `docker compose up -d` |
| Výpis chyb | `docker compose logs --tail 100 web` |
| Aktualizace na novou verzi | nejdřív záloha, pak nové soubory (`git pull`, nebo nový ZIP rozbalený přes starý, `.env` zůstane), pak `docker compose up -d --build` |

**Nikdy nespouštějte `docker compose down -v`.** Přepínač `-v` smaže databázi i nahrané soubory.
`docker compose down` bez `-v` je bezpečné.

## 10. Když něco nefunguje

- **Stránka se nenačte ani na serverovém PC:** běží Docker Desktop? `docker compose ps` ukazuje oba kontejnery `Up`?
  Chybu najdete v `docker compose logs web`.
- **`web` stále restartuje:** nejčastěji překlep v `.env`. Po opravě `docker compose up -d`.
- **Na jiném PC se nenačte:** firewall (krok 7), stejná síť, správná IP (`ipconfig`), síť nastavená jako soukromá.
- **400 Bad Request:** adresa chybí v `ALLOWED_HOSTS` (krok 7).
- **403 CSRF při přihlášení:** adresa chybí v `CSRF_TRUSTED_ORIGINS`.
- **Zapomenuté heslo administrátora:**
  `docker compose exec web python manage.py changepassword JMENO`
- **Port 8080 je obsazený:** v `docker-compose.yml` změňte `"8080:8080"` na např. `"8090:8080"`
  a adresy v `.env` upravte na `:8090`.
