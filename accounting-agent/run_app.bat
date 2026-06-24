@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ======================================
echo   AI Agent - Web Interface
echo ======================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Setting up Python environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Install Python from https://python.org first
        pause
        exit /b 1
    )
)

echo Installing dependencies...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Opening web interface at http://localhost:8501
echo Press Ctrl+C to close
echo.

.venv\Scripts\streamlit.exe run app.py --server.headless false --browser.gatherUsageStats false
pause
