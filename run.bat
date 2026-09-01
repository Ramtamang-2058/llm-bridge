@echo off
REM Convenience wrapper: activates the venv and runs a command with it.
REM   run.bat login_setup.py --all
REM   run.bat orchestrator.py --headless
cd /d "%~dp0"

if not exist venv (
  echo No venv found. Run setup.bat first.
  exit /b 1
)
call venv\Scripts\activate.bat
python %*
