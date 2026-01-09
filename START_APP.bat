@echo off
REM Rüttenscheid Smart Kalkulation Starter
REM Doppelklick auf diese Datei startet die Anwendung

echo.
echo ========================================
echo   Ruettenscheid Smart Kalkulation
echo ========================================
echo.
echo Starte Anwendung...
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python ist nicht installiert!
    echo Bitte installiere Python von: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Check if requirements are installed
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installiere benoetigte Pakete...
    echo Dies kann einige Minuten dauern...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [FEHLER] Installation fehlgeschlagen!
        pause
        exit /b 1
    )
)

REM Check if secrets.toml exists
if not exist ".streamlit\secrets.toml" (
    echo [WARNUNG] API Key nicht gefunden!
    echo Bitte erstelle die Datei: .streamlit\secrets.toml
    echo Vorlage siehe: .streamlit\secrets.toml.example
    echo.
    pause
    exit /b 1
)

REM Start Streamlit
echo [OK] Starte Anwendung...
echo.
echo Die App oeffnet sich automatisch im Browser.
echo Falls nicht: http://localhost:8501
echo.
echo Zum Beenden: Druecke STRG+C oder schliesse dieses Fenster
echo.

streamlit run main.py

pause
