@echo off
setlocal EnableDelayedExpansion
title WealthOS — Finance Tracker Setup

echo.
echo  ============================================
echo    WealthOS Personal Finance Tracker
echo  ============================================
echo.

:: ── Check Python ──────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
    where python3 >nul 2>nul
    if errorlevel 1 (
        echo  [ERROR] Python not found.
        echo  Download from: https://www.python.org/downloads/
        echo  Make sure to tick "Add Python to PATH" during install!
        pause & exit /b 1
    )
    set PYTHON=python3
) else (
    set PYTHON=python
)
for /f "tokens=*" %%v in ('!PYTHON! --version') do echo  [OK] %%v found

:: ── Check Node.js ─────────────────────────────
where node >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] Node.js not found.
    echo  Download from: https://nodejs.org/
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do echo  [OK] Node.js %%v found

:: ── Setup Backend ─────────────────────────────
echo.
echo  [1/4] Setting up Python backend...
cd /d "%~dp0backend"

if not exist "venv" (
    echo        Creating virtual environment...
    !PYTHON! -m venv venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create venv. Try: !PYTHON! -m pip install virtualenv
        pause & exit /b 1
    )
)

echo        Installing Python packages...
call venv\Scripts\activate.bat
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] pip install failed. Check your internet connection.
    pause & exit /b 1
)
echo  [OK] Backend dependencies installed

:: ── Setup Frontend ────────────────────────────
echo.
echo  [2/4] Setting up React frontend...
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 (
    echo  [ERROR] npm install failed.
    pause & exit /b 1
)
echo  [OK] Frontend dependencies installed

:: ── Start Backend ─────────────────────────────
echo.
echo  [3/4] Starting backend server (port 8000)...
cd /d "%~dp0backend"
start "WealthOS Backend" cmd /k "call venv\Scripts\activate.bat && uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

:: Wait for backend to be ready
echo        Waiting for backend to start...
timeout /t 4 /nobreak >nul

:: ── Start Frontend ────────────────────────────
echo.
echo  [4/4] Starting frontend (port 3000)...
cd /d "%~dp0frontend"
start "WealthOS Frontend" cmd /k "npm run dev"

:: Wait then open browser
echo.
echo  Waiting for frontend to compile...
timeout /t 8 /nobreak >nul

echo.
echo  ============================================
echo    Opening http://localhost:3000 ...
echo  ============================================
start "" "http://localhost:3000"

echo.
echo  Both servers are running in separate windows.
echo  Close those windows to stop WealthOS.
echo.
pause
