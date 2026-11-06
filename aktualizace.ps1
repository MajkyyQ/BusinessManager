# Aktualizace BusinessManageru: zaloha, stazeni nejnovejsi verze z GitHubu, nove sestaveni a spusteni.
# Spoustejte pres aktualizace.bat (dvojklik). Data (databaze, fotky, prilohy) i soubor .env zustanou.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

$repo = "MajkyyQ/BusinessManager"   # odkud se nova verze stahuje
$vetev = "main"

function Konec($kod) { Write-Host ""; Read-Host "Stisknete Enter pro zavreni okna" | Out-Null; exit $kod }

Write-Host "=== Aktualizace BusinessManager ===" -ForegroundColor Cyan

# 1) Kontroly
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker nebezi. Spustte Docker Desktop, pockejte, az se nacte, a spustte aktualizaci znovu." -ForegroundColor Red
    Konec 1
}
if (-not (Test-Path ".env")) {
    Write-Host "Ve slozce chybi soubor .env, aplikace tu zrejme neni nainstalovana." -ForegroundColor Red
    Write-Host "Aktualizaci spoustejte ve slozce, kde aplikace bezi (napr. C:\BusinessManager)."
    Konec 1
}
Write-Host "Aktualizace stahne nejnovejsi verzi z https://github.com/$repo"
Write-Host "Pred aktualizaci se udela zaloha. Data i nastaveni zustanou."
$volba = Read-Host "Pokracovat? (A/N)"
if ($volba -notmatch '^[aAyY]') { Write-Host "Aktualizace zrusena."; Konec 0 }

# 2) Zaloha (aplikace musi bezet)
Write-Host ""
Write-Host "Spoustim aplikaci kvuli zaloze..."
docker compose up -d *> $null
Start-Sleep -Seconds 5
cmd /c "`"$PSScriptRoot\zaloha.bat`" auto"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Zaloha se nepovedla, aktualizaci proto neprovadim. Nic se nezmenilo." -ForegroundColor Red
    Konec 1
}

# 3) Nove soubory
Write-Host ""
if (Test-Path ".git") {
    Write-Host "Stahuji novou verzi pres git..."
    git pull --ff-only
    if ($LASTEXITCODE -ne 0) { Write-Host "git pull se nepovedl, viz chyba vyse. Aplikace bezi dal ve stare verzi." -ForegroundColor Red; Konec 1 }
} else {
    Write-Host "Stahuji novou verzi z GitHubu..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $docasna = Join-Path $env:TEMP ("bm-aktualizace-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $docasna | Out-Null
    $zip = Join-Path $docasna "aktualizace.zip"
    try {
        $ProgressPreference = "SilentlyContinue"  # bez progress baru je stahovani v PowerShellu 5 mnohem rychlejsi
        Invoke-WebRequest -Uri "https://github.com/$repo/archive/refs/heads/$vetev.zip" -OutFile $zip -UseBasicParsing -ErrorAction Stop
        Expand-Archive -Path $zip -DestinationPath $docasna -Force -ErrorAction Stop
    } catch {
        Write-Host "Stazeni se nepovedlo: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Zkontrolujte pripojeni k internetu. Aplikace bezi dal ve stare verzi."
        Remove-Item -Recurse -Force $docasna -ErrorAction SilentlyContinue
        Konec 1
    }
    $zdroj = Get-ChildItem -Path $docasna -Directory | Select-Object -First 1
    if (-not $zdroj -or -not (Test-Path (Join-Path $zdroj.FullName "docker-compose.yml"))) {
        Write-Host "Stazeny archiv nema ocekavany obsah. Aplikace bezi dal ve stare verzi." -ForegroundColor Red
        Remove-Item -Recurse -Force $docasna -ErrorAction SilentlyContinue
        Konec 1
    }
    # Prepise soubory aplikace; .env a zalohy v archivu nejsou, takze zustanou beze zmeny
    Copy-Item -Path (Join-Path $zdroj.FullName "*") -Destination $PSScriptRoot -Recurse -Force
    Remove-Item -Recurse -Force $docasna -ErrorAction SilentlyContinue
    Write-Host "Nova verze stazena." -ForegroundColor Green
}

# 4) Sestaveni a spusteni nove verze: postara se o to instalacni skript (.env necha beze zmeny,
#    migrace databaze probehnou samy pri startu aplikace). Spousti se uz jeho nova verze.
Write-Host ""
Write-Host "Sestavuji a spoustim novou verzi..."
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "instalace.ps1")
exit $LASTEXITCODE
