@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or later is required. Install Python and enable Add to PATH.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8765 in your browser after the server starts.
python -m taskflow
if errorlevel 1 pause
