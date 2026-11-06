# Instalace BusinessManageru na Windows: vytvori .env, spusti aplikaci a otevre prohlizec.
# Spoustejte pres instalace.bat (dvojklik). Predem musi byt nainstalovany a spusteny Docker Desktop.
$ErrorActionPreference = "Continue"  # chybove vystupy dockeru nejsou chyba skriptu
Set-Location -Path $PSScriptRoot

function Konec($kod) { Write-Host ""; Read-Host "Stisknete Enter pro zavreni okna" | Out-Null; exit $kod }

function NahodnyText($delka) {
    $znaky = [char[]]"abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $b = New-Object byte[] $delka; $rng.GetBytes($b)
    -join ($b | ForEach-Object { $znaky[$_ % $znaky.Length] })
}

Write-Host "=== Instalace BusinessManager ===" -ForegroundColor Cyan

# 1) Docker
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker nebezi. Nainstalujte a spustte Docker Desktop, pockejte, az se nacte, a spustte instalaci znovu." -ForegroundColor Red
    Konec 1
}

# 2) Soubor .env (jen pri prvni instalaci, existujici se neprepisuje)
$pc = $env:COMPUTERNAME.ToLower()
$ip = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.InterfaceAlias -notmatch "vEthernet|WSL|Loopback|Docker" } |
        Select-Object -ExpandProperty IPAddress)
if (Test-Path ".env") {
    Write-Host "Soubor .env uz existuje, ponechavam ho beze zmeny."
} else {
    # Databaze z drivejsi instalace (Docker volume) prezije smazani slozky, ale jeji heslo bylo v puvodnim .env.
    # S novym nahodnym heslem by se k ni aplikace neprihlasila ("password authentication failed").
    $projekt = (Split-Path -Leaf $PSScriptRoot).ToLower() -replace '[^a-z0-9_-]', ''
    docker volume inspect "${projekt}_pgdata" *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "V Dockeru zustala databaze z predchozi instalace, ale chybi k ni soubor .env s heslem." -ForegroundColor Yellow
        Write-Host "Mate dve moznosti:"
        Write-Host "  1) Mate puvodni .env (napr. v zaloze)? Zkopirujte ho do teto slozky a spustte instalaci znovu."
        Write-Host "     Data z predchozi instalace zustanou."
        Write-Host "  2) Starou databazi smazat a zacit znovu. VSECHNA DATA z predchozi instalace (vcetne fotek a priloh) se ztrati."
        $volba = Read-Host "Pro smazani napiste SMAZAT, cokoli jineho instalaci ukonci"
        if ($volba -cne "SMAZAT") { Write-Host "Instalace ukoncena, nic se nesmazalo."; Konec 1 }
        # docker compose down bez .env nejde (env_file chybi), proto kontejnery a volumy primo
        $kontejnery = @(docker ps -aq --filter "label=com.docker.compose.project=$projekt")
        if ($kontejnery.Count -gt 0) { docker rm -f $kontejnery *> $null }
        docker volume rm "${projekt}_pgdata" "${projekt}_media" *> $null
        Write-Host "Stara databaze smazana." -ForegroundColor Green
    }
    $hosty = @("localhost", "127.0.0.1", $pc) + $ip
    $puvody = $hosty | ForEach-Object { "http://${_}:8080" }
    $obsah = @(
        "# Vytvoreno skriptem instalace.ps1 $(Get-Date -Format 'yyyy-MM-dd HH:mm'). Soubor nesdilejte, obsahuje hesla.",
        "# SECRET_KEY a DB_PASSWORD pouziva jen aplikace sama, nikam se nezadavaji. Nemente je, databaze by se neotevrela.",
        "SECRET_KEY=$(NahodnyText 60)",
        "DEBUG=0",
        "ALLOWED_HOSTS=$($hosty -join ',')",
        "CSRF_TRUSTED_ORIGINS=$($puvody -join ',')",
        "DB_NAME=businessmanager",
        "DB_USER=businessmanager",
        "DB_PASSWORD=$(NahodnyText 24)"
    )
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot ".env"), (($obsah -join "`n") + "`n"))  # UTF-8 bez BOM, konce radku LF
    Write-Host "Vytvoren soubor .env s nahodnymi hesly." -ForegroundColor Green
}

# 3) Sestaveni a spusteni (poprve 5-15 minut)
Write-Host "Spoustim aplikaci, poprve to muze trvat 5-15 minut..."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Write-Host "Spusteni se nepovedlo, viz chyba vyse." -ForegroundColor Red; Konec 1 }

# 4) Cekani, az aplikace odpovi
# Dotaz jde primo na 127.0.0.1 a bez proxy. "localhost" se na Windows preklada nejdriv na IPv6 (::1)
# a presmerovani portu Dockeru na IPv6 na nekterych PC visi; firemni proxy zas umi localhost zachytit.
function StavHttp {
    try {
        $r = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:8080/login/")
        $r.Proxy = $null; $r.Timeout = 5000; $r.ReadWriteTimeout = 5000; $r.AllowAutoRedirect = $false
        $odp = $r.GetResponse(); $kod = [int]$odp.StatusCode; $odp.Close(); return $kod
    } catch {
        $odp = $_.Exception.InnerException.Response
        if (-not $odp) { $odp = $_.Exception.Response }
        if ($odp) { $kod = [int]$odp.StatusCode; $odp.Close(); return $kod }
        return 0  # zadna odpoved, server jeste nebezi
    }
}

