@echo off
rem DocSense: start the API and the web UI for local use on Windows.
rem Do NOT run this twice: the local Qdrant store allows only ONE backend process,
rem so a second backend fails with "Storage folder ... is already accessed by another instance".
rem Close both windows first (or press Ctrl+C in each) before starting again.
cd /d "%~dp0"

set "ACTIVATE="
if exist "venv\Scripts\activate.bat" set "ACTIVATE=call venv\Scripts\activate.bat && "
if exist ".venv\Scripts\activate.bat" set "ACTIVATE=call .venv\Scripts\activate.bat && "

start "DocSense API" cmd /k "%ACTIVATE%python -m uvicorn api.main:app --host 127.0.0.1 --port 8000"
timeout /t 8 /nobreak >nul

start "DocSense UI" /d "%~dp0DocSense-UI" cmd /k "npm run dev"
timeout /t 5 /nobreak >nul

start "" "http://localhost:5173"
