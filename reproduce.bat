@echo off
rem AgriSecure-AI: reproduce every result with one double-click (Windows).
rem
rem First run on a fresh copy: creates the repository's own Python environment
rem (.venv) from the pinned requirements. That needs Python 3.9 installed
rem (python.org; the results on record were made with 3.9.13; 3.10 to 3.12 also
rem work, with a note) and an internet connection for pip. Later runs reuse
rem .venv. The tractor recording ships in data\tumosan_raw\FIELD_FILES.zip and
rem reproduce.py unpacks it; the C self-test runs if gcc, cc or clang is on the
rem PATH and is skipped otherwise.
rem Extra arguments are passed on, e.g.   reproduce.bat --skip-sil
rem This file must keep Windows (CRLF) line endings: cmd.exe cannot find the
rem labels below in a file with Unix line endings.
setlocal
cd /d "%~dp0"
if exist ".venv\requirements.ok" goto run
if exist ".venv\Scripts\python.exe" goto install

echo No .venv yet: creating the Python environment (first run only).
set "PYCMD="
py -3.9 -c "pass" >nul 2>&1 && set "PYCMD=py -3.9"
if not defined PYCMD if exist "C:\Program Files\Python39\python.exe" set "PYCMD="C:\Program Files\Python39\python.exe""
if not defined PYCMD if exist "%LocalAppData%\Programs\Python\Python39\python.exe" set "PYCMD="%LocalAppData%\Programs\Python\Python39\python.exe""
if defined PYCMD goto found
rem The pinned packages have prebuilt wheels for Python 3.9 to 3.12 only; a newer
rem Python would try to compile numpy from source and fail without a C compiler.
py -3.12 -c "pass" >nul 2>&1 && set "PYCMD=py -3.12"
if not defined PYCMD py -3.11 -c "pass" >nul 2>&1 && set "PYCMD=py -3.11"
if not defined PYCMD py -3.10 -c "pass" >nul 2>&1 && set "PYCMD=py -3.10"
if not defined PYCMD goto nopython
echo   note: Python 3.9 not found; using %PYCMD%. The run works, but floating-point
echo   details or parquet bytes may differ from the record, which was made with 3.9.13.

:found
echo Using: %PYCMD%
%PYCMD% -c "import sys; print('Python', sys.version.split()[0])"
%PYCMD% -m venv .venv
if errorlevel 1 goto venvfail

:install
echo Installing the pinned packages from requirements.txt (about 120 MB; resumes if interrupted).
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --only-binary=:all: --timeout 120 --retries 10 -r requirements.txt
if errorlevel 1 goto pipfail
echo ok> ".venv\requirements.ok"
echo Environment ready.
echo.

:run
".venv\Scripts\python.exe" -I -u reproduce.py --pause %*
endlocal
goto :eof

:nopython
echo.
echo Python 3.9 was not found (nor 3.10, 3.11 or 3.12). Install Python 3.9.13 from
echo   https://www.python.org/downloads/release/python-3913/
echo (64-bit installer; keep the "py launcher" option ticked), then double-click this file again.
echo A newer Python, such as 3.13 or 3.14, cannot install the pinned packages without a C compiler.
pause
endlocal
exit /b 2

:venvfail
echo Could not create .venv. Check that Python is installed correctly, then run again.
pause
endlocal
exit /b 2

:pipfail
echo.
echo Could not install the pinned packages from requirements.txt.
echo If the message above is a download timeout, check the internet connection and
echo double-click this file again to resume. If it says no matching distribution,
echo the Python used is too new: install Python 3.9.13 (link above in this file),
echo delete the .venv folder and run again.
pause
endlocal
exit /b 2
