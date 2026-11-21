@echo off
REM Windows: double-click this file (or drag chat.json onto it).
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\make_pdf.py %*
) else (
  py -3 scripts\make_pdf.py %*
)
if errorlevel 1 pause