function StavKontejneru {
    $id = (docker compose ps -a -q web 2>$null | Select-Object -First 1)
    if (-not $id) { return @{ Stav = "chybi"; Restarty = 0 } }
    $t = (docker inspect -f "{{.State.Status}} {{.RestartCount}}" $id 2>$null) -split " "
    return @{ Stav = $t[0]; Restarty = [int]$t[1] }
}

$log = Join-Path $PSScriptRoot "instalace-log.txt"
function UlozLog($duvod) {
    Set-Content -Path $log -Encoding UTF8 -Value @(
        "BusinessManager - log instalace $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "Duvod: $duvod", "", "=== docker compose ps -a ===")
    cmd /c "docker compose ps -a >> `"$log`" 2>&1"
    Add-Content -Path $log -Encoding UTF8 -Value @("", "=== docker compose logs web ===")
    cmd /c "docker compose logs --no-color --tail 300 web >> `"$log`" 2>&1"
    Add-Content -Path $log -Encoding UTF8 -Value @("", "=== docker compose logs db ===")
    cmd /c "docker compose logs --no-color --tail 50 db >> `"$log`" 2>&1"
}

function Selhani($duvod) {
    Write-Host ""
    Write-Host $duvod -ForegroundColor Red
    UlozLog $duvod
    if (Select-String -Path $log -Pattern "password authentication failed" -Quiet) {
        Write-Host ""
        Write-Host "Heslo k databazi nesedi: databaze je z drivejsi instalace a soubor .env je novy." -ForegroundColor Yellow
        Write-Host "Vratte puvodni .env, nebo (pokud stara data nepotrebujete) spustte 'docker compose down -v' a instalaci znovu."
    }
    Write-Host ""
    Write-Host "--- posledni radky logu aplikace (docker compose logs web) ---" -ForegroundColor Yellow
    cmd /c "docker compose logs --no-color --tail 40 web 2>&1"
    Write-Host "--------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Cely log je ulozen v souboru:" -ForegroundColor Yellow
    Write-Host "  $log" -ForegroundColor Yellow
    Write-Host "Tento soubor poslete spravci/autorovi aplikace. Otviram ho v Poznamkovem bloku."
    Start-Process notepad.exe -ArgumentList "`"$log`""
    Konec 1
}

Write-Host "Cekam, az se aplikace nacte (prvni spusteni obvykle do 1 minuty, nejvyse 10 minut)..."
$limit = [TimeSpan]::FromMinutes(10)
$hodiny = [System.Diagnostics.Stopwatch]::StartNew()
$dalsiHlaseni = 30
$restartyPred = (StavKontejneru).Restarty  # restarty z drivejsich spusteni se nepocitaji
$ok = $false
while (-not $ok -and $hodiny.Elapsed -lt $limit) {
    $kod = StavHttp
    if ($kod -ge 200 -and $kod -lt 500) { $ok = $true; break }
    if ($kod -ge 500) { Selhani "Aplikace bezi, ale hlasi chybu (HTTP $kod)." }

    $k = StavKontejneru
    if ($k.Stav -eq "exited" -or $k.Stav -eq "dead" -or $k.Stav -eq "chybi") { Selhani "Kontejner aplikace (web) se zastavil (stav: $($k.Stav))." }
    if ($k.Restarty -gt $restartyPred -or $k.Stav -eq "restarting") { Selhani "Kontejner aplikace (web) pri startu spadl a restartuje se." }

    $s = [int]$hodiny.Elapsed.TotalSeconds
    if ($s -ge $dalsiHlaseni) { Write-Host "  porad cekam... ($s s, kontejner web: $($k.Stav))"; $dalsiHlaseni += 30 }
    Start-Sleep -Seconds 3
}

if (-not $ok) {
    # Odpovida aplikace aspon uvnitr kontejneru? Pak bezi a problem je jen ve spojeni z Windows (proxy, antivir, firewall, port).
    docker compose exec -T web python -c "import urllib.request as u; u.urlopen('http://localhost:8080/login/', timeout=5)" *> $null
    if ($LASTEXITCODE -eq 0) {
        UlozLog "Aplikace v kontejneru bezi, ale z Windows na http://127.0.0.1:8080 neodpovida."
        Write-Host ""
        Write-Host "Aplikace v Dockeru bezi, ale skript se k ni z Windows nedostal (http://127.0.0.1:8080)." -ForegroundColor Yellow
        Write-Host "Casta pricina je firemni proxy, antivir nebo firewall. Zkusim otevrit prohlizec."
        Write-Host "Kdyz se stranka nenacte, poslete soubor $log"
    } else {
        Selhani "Aplikace ani po $([int]$limit.TotalMinutes) minutach neodpovida."
    }
}

Start-Process "http://127.0.0.1:8080"
Write-Host ""
Write-Host "Hotovo. Aplikace bezi na http://127.0.0.1:8080" -ForegroundColor Green
Write-Host "V prohlizeci zalozte v pruvodci ucet administratora (toto heslo si zapamatujte) a firmu."
Write-Host "Z ostatnich PC ve firme (po povoleni portu 8080 ve firewallu, viz INSTALACE.md):"
Write-Host "  http://${pc}:8080"
foreach ($a in $ip) { Write-Host "  http://${a}:8080" }
Write-Host "Interni hesla aplikace jsou ulozena v souboru $PSScriptRoot\.env (nikam se nezadavaji)."
Konec 0
