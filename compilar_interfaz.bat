@echo off
:: Compila interfaz_agentes.py con PyInstaller y copia el resultado a
:: releases\vX.X.X\ (version leida del propio .py). No crea carpetas
:: dist_v2, dist_nuevo, etc. — solo dist\gmn ai\ (siempre el ultimo) y
:: la carpeta de version en releases\.

title Compilando GMN AI

set "PYTHON=C:\Users\warx1\AppData\Local\Programs\Python\Python310\python.exe"
set "DIR_DIST=dist\gmn ai"
set "DIR_RELEASES=releases"

echo =========================================================
echo  Compilando interfaz_agentes.py con PyInstaller...
echo =========================================================
echo.

"%PYTHON%" -m PyInstaller interfaz_agentes.spec --noconfirm --clean
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] La compilacion fallo.
    pause
    exit /b %errorlevel%
)

:: Extraer version del .py  (busca la linea: GMN AI vX.X.X)
for /f "usebackq tokens=*" %%L in (`"%PYTHON%" -c "import re; m=re.search(r'v(\d+\.\d+\.\d+)', open('interfaz_agentes.py',encoding='utf-8').read()); print(m.group(1) if m else 'sin-version')" 2^>nul`) do set "VERSION=%%L"
if "%VERSION%"=="" set "VERSION=sin-version"

set "DESTINO=%DIR_RELEASES%\v%VERSION%"

echo.
echo  Version detectada: v%VERSION%
echo  Copiando a %DESTINO% ...

if not exist "%DIR_RELEASES%" mkdir "%DIR_RELEASES%"

:: Copiar con PowerShell (mas fiable con rutas con espacios)
powershell -NoProfile -Command "
    \$src = '%DIR_DIST%'
    \$dst = '%DESTINO%'
    if (Test-Path \$dst) { Remove-Item -Recurse -Force \$dst }
    Copy-Item -Recurse -Force \$src \$dst
    Write-Host 'Copia OK'
"

if %errorlevel% neq 0 (
    echo [ERROR] No se pudo copiar a %DESTINO%.
    pause
    exit /b 1
)

echo.
echo =========================================================
echo  Compilacion lista.
echo  Ultimo build : dist\gmn ai\interfaz_agentes.exe
echo  Version      : %DESTINO%\interfaz_agentes.exe
echo =========================================================
pause
