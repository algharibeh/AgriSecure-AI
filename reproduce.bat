@echo off
rem AgriSecure-AI: reproduce every result with one double-click (Windows).
rem Uses the repository's own Python environment (.venv) so the pinned package
rem versions are the ones that produced the record, and keeps the window open
rem at the end. Extra arguments are passed on, e.g.   reproduce.bat --skip-sil
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto novenv
".venv\Scripts\python.exe" -I -u reproduce.py --pause %*
endlocal
goto :eof

:novenv
echo .venv not found. Create it first - see README, "Running it":
echo   "C:\Program Files\Python39\python.exe" -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
pause
endlocal
exit /b 2