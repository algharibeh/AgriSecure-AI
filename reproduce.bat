@echo off
rem AgriSecure-AI: reproduce every result with one double-click (Windows).
rem
rem First run on a fresh copy: creates the repository's own Python environment
rem (.venv) from the pinned requirements. That needs Python 3.9 installed
rem (python.org; the results on record were made with 3.9.13) and an internet
rem connection for pip. Later runs reuse .venv. The tractor recording ships in
rem data\tumosan_raw\FIELD_FILES.zip and reproduce.py unpacks it; the C self-test
rem runs if gcc, cc or clang is on the PATH and is skipped otherwise.
rem Extra arguments are passed on, e.g.   reproduce.bat --skip-sil
setlocal
cd /d "%~dp0"
if exist ".venv\requirements.ok" goto run
if exist ".venv\Scripts\python.exe" goto install

echo No .venv yet: creating the Python environment (first run only).
set "PYCMD="
py -3.9 -c "pass" >nul 2>&1 && set "PYCMD=py -3.9"
if not defined PYCMD if exist "C:\Program Files\Python39\python.exe" set "PYCMD="C:\Program Files\Python39\python.exe""
if not defined PYCMD if exist "%LocalAppData%\Programs\Python\Python39\python.exe" set "PYCMD="%LocalAppData%\Programs\Python\Python39\python.exe""
if not defined PYCMD py -3 -c "pass" >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD python -c "pass" >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD goto nopython

echo Using: %PYCMD%
%PYCMD% -c "import sys; print('Python', sys.version.split()[0]); sys.exit(0 if sys.version_info[:2]==(3,9) else 3)"
if errorlevel 3 echo   note: not Python 3.9; the run will still work, but floating-point details or parquet bytes may differ from the record.
%PYCMD% -m venv .venv
if errorlevel 1 goto venvfail

:install
echo Installing the pinned packages from requirements.txt (about 120 MB; resumes if interrupted).
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --timeout 120 --retries 10 -r requirements.txt
if errorlevel 1 goto pipfail
echo ok> ".venv\requirements.ok"
echo Environment ready.
echo.

:run
".venv\Scripts\python.exe" -I -u reproduce.py --pause %*
endlocal
goto :eof

:nopython
echo Python was not found. Install Python 3.9 from https://www.python.org/downloads/release/python-3913/
echo (tick "Add python.exe to PATH" or keep the py launcher), then double-click this file again.
pause
endlocal
exit /b 2

:venvfail
echo Could not create .venv. Check that Python is installed correctly, then run again.
pause
endlocal
exit /b 2

:pipfail
echo Could not install the pinned packages from requirements.txt (is the internet reachable?).
echo Double-click this file again to resume the installation.
pause
endlocal
exit /b 2
