@echo off
rem Zaloha BusinessManageru: databaze + nahrane soubory (fotky, prilohy, logo).
rem Spustte dvojklikem nebo z Planovace uloh. Aplikace musi bezet (docker compose up -d).
chcp 65001 >nul
cd /d "%~dp0"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set D=%%i
set CIL=zalohy\%D%
mkdir "%CIL%" 2>nul
echo Zalohuji databazi do %CIL%\databaze.sql ...
docker compose exec -T db pg_dump -U businessmanager businessmanager > "%CIL%\databaze.sql"
if errorlevel 1 (
  echo CHYBA: zaloha databaze se nepovedla. Bezi aplikace? Zkontrolujte "docker compose ps".
  if "%1"=="" pause
  exit /b 1
)
echo Zalohuji soubory do %CIL%\media ...
docker compose cp web:/app/media "%CIL%\media"
if errorlevel 1 (
  echo CHYBA: zaloha souboru se nepovedla.
  if "%1"=="" pause
  exit /b 1
)
echo Hotovo: %CIL%
echo Zalohu zkopirujte i mimo tento pocitac (USB, sitovy disk).
if "%1"=="" timeout /t 10
