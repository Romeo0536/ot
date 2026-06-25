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

REM Skip Streamlit email prompt on first run
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    mkdir "%USERPROFILE%\.streamlit" 2>nul
    echo [general]> "%USERPROFILE%\.streamlit\credentials.toml"
    echo email = "">> "%USERPROFILE%\.streamlit\credentials.toml"
)

echo.
echo Opening web interface at http://localhost:8501
echo Also accessible from other devices on the same network
echo Press Ctrl+C to close this window when done
echo.

REM Open browser automatically after 3 seconds
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8501"

.venv\Scripts\streamlit.exe run app.py --server.headless true --browser.gatherUsageStats false --server.address 0.0.0.0
pause
