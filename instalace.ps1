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
Write-Host "Cekam, az se aplikace nacte..."
$ok = $false
for ($i = 0; $i -lt 60 -and -not $ok; $i++) {
    try { Invoke-WebRequest -Uri "http://localhost:8080/login/" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop | Out-Null; $ok = $true }
    catch { Start-Sleep -Seconds 3 }
}
if (-not $ok) {
    Write-Host "Aplikace zatim neodpovida. Vypis chyb: docker compose logs --tail 50 web" -ForegroundColor Red
    Konec 1
}

Start-Process "http://localhost:8080"
Write-Host ""
Write-Host "Hotovo. Aplikace bezi na http://localhost:8080" -ForegroundColor Green
Write-Host "V prohlizeci zalozte v pruvodci ucet administratora (toto heslo si zapamatujte) a firmu."
Write-Host "Z ostatnich PC ve firme (po povoleni portu 8080 ve firewallu, viz INSTALACE.md):"
Write-Host "  http://${pc}:8080"
foreach ($a in $ip) { Write-Host "  http://${a}:8080" }
Write-Host "Interni hesla aplikace jsou ulozena v souboru $PSScriptRoot\.env (nikam se nezadavaji)."
Konec 0
