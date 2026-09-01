@echo off
REM One-time setup for Windows. Usage: setup.bat
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo python not found. Install Python 3.10+ and re-run.
  exit /b 1
)

echo [1/3] Creating virtualenv...
if not exist venv python -m venv venv

echo [2/3] Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [3/3] Installing Chromium for Playwright...
python -m playwright install chromium

echo.
echo Setup complete. Next steps:
echo   python login_setup.py --all
echo   python cli.py add gemini "my prompt"
echo   python cli.py run
