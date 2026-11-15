@echo off
rem Zaloha BusinessManageru: databaze + nahrane soubory (fotky, prilohy, logo) + nastaveni (.env).
rem Spustte dvojklikem nebo z Planovace uloh. Aplikace musi bezet (docker compose up -d).
rem V .env lze nastavit (nepovinne):
rem   ZALOHA_KOPIE=E:\Zalohy\BusinessManager  nebo  \\JINE-PC\Zalohy  ... kam kopirovat posledni zalohu
rem                (drzi se tam 2 zalohy: "posledni" a "predposledni", starsi se prepisuji)
rem   ZALOHA_PONECHAT=7  ... kolik zaloh nechat ve slozce zalohy na tomto PC (starsi se smazou)
chcp 65001 >nul
cd /d "%~dp0"
set "KOPIE="
set "PONECHAT=7"
if exist ".env" for /f "usebackq eol=# tokens=1,* delims==" %%a in (`type ".env"`) do (
  if /i "%%a"=="ZALOHA_KOPIE" set "KOPIE=%%b"
  if /i "%%a"=="ZALOHA_PONECHAT" set "PONECHAT=%%b"
)
if defined KOPIE set "KOPIE=%KOPIE:"=%"
if not defined PONECHAT set "PONECHAT=7"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set D=%%i
set CIL=zalohy\%D%
mkdir "%CIL%" 2>nul
echo Zalohuji databazi do %CIL%\databaze.sql ...
docker compose exec -T db pg_dump -U businessmanager businessmanager > "%CIL%\databaze.sql"
if errorlevel 1 (
  echo CHYBA: zaloha databaze se nepovedla. Bezi aplikace? Zkontrolujte "docker compose ps".
  goto :chyba
)
echo Zalohuji soubory do %CIL%\media ...
docker compose cp web:/app/media "%CIL%\media"
if errorlevel 1 (
  echo CHYBA: zaloha souboru se nepovedla.
  goto :chyba
)
if exist ".env" copy /y ".env" "%CIL%\nastaveni.env" >nul
echo Hotovo: %CIL%

rem --- Stare zalohy na tomto PC: ponechat jen poslednich %PONECHAT% (nazvy slozek jsou datum, takze jdou seradit)
set /a PONECHAT=%PONECHAT% 2>nul
if %PONECHAT% LSS 1 set PONECHAT=1
for /f "skip=%PONECHAT% delims=" %%d in ('dir /b /ad /o-n "zalohy"') do (
  echo Mazu starou zalohu zalohy\%%d
  rmdir /s /q "zalohy\%%d"
)

rem --- Kopie na jiny disk nebo PC
if not defined KOPIE (
  echo Zalohu zkopirujte i mimo tento pocitac (USB, sitovy disk^), nebo nastavte ZALOHA_KOPIE v souboru .env.
  goto :konec
)
echo Kopiruji zalohu do %KOPIE% ...
if not exist "%KOPIE%" mkdir "%KOPIE%" 2>nul
if exist "%KOPIE%\nova" rmdir /s /q "%KOPIE%\nova"
robocopy "%CIL%" "%KOPIE%\nova" /E /R:2 /W:5 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo CHYBA: kopie do %KOPIE% se nepovedla. Je disk pripojeny nebo PC zapnute? Zaloha na tomto PC je v poradku.
  if exist "%KOPIE%\nova" rmdir /s /q "%KOPIE%\nova"
  goto :chyba
)
echo %D%> "%KOPIE%\nova\datum-zalohy.txt"
rem predchozi kopie se smaze az ve chvili, kdy je nova cela zkopirovana
if exist "%KOPIE%\predposledni" rmdir /s /q "%KOPIE%\predposledni"
if exist "%KOPIE%\posledni" move "%KOPIE%\posledni" "%KOPIE%\predposledni" >nul
move "%KOPIE%\nova" "%KOPIE%\posledni" >nul
echo Kopie hotova: %KOPIE%\posledni

:konec
if "%1"=="" timeout /t 10
exit /b 0

:chyba
if "%1"=="" pause
exit /b 1
