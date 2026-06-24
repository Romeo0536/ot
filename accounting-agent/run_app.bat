@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ======================================
echo   AI Agent นักบัญชี — Web Interface
echo ======================================
echo.

REM สร้าง venv ถ้ายังไม่มี
if not exist ".venv\Scripts\python.exe" (
    echo กำลังสร้าง virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ติดตั้ง Python ก่อนที่ https://python.org
        pause
        exit /b 1
    )
)

REM ติดตั้ง/อัปเดต dependencies
echo กำลังติดตั้ง dependencies...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo ติดตั้ง dependencies ไม่สำเร็จ
    pause
    exit /b 1
)

echo.
echo เปิดเว็บที่ http://localhost:8501
echo กด Ctrl+C เพื่อปิดโปรแกรม
echo.

.venv\Scripts\streamlit.exe run app.py --server.headless false --browser.gatherUsageStats false
pause
