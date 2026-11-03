@echo off
rem Starts the USIS risk monitor. Double-click this file, or run it from PowerShell with .\run.bat
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First run: installing the app's Python packages into .venv on this drive. This takes a few minutes...
    python -m venv .venv
    set "TMP=%~dp0.venv"
    set "TEMP=%~dp0.venv"
    ".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements.txt
)

".venv\Scripts\python.exe" -m streamlit run app.py
